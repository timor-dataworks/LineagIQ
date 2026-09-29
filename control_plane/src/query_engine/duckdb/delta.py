"""DuckDB Delta Lake integration, in-memory snapshot materialization, and commit log timestamps."""

import datetime
import hashlib
import json
import logging
import os
import time
from typing import Any

import duckdb
from deltalake import DeltaTable

from control_plane.src.query_engine.duckdb.connection import (
    configure_duckdb_s3,
    ensure_duckdb_extensions,
    resolve_iam_credentials,
)
from core.constants import get_nodes_table_path
from core.utils import parse_iso_to_epoch_ms

logger = logging.getLogger(__name__)

_TIMESTAMPS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_TIMESTAMPS_CACHE_TTL = 15.0  # 15 seconds commit logs cache


def get_available_timestamps(
    data_base_path: str, storage_options: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Retrieves commit history timestamps from tenant Delta Lake table logs.

    Args:
        data_base_path: Base path to tenant data directory or S3 URI (s3://bucket/tenant).
        storage_options: Optional remote storage backend options (e.g. S3 credentials / endpoint).

    Returns:
        List of dictionaries with 'version', 'timestamp' (ISO 8601), and 'operation'.
    """
    is_s3 = data_base_path.startswith("s3://")
    nodes_dir = f"{data_base_path.rstrip('/')}/graph/nodes" if is_s3 else get_nodes_table_path(data_base_path)

    if is_s3:
        now = time.time()
        clean_path = data_base_path.rstrip("/")
        cache_entry = _TIMESTAMPS_CACHE.get(clean_path)
        if cache_entry and (now - cache_entry[0]) < _TIMESTAMPS_CACHE_TTL:
            return cache_entry[1]
        try:
            import boto3

            s3_path = nodes_dir[5:]
            bucket = s3_path.split("/")[0]
            prefix = s3_path[len(bucket) + 1 :].strip("/")
            log_prefix = f"{prefix}/_delta_log/"

            opts = storage_options or {}
            endpoint = (
                opts.get("AWS_ENDPOINT_URL")
                or opts.get("endpoint_url")
                or opts.get("s3_endpoint")
                or os.getenv("AWS_ENDPOINT_URL")
            )
            ak = opts.get("AWS_ACCESS_KEY_ID") or opts.get("access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
            sk = (
                opts.get("AWS_SECRET_ACCESS_KEY") or opts.get("secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY")
            )
            token = opts.get("AWS_SESSION_TOKEN") or opts.get("session_token") or os.getenv("AWS_SESSION_TOKEN")
            region = (
                opts.get("AWS_REGION")
                or opts.get("region")
                or os.getenv("AWS_REGION")
                or os.getenv("AWS_DEFAULT_REGION")
                or "eu-central-1"
            )

            if not (ak and sk):
                iam_ak, iam_sk, iam_token = resolve_iam_credentials(region)
                ak = ak or iam_ak
                sk = sk or iam_sk
                token = token or iam_token

            client_kwargs: dict[str, Any] = {"region_name": region}
            if endpoint:
                client_kwargs["endpoint_url"] = endpoint
            if ak and sk:
                client_kwargs["aws_access_key_id"] = ak
                client_kwargs["aws_secret_access_key"] = sk
                if token:
                    client_kwargs["aws_session_token"] = token

            s3 = boto3.client("s3", **client_kwargs)
            paginator = s3.get_paginator("list_objects_v2")
            commit_files = []
            for page in paginator.paginate(Bucket=bucket, Prefix=log_prefix):
                for item in page.get("Contents", []):
                    key = item["Key"]
                    filename = key.split("/")[-1]
                    if filename.endswith(".json") and filename[:-5].isdigit():
                        ver = int(filename[:-5])
                        commit_files.append((ver, key))

            results = []
            for ver, key in sorted(commit_files, key=lambda x: x[0]):
                obj = s3.get_object(Bucket=bucket, Key=key)
                content = obj["Body"].read().decode("utf-8")
                commit_info = {}
                for line in content.strip().split("\n"):
                    try:
                        record = json.loads(line)
                        if "commitInfo" in record:
                            commit_info = record["commitInfo"]
                            break
                    except Exception:
                        continue

                commit_ms = commit_info.get("timestamp", 0)
                if commit_ms:
                    dt_obj = datetime.datetime.fromtimestamp(commit_ms / 1000, tz=datetime.UTC)
                    iso_str = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                else:
                    iso_str = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

                results.append(
                    {
                        "version": ver,
                        "timestamp": iso_str,
                        "timestamp_ms": commit_ms,
                        "operation": commit_info.get("operation", "WRITE"),
                    }
                )
            _TIMESTAMPS_CACHE[clean_path] = (now, results)
            return results
        except Exception as e:
            logger.warning(f"Error fetching S3 Delta timestamps via boto3: {e}")

    if not os.path.exists(nodes_dir) or not DeltaTable.is_deltatable(nodes_dir):
        return []

    try:
        dt = DeltaTable(nodes_dir)
        history = dt.history()
        results = []
        for commit in sorted(history, key=lambda x: x.get("version", 0)):
            commit_ms = commit.get("timestamp", 0)
            dt_obj = datetime.datetime.fromtimestamp(commit_ms / 1000, tz=datetime.UTC)
            iso_str = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            results.append(
                {
                    "version": commit.get("version", 0),
                    "timestamp": iso_str,
                    "timestamp_ms": commit_ms,
                    "operation": commit.get("operation", "WRITE"),
                }
            )
        return results
    except Exception as e:
        logger.warning(f"Error fetching available timestamps: {e}")
        return []


def resolve_delta_table(
    con: duckdb.DuckDBPyConnection,
    target_path: str,
    view_name: str,
    as_of: str | None = None,
    storage_options: dict[str, Any] | None = None,
    view_cache: dict[str, Any] | None = None,
) -> bool:
    """Registers a Delta Lake dataset as a DuckDB SQL view.

    Exclusively uses native DuckDB C++ `ATTACH '<path>' AS <alias> (TYPE delta);`
    with direct time-travel querying `SELECT * FROM <alias> AT (VERSION => <version>);`.
    Supports local Delta tables and remote s3:// Delta tables without delta-rs or Parquet fallbacks.

    Args:
        con: Active DuckDB connection instance.
        target_path: File or directory path to Delta dataset (local path or s3:// URI).
        view_name: Registered SQL view name in DuckDB connection.
        as_of: Optional ISO 8601 timestamp string or integer version string for historical snapshots.
        storage_options: Optional remote storage backend options (e.g. S3 credentials / endpoint).
        view_cache: Optional dict cache of currently registered views for fast no-op returns.

    Returns:
        True if Delta table exists and view was registered, False otherwise.
    """
    if view_cache is not None and view_cache.get(view_name) == (target_path, as_of):
        return True

    table_dir = target_path
    is_s3 = target_path.startswith("s3://")
    if not is_s3 and os.path.isfile(target_path) and target_path.endswith(".parquet"):
        table_dir = os.path.dirname(target_path)

    if not is_s3 and not os.path.exists(table_dir):
        return False

    try:
        ensure_duckdb_extensions(con)
        if is_s3:
            configure_duckdb_s3(con, storage_options)

        # Determine historical version if as_of is provided
        target_ver = None
        is_before_history = False
        if as_of is not None:
            if isinstance(as_of, int) or (isinstance(as_of, str) and as_of.isdigit()):
                target_ver = int(as_of)
            else:
                target_ms = parse_iso_to_epoch_ms(as_of)
                if target_ms is not None:
                    base_tenant_dir = table_dir
                    for sub in ["/graph/nodes", "/graph/edges", "/vectors"]:
                        if table_dir.endswith(sub):
                            base_tenant_dir = table_dir[: -len(sub)]
                            break
                    ts_list = get_available_timestamps(base_tenant_dir, storage_options=storage_options)
                    if ts_list and target_ms + 100 < ts_list[0].get("timestamp_ms", 0):
                        is_before_history = True
                    else:
                        for commit in ts_list:
                            if commit.get("timestamp_ms", 0) <= target_ms + 100:
                                target_ver = commit.get("version", 0)
        else:
            # Current snapshot: find latest version for in-memory snapshot caching
            base_tenant_dir = table_dir
            for sub in ["/graph/nodes", "/graph/edges", "/vectors"]:
                if table_dir.endswith(sub):
                    base_tenant_dir = table_dir[: -len(sub)]
                    break
            ts_list = get_available_timestamps(base_tenant_dir, storage_options=storage_options)
            if ts_list:
                target_ver = ts_list[-1].get("version", 0)

        attach_alias = f"delta_{view_name}"
        escaped_path = (target_path if is_s3 else os.path.abspath(table_dir)).replace("'", "''")

        attached_map = view_cache.setdefault("_attached_delta", {}) if view_cache is not None else {}
        if attached_map.get(attach_alias) != escaped_path:
            try:
                con.execute(f"DETACH {attach_alias};")
            except Exception:
                pass
            con.execute(f"ATTACH '{escaped_path}' AS {attach_alias} (TYPE delta);")
            if view_cache is not None:
                attached_map[attach_alias] = escaped_path

        if is_before_history:
            con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM {attach_alias} WHERE 1=0;")
        else:
            # Snapshot In-Memory Caching:
            # Materialize the selected Delta version snapshot into an in-memory DuckDB table
            # so that all graph traversals, joins, and vector distance calculations run 100% in RAM!
            path_hash = hashlib.md5(escaped_path.encode()).hexdigest()[:8]
            ver_label = f"v{target_ver}" if target_ver is not None else "latest"
            mem_table = f"_snapshot_{view_name}_{path_hash}_{ver_label}"

            cached_tables = view_cache.setdefault("_cached_snapshot_tables", set()) if view_cache is not None else set()
            if mem_table not in cached_tables:
                try:
                    exists = con.execute(
                        f"SELECT 1 FROM information_schema.tables WHERE table_name = '{mem_table}' AND table_schema = 'main';"
                    ).fetchone()
                except Exception:
                    exists = None

                if not exists:
                    if target_ver is not None:
                        con.execute(
                            f"CREATE OR REPLACE TABLE {mem_table} AS SELECT * FROM {attach_alias} AT (VERSION => {target_ver});"
                        )
                    else:
                        con.execute(f"CREATE OR REPLACE TABLE {mem_table} AS SELECT * FROM {attach_alias};")
                cached_tables.add(mem_table)

            con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM {mem_table};")

        if view_cache is not None:
            view_cache[view_name] = (target_path, as_of)
        return True
    except Exception as e:
        logger.warning(f"Failed to attach Delta table at {target_path}: {e}")
        return False


resolve_delta_or_parquet_table = resolve_delta_table
