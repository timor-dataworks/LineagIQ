"""DuckDB connection lifecycle, extension loading, and S3 configuration management."""

import logging
import os
import threading
import time
from typing import Any

import duckdb

logger = logging.getLogger(__name__)

_EXTENSIONS_LOADED: set[int] = set()
_S3_CONFIGURED_CONNS: dict[tuple[int, str], float] = {}
_BOTO_SESSION: Any = None
_CREDENTIALS_CACHE: dict[str, Any] = {
    "creds": None,
    "expires_at": 0.0,
}
_CREDENTIAL_TTL_SECONDS = 2700.0  # 45 minutes cache for IAM task/instance profile credentials

_SHARED_CONNECTIONS: dict[str, duckdb.DuckDBPyConnection] = {}
_SHARED_VIEW_CACHES: dict[str, dict[str, Any]] = {}
_CONNECTION_LOCK = threading.Lock()


def get_shared_duckdb_connection(
    data_base_path: str, storage_options: dict[str, Any] | None = None
) -> duckdb.DuckDBPyConnection:
    """Returns a thread-safe shared in-memory DuckDB connection for data_base_path."""
    clean_path = data_base_path.rstrip("/")
    with _CONNECTION_LOCK:
        if clean_path not in _SHARED_CONNECTIONS:
            con = duckdb.connect(database=":memory:")
            ensure_duckdb_extensions(con)
            if clean_path.startswith("s3://") or storage_options:
                configure_duckdb_s3(con, storage_options)
            _SHARED_CONNECTIONS[clean_path] = con
            _SHARED_VIEW_CACHES[clean_path] = {}
        return _SHARED_CONNECTIONS[clean_path]


def get_shared_view_cache(data_base_path: str) -> dict[str, Any]:
    """Returns the view cache associated with the shared connection for data_base_path."""
    clean_path = data_base_path.rstrip("/")
    with _CONNECTION_LOCK:
        if clean_path not in _SHARED_VIEW_CACHES:
            _SHARED_VIEW_CACHES[clean_path] = {}
        return _SHARED_VIEW_CACHES[clean_path]


def clear_duckdb_caches(data_base_path: str | None = None) -> None:
    """Clears in-memory connection and view caches."""
    with _CONNECTION_LOCK:
        if data_base_path:
            clean_path = data_base_path.rstrip("/")
            _SHARED_CONNECTIONS.pop(clean_path, None)
            _SHARED_VIEW_CACHES.pop(clean_path, None)
        else:
            _SHARED_CONNECTIONS.clear()
            _SHARED_VIEW_CACHES.clear()


def resolve_iam_credentials(region: str) -> tuple[str | None, str | None, str | None]:
    """Resolves and caches temporary AWS credentials from Fargate/ECS instance/task profiles."""
    global _BOTO_SESSION
    now = time.time()
    if _CREDENTIALS_CACHE["creds"] is not None and now < _CREDENTIALS_CACHE["expires_at"]:
        return _CREDENTIALS_CACHE["creds"]

    try:
        import boto3

        if _BOTO_SESSION is None:
            _BOTO_SESSION = boto3.Session(region_name=region)
        creds = _BOTO_SESSION.get_credentials()
        if creds:
            frozen = creds.get_frozen_credentials()
            result = (frozen.access_key, frozen.secret_key, getattr(frozen, "token", None))
            _CREDENTIALS_CACHE["creds"] = result
            _CREDENTIALS_CACHE["expires_at"] = now + _CREDENTIAL_TTL_SECONDS
            return result
    except Exception as e:
        logger.debug(f"Could not resolve AWS IAM profile credentials via boto3: {e}")

    return None, None, None


def fetchall_dicts(rel: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Fast extraction of DuckDB query results to dictionaries without Pandas overhead."""
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, row, strict=True)) for row in rel.fetchall()]


def quote_id(val: str) -> str:
    """Escapes single quotes and wraps string in SQL single quotes."""
    return "'" + val.replace("'", "''") + "'"


def ensure_duckdb_extensions(con: duckdb.DuckDBPyConnection) -> None:
    """Ensures required DuckDB extensions (delta, httpfs) are installed and loaded."""
    con_id = id(con)
    if con_id in _EXTENSIONS_LOADED:
        return

    for ext in ["delta", "httpfs"]:
        try:
            con.execute(f"LOAD {ext};")
        except Exception:
            try:
                con.execute(f"INSTALL {ext}; LOAD {ext};")
            except Exception as e:
                logger.debug(f"DuckDB extension {ext} not loaded: {e}")
    _EXTENSIONS_LOADED.add(con_id)


def configure_duckdb_s3(con: duckdb.DuckDBPyConnection, storage_options: dict[str, Any] | None = None) -> None:
    """Configures DuckDB S3 credentials, endpoint, and performance settings for Fargate / AWS environments."""
    con_id = id(con)
    opts = storage_options or {}
    cfg_key = (con_id, str(sorted(opts.items())))
    now = time.time()

    # Fast return if connection already configured within credential TTL
    if cfg_key in _S3_CONFIGURED_CONNS and (now - _S3_CONFIGURED_CONNS[cfg_key]) < _CREDENTIAL_TTL_SECONDS:
        return

    endpoint = (
        opts.get("AWS_ENDPOINT_URL")
        or opts.get("endpoint_url")
        or opts.get("s3_endpoint")
        or os.getenv("AWS_ENDPOINT_URL")
    )
    ak = opts.get("AWS_ACCESS_KEY_ID") or opts.get("access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
    sk = opts.get("AWS_SECRET_ACCESS_KEY") or opts.get("secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
    token = opts.get("AWS_SESSION_TOKEN") or opts.get("session_token") or os.getenv("AWS_SESSION_TOKEN")
    region = (
        opts.get("AWS_REGION")
        or opts.get("region")
        or os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "eu-central-1"
    )

    # If running on Fargate / ECS / App Runner with IAM instance profile (no static keys in env/opts)
    if not (ak and sk):
        iam_ak, iam_sk, iam_token = resolve_iam_credentials(region)
        ak = ak or iam_ak
        sk = sk or iam_sk
        token = token or iam_token

    allow_http = (
        str(opts.get("AWS_ALLOW_HTTP", "")).lower() == "true"
        or (endpoint is not None and "http://" in str(endpoint))
    )

    try:
        con.execute("LOAD httpfs;")

        if endpoint:
            clean_endpoint = endpoint
            if clean_endpoint.startswith("http://"):
                clean_endpoint = clean_endpoint[7:]
            elif clean_endpoint.startswith("https://"):
                clean_endpoint = clean_endpoint[8:]

            use_ssl_val = "false" if allow_http else "true"
            escaped_ak = (ak or "mock").replace("'", "''")
            escaped_sk = (sk or "mock").replace("'", "''")
            escaped_region = region.replace("'", "''")
            escaped_endpoint = clean_endpoint.replace("'", "''")
            escaped_token = (token or "").replace("'", "''")

            token_clause = f", SESSION_TOKEN '{escaped_token}'" if escaped_token else ""
            secret_sql = f"""
            CREATE OR REPLACE SECRET lineagiq_s3 (
                TYPE S3,
                KEY_ID '{escaped_ak}',
                SECRET '{escaped_sk}',
                REGION '{escaped_region}',
                ENDPOINT '{escaped_endpoint}',
                USE_SSL {use_ssl_val},
                URL_STYLE 'path'
                {token_clause}
            );
            """
            con.execute(secret_sql)

        elif ak and sk:
            # Native AWS S3 with IAM instance profile / STS session token on Fargate
            escaped_ak = ak.replace("'", "''")
            escaped_sk = sk.replace("'", "''")
            escaped_region = region.replace("'", "''")
            escaped_token = (token or "").replace("'", "''")

            token_clause = f", SESSION_TOKEN '{escaped_token}'" if escaped_token else ""
            secret_sql = f"""
            CREATE OR REPLACE SECRET lineagiq_s3 (
                TYPE S3,
                KEY_ID '{escaped_ak}',
                SECRET '{escaped_sk}',
                REGION '{escaped_region}',
                URL_STYLE 'vhost'
                {token_clause}
            );
            """
            con.execute(secret_sql)
        else:
            escaped_region = region.replace("'", "''")
            secret_sql = f"""
            CREATE OR REPLACE SECRET lineagiq_s3 (
                TYPE S3,
                PROVIDER CREDENTIAL_CHAIN,
                REGION '{escaped_region}'
            );
            """
            con.execute(secret_sql)

        # Fargate / S3 scan performance optimizations:
        # Cache parquet metadata/footers across queries to avoid redundant S3 GETs
        con.execute("SET enable_object_cache = true;")
        con.execute("SET preserve_insertion_order = false;")

        _S3_CONFIGURED_CONNS[cfg_key] = now

    except Exception as e:
        logger.debug(f"Could not configure DuckDB S3 secret: {e}")
