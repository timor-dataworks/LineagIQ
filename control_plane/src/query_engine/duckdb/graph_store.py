"""DuckDB & Parquet/Delta Lake Implementation of BaseGraphStore."""

import json
import logging
import os
from typing import Any

import duckdb

from control_plane.src.query_engine.base import BaseGraphStore
from control_plane.src.query_engine.duckdb.connection import (
    configure_duckdb_s3,
    ensure_duckdb_extensions,
    fetchall_dicts,
    get_shared_duckdb_connection,
    get_shared_view_cache,
)
from control_plane.src.query_engine.duckdb.delta import (
    get_available_timestamps,
    resolve_delta_or_parquet_table,
)
from core.constants import (
    FILE_DATA_PARQUET,
    get_edges_table_path,
    get_nodes_table_path,
)
from core.utils import extract_search_terms

logger = logging.getLogger(__name__)


class DuckDBGraphStore(BaseGraphStore):
    """DuckDB & Parquet/Delta Lake Implementation of `BaseGraphStore`.

    Executes in-memory SQL queries over Parquet dataset files or Delta Lake tables
    (`graph/nodes` and `graph/edges`) for recursive graph traversals, metadata queries,
    and historical time-travel analysis. Supports local file paths and s3:// URIs.

    Args:
        data_base_path: Root directory path or s3:// URI containing graph and vector Parquet/Delta data.
        storage_options: Optional remote storage backend options (e.g. S3 credentials / endpoint).
        con: Optional existing DuckDB connection instance. If omitted, uses shared connection.
    """

    def __init__(
        self,
        data_base_path: str,
        storage_options: dict[str, Any] | None = None,
        con: duckdb.DuckDBPyConnection | None = None,
    ):
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
        if con is not None:
            self.con = con
        else:
            self.con = get_shared_duckdb_connection(data_base_path, storage_options)
        self._registered_views = get_shared_view_cache(data_base_path)

        ensure_duckdb_extensions(self.con)
        if self.is_s3 or self.storage_options:
            configure_duckdb_s3(self.con, self.storage_options)

    def _synthesize_missing_nodes(self, nodes: list[dict[str, Any]], target_ids: set) -> list[dict[str, Any]]:
        """Helper method to synthesize node metadata for any edge endpoint IDs not present in nodes table.

        Args:
            nodes: List of existing node metadata dictionaries.
            target_ids: Set of all node IDs referenced in edges or lineage traversals.

        Returns:
            Updated nodes list with synthesized placeholder nodes added.
        """
        found_ids = {n["id"] for n in nodes if isinstance(n, dict) and "id" in n}
        for nid in target_ids:
            if nid not in found_ids:
                name = nid.split(".")[-1] if "." in nid else nid
                ntype = "Dataset" if any(k in nid.lower() for k in ["source", "raw", "db.", "table"]) else "Pipeline"
                nodes.append(
                    {
                        "id": nid,
                        "type": ntype,
                        "name": name,
                        "description": f"External Data Asset / Source ({nid})",
                        "properties": json.dumps({"source": "lineage_traversal"}),
                    }
                )
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
            con,
            self.nodes_dir,
            "nodes_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
        ):
            return {"nodes": [], "edges": []}
        if not resolve_delta_or_parquet_table(
            con,
            self.edges_dir,
            "edges_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
        ):
            return {"nodes": [], "edges": []}

        nodes = fetchall_dicts(
            con.execute(
                "SELECT id, FIRST(type) as type, FIRST(name) as name, FIRST(description) as description, "
                "FIRST(properties) as properties FROM nodes_view GROUP BY id"
            )
        )
        edges = fetchall_dicts(con.execute("SELECT DISTINCT source_id, target_id, type, properties FROM edges_view"))

        # Synthesize missing nodes referenced in edges so the graph is always complete
        referenced_ids = {e["source_id"] for e in edges} | {e["target_id"] for e in edges}
        nodes = self._synthesize_missing_nodes(nodes, referenced_ids)

        return {"nodes": nodes, "edges": edges}

    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5, as_of: str | None = None
    ) -> dict[str, Any]:
        """Computes the downstream blast radius traversal starting from a target node.

        Args:
            start_node_id: Canonical target node identifier.
            max_depth: Maximum recursive lineage traversal depth (1 to 10). Defaults to 5.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'root_node', 'impacted_nodes', 'edges', and 'depth_reached'.
        """
        con = self.con
        if not resolve_delta_or_parquet_table(
            con,
            self.nodes_dir,
            "nodes_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
        ):
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}
        if not resolve_delta_or_parquet_table(
            con,
            self.edges_dir,
            "edges_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
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
        edges = fetchall_dicts(edges_rel)

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
        nodes = fetchall_dicts(nodes_rel)

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
        """Computes the upstream root cause traversal starting from a target node.

        Args:
            start_node_id: Canonical target node identifier.
            max_depth: Maximum recursive lineage traversal depth (1 to 10). Defaults to 5.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'target_node', 'upstream_nodes', 'edges', and 'depth_reached'.
        """
        con = self.con
        if not resolve_delta_or_parquet_table(
            con,
            self.nodes_dir,
            "nodes_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
        ):
            return {"upstream_nodes": [], "edges": [], "target_node": None, "depth_reached": 0}
        if not resolve_delta_or_parquet_table(
            con,
            self.edges_dir,
            "edges_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
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
        edges = fetchall_dicts(edges_rel)

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
        nodes = fetchall_dicts(nodes_rel)

        nodes = self._synthesize_missing_nodes(nodes, upstream_node_ids)
        target_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "target_node": target_node,
            "upstream_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def get_nodes_by_ids(self, node_ids: list[str], as_of: str | None = None) -> list[dict[str, Any]]:
        """Retrieves full node metadata records for a given list of node IDs.

        Args:
            node_ids: List of canonical node identifiers.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            List of matching node metadata dictionaries in requested order.
        """
        if not node_ids:
            return []

        con = self.con
        if not resolve_delta_or_parquet_table(
            con,
            self.nodes_dir,
            "nodes_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
        ):
            return []

        query = """
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE id = ANY(?);
        """
        rel = con.execute(query, [node_ids])
        records = fetchall_dicts(rel)
        record_map = {r["id"]: r for r in records}
        return [record_map[vid] for vid in node_ids if vid in record_map]

    def search_nodes_by_terms(self, query_text: str, top_k: int = 5, as_of: str | None = None) -> list[dict[str, Any]]:
        """Searches graph node metadata fields (name, id, description, properties) for matching keywords.

        Args:
            query_text: User search query or keyword phrase.
            top_k: Maximum number of candidate node records to return. Defaults to 5.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            List of matching node metadata dictionaries.
        """
        if not query_text or not query_text.strip():
            return []

        con = self.con
        if not resolve_delta_or_parquet_table(
            con,
            self.nodes_dir,
            "nodes_view",
            as_of=as_of,
            storage_options=self.storage_options,
            view_cache=self._registered_views,
        ):
            return []

        terms = extract_search_terms(query_text)
        if not terms:
            return []

        where_clauses = []
        params = []
        for t in terms:
            param = f"%{t.lower()}%"
            where_clauses.extend(
                [
                    "LOWER(name) LIKE ?",
                    "LOWER(id) LIKE ?",
                    "LOWER(COALESCE(description, '')) LIKE ?",
                    "LOWER(type) LIKE ?",
                    "LOWER(CAST(properties AS VARCHAR)) LIKE ?",
                ]
            )
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
        return fetchall_dicts(rel)

    def _get_scoped_node_ids(self, graph: dict[str, Any], start_node_id: str | None, as_of: str | None = None) -> set:
        """Helper to compute set of node IDs connected to start_node_id (upstream + downstream)."""
        nodes = graph.get("nodes", [])
        if not nodes or not start_node_id:
            return {n["id"] for n in nodes}

        clean_start = start_node_id.strip().lower()
        if not clean_start or clean_start in ["all", "enterprise", "global", "none"]:
            return {n["id"] for n in nodes}

        matched_target_ids = {
            n["id"] for n in nodes if clean_start == n.get("id", "").lower() or clean_start == n.get("name", "").lower()
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
        """Computes schema and lineage graph diff between two historical ISO 8601 timestamps.

        Args:
            start_node_id: Canonical asset identifier to scope diff assessment (or None for global).
            timestamp_t1: Initial ISO 8601 timestamp string.
            timestamp_t2: Subsequent ISO 8601 timestamp string.

        Returns:
            Dictionary containing added_nodes, removed_nodes, modified_nodes, added_edges,
            removed_edges, and summary counts.
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
            {"source_id": s, "target_id": t, "type": ty} for (s, t, ty) in edges_t2 if (s, t, ty) not in edges_t1
        ]
        removed_edges = [
            {"source_id": s, "target_id": t, "type": ty} for (s, t, ty) in edges_t1 if (s, t, ty) not in edges_t2
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

    def get_available_timestamps(self) -> list[dict[str, Any]]:
        """Retrieves available commit history timestamps from tenant Delta Lake table logs.

        Returns:
            List of dictionaries with 'version', 'timestamp', and 'operation'.
        """
        return get_available_timestamps(self.base_path, storage_options=self.storage_options)
