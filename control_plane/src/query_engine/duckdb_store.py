import datetime
import json
import logging
import os
from typing import Any

import duckdb
from deltalake import DeltaTable

from control_plane.src.query_engine.base import BaseGraphStore
from core.constants import (
    FILE_DATA_PARQUET,
    get_edges_table_path,
    get_nodes_table_path,
)
from core.utils import extract_search_terms, parse_iso_to_epoch_ms

logger = logging.getLogger(__name__)


_EXTENSIONS_LOADED = set()
_S3_CONFIGURED = set()


def _fetchall_dicts(rel: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Fast extraction of DuckDB query results to dictionaries without Pandas overhead."""
    cols = [d[0] for d in rel.description]
    return [dict(zip(cols, row, strict=True)) for row in rel.fetchall()]



def _quote_id(val: str) -> str:
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
    """Configures DuckDB S3 credentials/endpoint for direct S3 delta_scan access."""
    con_id = id(con)
    cfg_key = (con_id, str(sorted((storage_options or {}).items())))
    if cfg_key in _S3_CONFIGURED:
        return

    opts = storage_options or {}
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

    if not (ak and sk):
        try:
            import boto3
            session = boto3.Session(region_name=region)
            creds = session.get_credentials()
            if creds:
                frozen = creds.get_frozen_credentials()
                ak = ak or frozen.access_key
                sk = sk or frozen.secret_key
                token = token or getattr(frozen, "token", None)
        except Exception as e:
            logger.debug(f"Could not resolve AWS credentials from boto3: {e}")

    allow_http = (
        str(opts.get("AWS_ALLOW_HTTP", "")).lower() == "true"
        or "http://" in str(endpoint)
    )

    try:
        con.execute("LOAD httpfs;")
        if endpoint or (ak and sk):
            clean_endpoint = endpoint
            if clean_endpoint and clean_endpoint.startswith("http://"):
                clean_endpoint = clean_endpoint[7:]
            elif clean_endpoint and clean_endpoint.startswith("https://"):
                clean_endpoint = clean_endpoint[8:]

            use_ssl_val = "false" if allow_http else "true"
            escaped_ak = (ak or "mock").replace("'", "''")
            escaped_sk = (sk or "mock").replace("'", "''")
            escaped_region = region.replace("'", "''")
            escaped_endpoint = clean_endpoint.replace("'", "''") if clean_endpoint else ""
            escaped_token = (token or "").replace("'", "''")

            extra_clauses = []
            if escaped_endpoint:
                extra_clauses.append(f", ENDPOINT '{escaped_endpoint}'")
                extra_clauses.append(f", USE_SSL {use_ssl_val}")
                extra_clauses.append(", URL_STYLE 'path'")
            if escaped_token:
                extra_clauses.append(f", SESSION_TOKEN '{escaped_token}'")

            extra_sql = "".join(extra_clauses)
            secret_sql = f"""
            CREATE OR REPLACE SECRET lineagiq_s3 (
                TYPE S3,
                KEY_ID '{escaped_ak}',
                SECRET '{escaped_sk}',
                REGION '{escaped_region}'
                {extra_sql}
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
        _S3_CONFIGURED.add(cfg_key)

    except Exception as e:
        logger.debug(f"Could not configure DuckDB S3 secret: {e}")


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
        elif target_ver is not None:
            con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM {attach_alias} AT (VERSION => {target_ver});")
        else:
            con.execute(f"CREATE OR REPLACE VIEW {view_name} AS SELECT * FROM {attach_alias};")


        if view_cache is not None:
            view_cache[view_name] = (target_path, as_of)
        return True
    except Exception as e:
        logger.warning(f"Failed to attach Delta table at {target_path}: {e}")
        return False


resolve_delta_or_parquet_table = resolve_delta_table



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
        try:
            import boto3
            s3_path = nodes_dir[5:]
            bucket = s3_path.split("/")[0]
            prefix = s3_path[len(bucket) + 1 :].strip("/")
            log_prefix = f"{prefix}/_delta_log/"

            opts = storage_options or {}
            endpoint = opts.get("AWS_ENDPOINT_URL") or opts.get("endpoint_url") or opts.get("s3_endpoint") or os.getenv("AWS_ENDPOINT_URL")
            ak = opts.get("AWS_ACCESS_KEY_ID") or opts.get("access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")
            token = opts.get("AWS_SESSION_TOKEN") or opts.get("session_token") or os.getenv("AWS_SESSION_TOKEN")
            region = opts.get("AWS_REGION") or opts.get("region") or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "eu-central-1"

            client_kwargs = {"region_name": region}
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

                results.append({
                    "version": ver,
                    "timestamp": iso_str,
                    "timestamp_ms": commit_ms,
                    "operation": commit_info.get("operation", "WRITE"),
                })
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
            results.append({
                "version": commit.get("version", 0),
                "timestamp": iso_str,
                "timestamp_ms": commit_ms,
                "operation": commit.get("operation", "WRITE"),
            })
        return results
    except Exception as e:
        logger.warning(f"Error fetching available timestamps: {e}")
        return []



class DuckDBGraphStore(BaseGraphStore):
    """DuckDB & Parquet/Delta Lake Implementation of `BaseGraphStore`.

    Executes in-memory SQL queries over Parquet dataset files or Delta Lake tables
    (`graph/nodes` and `graph/edges`) for recursive graph traversals, metadata queries,
    and historical time-travel analysis. Supports local file paths and s3:// URIs.

    Args:
        data_base_path: Root directory path or s3:// URI containing graph and vector Parquet/Delta data.
        storage_options: Optional remote storage backend options (e.g. S3 credentials / endpoint).
    """

    def __init__(self, data_base_path: str, storage_options: dict[str, Any] | None = None):
        self.base_path = data_base_path
        self.storage_options = storage_options
        self.is_s3 = data_base_path.startswith("s3://")
        if self.is_s3:
            base_clean = data_base_path.rstrip("/")
            self.nodes_dir = f"{base_clean}/graph/nodes"
            self.edges_dir = f"{base_clean}/graph/edges"
            self.nodes_file = ""
            self.edges_file = ""
        else:
            self.nodes_dir = get_nodes_table_path(data_base_path)
            self.edges_dir = get_edges_table_path(data_base_path)
            self.nodes_file = os.path.join(self.nodes_dir, FILE_DATA_PARQUET)
            self.edges_file = os.path.join(self.edges_dir, FILE_DATA_PARQUET)

        # Persistent DuckDB connection with pre-loaded extensions and S3 secrets
        self.con = duckdb.connect(database=":memory:")
        self._registered_views: dict[str, tuple[str, str | None]] = {}
        ensure_duckdb_extensions(self.con)
        if self.is_s3 or self.storage_options:
            configure_duckdb_s3(self.con, self.storage_options)

    def _synthesize_missing_nodes(self, nodes: list[dict[str, Any]], target_ids: set) -> list[dict[str, Any]]:
        """
        Helper method to synthesize node metadata for any edge endpoint IDs not present in nodes table.

        :param nodes: List of existing node metadata dictionaries.
        :param target_ids: Set of all node IDs referenced in edges or lineage traversals.
        :return: Updated nodes list with synthesized placeholder nodes added.
        """
        found_ids = {n["id"] for n in nodes if isinstance(n, dict) and "id" in n}
        for nid in target_ids:
            if nid not in found_ids:
                name = nid.split(".")[-1] if "." in nid else nid
                ntype = "Dataset" if any(k in nid.lower() for k in ["source", "raw", "db.", "table"]) else "Pipeline"
                nodes.append({
                    "id": nid,
                    "type": ntype,
                    "name": name,
                    "description": f"External Data Asset / Source ({nid})",
                    "properties": json.dumps({"source": "lineage_traversal"}),
                })
                found_ids.add(nid)
        return nodes

    def get_full_graph(self, as_of: str | None = None) -> dict[str, Any]:
        """Retrieves all graph nodes and edges as of optional ISO 8601 timestamp.

        Args:
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'nodes' list and 'edges' list.
        """
        con = self.con
        if not resolve_delta_or_parquet_table(
            con, self.nodes_dir, "nodes_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return {"nodes": [], "edges": []}
        if not resolve_delta_or_parquet_table(
            con, self.edges_dir, "edges_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return {"nodes": [], "edges": []}

        nodes = _fetchall_dicts(
            con.execute(
                "SELECT id, FIRST(type) as type, FIRST(name) as name, FIRST(description) as description, FIRST(properties) as properties FROM nodes_view GROUP BY id"
            )
        )
        edges = _fetchall_dicts(
            con.execute(
                "SELECT DISTINCT source_id, target_id, type, properties FROM edges_view"
            )
        )

        # Synthesize missing nodes referenced in edges so the graph is always complete
        referenced_ids = {e["source_id"] for e in edges} | {e["target_id"] for e in edges}
        nodes = self._synthesize_missing_nodes(nodes, referenced_ids)

        return {"nodes": nodes, "edges": edges}

    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5, as_of: str | None = None
    ) -> dict[str, Any]:
        """
        Executes recursive CTE traversal in DuckDB to compute downstream blast radius starting from `start_node_id`.

        :param start_node_id: Target node canonical ID.
        :param max_depth: Maximum recursive lineage traversal depth (1 to 10).
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: Traversal payload containing 'root_node', 'impacted_nodes', 'edges', and 'depth_reached'.
        """
        con = self.con
        if not resolve_delta_or_parquet_table(
            con, self.nodes_dir, "nodes_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}
        if not resolve_delta_or_parquet_table(
            con, self.edges_dir, "edges_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}

        safe_depth = max(1, min(max_depth, 10))
        query = f"""
        WITH RECURSIVE downstream_traverse(source_id, target_id, type, depth) AS (
            SELECT source_id, target_id, type, 1 AS depth
            FROM edges_view
            WHERE source_id = ?

            UNION ALL

            SELECT e.source_id, e.target_id, e.type, d.depth + 1
            FROM edges_view e
            JOIN downstream_traverse d ON e.source_id = d.target_id
            WHERE d.depth < {safe_depth} AND e.type != 'BELONGS_TO'
        )
        SELECT DISTINCT source_id, target_id, type, depth
        FROM downstream_traverse;
        """

        edges_rel = con.execute(query, [start_node_id])
        edges = _fetchall_dicts(edges_rel)

        impacted_node_ids = set()
        for e in edges:
            impacted_node_ids.add(e["source_id"])
            impacted_node_ids.add(e["target_id"])

        if not impacted_node_ids:
            impacted_node_ids.add(start_node_id)

        nodes_query = """
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE id = ANY(?);
        """
        nodes_rel = con.execute(nodes_query, [list(impacted_node_ids)])
        nodes = _fetchall_dicts(nodes_rel)

        nodes = self._synthesize_missing_nodes(nodes, impacted_node_ids)
        root_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "root_node": root_node,
            "impacted_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5, as_of: str | None = None
    ) -> dict[str, Any]:
        """
        Executes recursive CTE traversal in DuckDB to compute upstream root cause dependencies starting from `start_node_id`.

        :param start_node_id: Target node canonical ID.
        :param max_depth: Maximum recursive lineage traversal depth (1 to 10).
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: Traversal payload containing 'target_node', 'upstream_nodes', 'edges', and 'depth_reached'.
        """
        con = self.con
        if not resolve_delta_or_parquet_table(
            con, self.nodes_dir, "nodes_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return {"upstream_nodes": [], "edges": [], "target_node": None, "depth_reached": 0}
        if not resolve_delta_or_parquet_table(
            con, self.edges_dir, "edges_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return {"upstream_nodes": [], "edges": [], "target_node": None, "depth_reached": 0}

        safe_depth = max(1, min(max_depth, 10))
        query = f"""
        WITH RECURSIVE upstream_traverse(source_id, target_id, type, depth) AS (
            SELECT source_id, target_id, type, 1 AS depth
            FROM edges_view
            WHERE target_id = ? AND type != 'BELONGS_TO'

            UNION ALL

            SELECT e.source_id, e.target_id, e.type, u.depth + 1
            FROM edges_view e
            JOIN upstream_traverse u ON e.target_id = u.source_id
            WHERE u.depth < {safe_depth} AND e.type != 'BELONGS_TO'
        )
        SELECT DISTINCT source_id, target_id, type, depth
        FROM upstream_traverse;
        """

        edges_rel = con.execute(query, [start_node_id])
        edges = _fetchall_dicts(edges_rel)

        upstream_node_ids = set()
        for e in edges:
            upstream_node_ids.add(e["source_id"])
            upstream_node_ids.add(e["target_id"])

        if not upstream_node_ids:
            upstream_node_ids.add(start_node_id)

        nodes_query = """
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE id = ANY(?);
        """
        nodes_rel = con.execute(nodes_query, [list(upstream_node_ids)])
        nodes = _fetchall_dicts(nodes_rel)

        nodes = self._synthesize_missing_nodes(nodes, upstream_node_ids)
        target_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "target_node": target_node,
            "upstream_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def get_nodes_by_ids(
        self, node_ids: list[str], as_of: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieves full node metadata records for a given list of node IDs.

        :param node_ids: List of canonical node identifiers.
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: List of matching node metadata dictionaries in requested order.
        """
        if not node_ids:
            return []

        con = self.con
        if not resolve_delta_or_parquet_table(
            con, self.nodes_dir, "nodes_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return []

        query = """
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE id = ANY(?);
        """
        rel = con.execute(query, [node_ids])
        records = _fetchall_dicts(rel)
        record_map = {r["id"]: r for r in records}
        return [record_map[vid] for vid in node_ids if vid in record_map]

    def search_nodes_by_terms(
        self, query_text: str, top_k: int = 5, as_of: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Searches node metadata fields (name, id, description, type, properties) using SQL LIKE clauses.

        :param query_text: User search query or keyword phrase.
        :param top_k: Maximum number of candidate node records to return.
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: List of matching node metadata dictionaries.
        """
        if not query_text or not query_text.strip():
            return []

        con = self.con
        if not resolve_delta_or_parquet_table(
            con, self.nodes_dir, "nodes_view", as_of=as_of, storage_options=self.storage_options, view_cache=self._registered_views
        ):
            return []

        terms = extract_search_terms(query_text)
        if not terms:
            return []

        where_clauses = []
        params = []
        for t in terms:
            param = f"%{t.lower()}%"
            where_clauses.extend([
                "LOWER(name) LIKE ?",
                "LOWER(id) LIKE ?",
                "LOWER(COALESCE(description, '')) LIKE ?",
                "LOWER(type) LIKE ?",
                "LOWER(CAST(properties AS VARCHAR)) LIKE ?",
            ])
            params.extend([param] * 5)

        safe_top_k = max(1, top_k)
        where_stmt = " OR ".join(where_clauses)
        query = f"""
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE {where_stmt}
        LIMIT {safe_top_k * 2};
        """
        rel = con.execute(query, params)
        return _fetchall_dicts(rel)

    def _get_scoped_node_ids(self, graph: dict[str, Any], start_node_id: str | None, as_of: str | None = None) -> set:
        """Helper to compute set of node IDs connected to start_node_id (upstream + downstream)."""
        nodes = graph.get("nodes", [])
        if not nodes or not start_node_id:
            return {n["id"] for n in nodes}

        clean_start = start_node_id.strip().lower()
        if not clean_start or clean_start in ["all", "enterprise", "global", "none"]:
            return {n["id"] for n in nodes}

        matched_target_ids = {
            n["id"] for n in nodes
            if clean_start == n.get("id", "").lower() or clean_start == n.get("name", "").lower()
        }
        if not matched_target_ids:
            for n in nodes:
                nid = n.get("id", "").lower()
                name = n.get("name", "").lower()
                if clean_start in nid or clean_start in name:
                    matched_target_ids.add(n["id"])

        if not matched_target_ids:
            return set()


        scoped_ids = set(matched_target_ids)
        for target_id in matched_target_ids:
            blast = self.get_downstream_blast_radius(start_node_id=target_id, max_depth=5, as_of=as_of)
            root_cause = self.get_upstream_root_cause(start_node_id=target_id, max_depth=5, as_of=as_of)

            for n in blast.get("impacted_nodes", []):
                scoped_ids.add(n["id"])
            for n in root_cause.get("upstream_nodes", []):
                scoped_ids.add(n["id"])

        # Include all column nodes belonging to any scoped dataset node
        for e in graph.get("edges", []):
            if e.get("type") == "BELONGS_TO" and e.get("target_id") in scoped_ids:
                scoped_ids.add(e["source_id"])

        return scoped_ids

    def get_schema_time_travel_diff(
        self, start_node_id: str | None, timestamp_t1: str, timestamp_t2: str
    ) -> dict[str, Any]:
        """Computes schema and lineage graph diff between two historical ISO 8601 timestamps,
        optionally scoped to target start_node_id and its connected lineage sub-graph.

        Args:
            start_node_id: Canonical asset identifier to scope diff assessment.
            timestamp_t1: Initial ISO 8601 timestamp string.
            timestamp_t2: Subsequent ISO 8601 timestamp string.

        Returns:
            Dictionary containing added_nodes, removed_nodes, modified_nodes, and edge_changes.
        """
        graph_t1 = self.get_full_graph(as_of=timestamp_t1)
        graph_t2 = self.get_full_graph(as_of=timestamp_t2)

        target_clean = (start_node_id or "").strip()
        is_global = not target_clean or target_clean.lower() in ["all", "enterprise", "global", "none"]

        if is_global:
            scoped_ids_t1 = {n["id"] for n in graph_t1.get("nodes", [])}
            scoped_ids_t2 = {n["id"] for n in graph_t2.get("nodes", [])}
        else:
            scoped_ids_t1 = self._get_scoped_node_ids(graph_t1, target_clean, as_of=timestamp_t1)
            scoped_ids_t2 = self._get_scoped_node_ids(graph_t2, target_clean, as_of=timestamp_t2)

        nodes_t1 = {n["id"]: n for n in graph_t1.get("nodes", []) if n["id"] in scoped_ids_t1}
        nodes_t2 = {n["id"]: n for n in graph_t2.get("nodes", []) if n["id"] in scoped_ids_t2}

        added_nodes = [n for nid, n in nodes_t2.items() if nid not in nodes_t1]
        removed_nodes = [n for nid, n in nodes_t1.items() if nid not in nodes_t2]

        modified_nodes = []
        for nid, n2 in nodes_t2.items():
            if nid in nodes_t1:
                n1 = nodes_t1[nid]
                if (
                    n1.get("name") != n2.get("name")
                    or n1.get("type") != n2.get("type")
                    or n1.get("properties") != n2.get("properties")
                    or n1.get("description") != n2.get("description")
                ):
                    modified_nodes.append({"id": nid, "before": n1, "after": n2})

        edges_t1 = {
            (e["source_id"], e["target_id"], e["type"])
            for e in graph_t1.get("edges", [])
            if e["source_id"] in scoped_ids_t1 or e["target_id"] in scoped_ids_t1
        }
        edges_t2 = {
            (e["source_id"], e["target_id"], e["type"])
            for e in graph_t2.get("edges", [])
            if e["source_id"] in scoped_ids_t2 or e["target_id"] in scoped_ids_t2
        }

        added_edges = [
            {"source_id": s, "target_id": t, "type": ty}
            for (s, t, ty) in edges_t2 if (s, t, ty) not in edges_t1
        ]
        removed_edges = [
            {"source_id": s, "target_id": t, "type": ty}
            for (s, t, ty) in edges_t1 if (s, t, ty) not in edges_t2
        ]

        return {
            "start_node_id": start_node_id,
            "timestamp_t1": timestamp_t1,
            "timestamp_t2": timestamp_t2,
            "added_nodes_count": len(added_nodes),
            "removed_nodes_count": len(removed_nodes),
            "modified_nodes_count": len(modified_nodes),
            "added_nodes": added_nodes,
            "removed_nodes": removed_nodes,
            "modified_nodes": modified_nodes,
            "added_edges": added_edges,
            "removed_edges": removed_edges,
        }
