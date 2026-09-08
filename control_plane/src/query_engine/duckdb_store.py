import os
import json
import re
import datetime
import logging
from typing import Dict, Any, List, Optional
import duckdb
from deltalake import DeltaTable
from control_plane.src.query_engine.base import BaseGraphStore
from core.utils import STOP_WORDS, extract_search_terms, parse_iso_to_epoch_ms
from core.constants import (
    get_nodes_table_path,
    get_edges_table_path,
    FILE_DATA_PARQUET,
)

logger = logging.getLogger(__name__)


def _quote_id(val: str) -> str:
    """Escapes single quotes and wraps string in SQL single quotes."""
    return "'" + val.replace("'", "''") + "'"


def resolve_delta_or_parquet_table(
    con: duckdb.DuckDBPyConnection,
    target_path: str,
    view_name: str,
    as_of: Optional[str] = None,
) -> bool:
    """Registers Delta Lake or Parquet dataset as a DuckDB SQL view.

    If target_path is a Delta Lake table directory, resolves the target version
    corresponding to `as_of` timestamp (if provided) and registers PyArrow table.
    Otherwise, registers standard Parquet file SQL view.

    Args:
        con: Active DuckDB connection instance.
        target_path: File or directory path to dataset.
        view_name: Registered SQL view name in DuckDB connection.
        as_of: Optional ISO 8601 timestamp string.

    Returns:
        True if table/file exists and view was registered, False otherwise.
    """
    table_dir = target_path
    if os.path.isfile(target_path) and target_path.endswith(".parquet"):
        table_dir = os.path.dirname(target_path)

    if os.path.exists(table_dir) and DeltaTable.is_deltatable(table_dir):
        try:
            dt = DeltaTable(table_dir)
            target_ms = parse_iso_to_epoch_ms(as_of)
            if target_ms is not None:
                history = dt.history()
                matching_ver = 0
                for commit in sorted(history, key=lambda x: x.get("version", 0)):
                    if commit.get("timestamp", 0) <= target_ms + 100:
                        matching_ver = commit.get("version", 0)
                dt.load_as_version(matching_ver)

            pa_table = dt.to_pyarrow_table()
            con.register(view_name, pa_table)
            return True
        except Exception as e:
            logger.warning(f"Failed to load Delta table at {table_dir}: {e}")

    # Fallback to direct parquet file scan
    p_file = target_path
    if os.path.isdir(target_path):
        data_parquet = os.path.join(target_path, "data.parquet")
        nodes_parquet = os.path.join(target_path, "nodes.parquet")
        if os.path.exists(data_parquet):
            p_file = data_parquet
        elif os.path.exists(nodes_parquet):
            p_file = nodes_parquet

    if os.path.exists(p_file) and os.path.isfile(p_file):
        p_file_escaped = p_file.replace("'", "''")
        con.execute(f"CREATE VIEW {view_name} AS SELECT * FROM read_parquet('{p_file_escaped}');")
        return True

    return False


def get_available_timestamps(data_base_path: str) -> List[Dict[str, Any]]:
    """Retrieves commit history timestamps from tenant Delta Lake table logs.

    Args:
        data_base_path: Base path to tenant data directory.

    Returns:
        List of dictionaries with 'version', 'timestamp' (ISO 8601), and 'operation'.
    """
    nodes_dir = get_nodes_table_path(data_base_path)
    if not os.path.exists(nodes_dir) or not DeltaTable.is_deltatable(nodes_dir):
        return []

    try:
        dt = DeltaTable(nodes_dir)
        history = dt.history()
        results = []
        for commit in sorted(history, key=lambda x: x.get("version", 0)):
            commit_ms = commit.get("timestamp", 0)
            dt_obj = datetime.datetime.fromtimestamp(commit_ms / 1000, tz=datetime.timezone.utc)
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
    and historical time-travel analysis.

    Args:
        data_base_path: Root directory path containing graph and vector Parquet/Delta data.
    """

    def __init__(self, data_base_path: str):
        self.base_path = data_base_path
        self.nodes_dir = get_nodes_table_path(data_base_path)
        self.edges_dir = get_edges_table_path(data_base_path)
        self.nodes_file = os.path.join(self.nodes_dir, FILE_DATA_PARQUET)
        self.edges_file = os.path.join(self.edges_dir, FILE_DATA_PARQUET)

    def _synthesize_missing_nodes(self, nodes: List[Dict[str, Any]], target_ids: set) -> List[Dict[str, Any]]:
        """
        Helper method to synthesize node metadata for any edge endpoint IDs not present in nodes table.

        :param nodes: List of existing node metadata dictionaries.
        :param target_ids: Set of all node IDs referenced in edges or lineage traversals.
        :return: Updated nodes list with synthesized placeholder nodes added.
        """
        found_ids = {n["id"] for n in nodes}
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

    def get_full_graph(self, as_of: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves all graph nodes and edges as of optional ISO 8601 timestamp.

        Args:
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'nodes' list and 'edges' list.
        """
        con = duckdb.connect(database=":memory:")
        if not resolve_delta_or_parquet_table(con, self.nodes_dir, "nodes_view", as_of=as_of):
            return {"nodes": [], "edges": []}
        if not resolve_delta_or_parquet_table(con, self.edges_dir, "edges_view", as_of=as_of):
            return {"nodes": [], "edges": []}

        nodes_df = con.execute("SELECT id, FIRST(type) as type, FIRST(name) as name, FIRST(description) as description, FIRST(properties) as properties FROM nodes_view GROUP BY id").df()
        edges_df = con.execute("SELECT DISTINCT source_id, target_id, type, properties FROM edges_view").df()

        nodes = nodes_df.to_dict(orient="records")
        edges = edges_df.to_dict(orient="records")

        # Synthesize missing nodes referenced in edges so the graph is always complete
        referenced_ids = {e["source_id"] for e in edges} | {e["target_id"] for e in edges}
        nodes = self._synthesize_missing_nodes(nodes, referenced_ids)

        return {"nodes": nodes, "edges": edges}

    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5, as_of: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes recursive CTE traversal in DuckDB to compute downstream blast radius starting from `start_node_id`.

        :param start_node_id: Target node canonical ID.
        :param max_depth: Maximum recursive lineage traversal depth (1 to 10).
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: Traversal payload containing 'root_node', 'impacted_nodes', 'edges', and 'depth_reached'.
        """
        con = duckdb.connect(database=":memory:")
        if not resolve_delta_or_parquet_table(con, self.nodes_dir, "nodes_view", as_of=as_of):
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}
        if not resolve_delta_or_parquet_table(con, self.edges_dir, "edges_view", as_of=as_of):
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}

        query = f"""
        WITH RECURSIVE downstream_traverse(source_id, target_id, type, depth) AS (
            SELECT source_id, target_id, type, 1 AS depth
            FROM edges_view
            WHERE source_id = {_quote_id(start_node_id)}
            
            UNION ALL
            
            SELECT e.source_id, e.target_id, e.type, d.depth + 1
            FROM edges_view e
            JOIN downstream_traverse d ON e.source_id = d.target_id
            WHERE d.depth < {max_depth} AND e.type != 'BELONGS_TO'
        )
        SELECT DISTINCT source_id, target_id, type, depth
        FROM downstream_traverse;
        """

        edges_df = con.execute(query).df()
        edges = edges_df.to_dict(orient="records")

        impacted_node_ids = set()
        for e in edges:
            impacted_node_ids.add(e["source_id"])
            impacted_node_ids.add(e["target_id"])

        if not impacted_node_ids:
            impacted_node_ids.add(start_node_id)

        node_id_list_str = ", ".join(_quote_id(nid) for nid in impacted_node_ids)
        nodes_query = f"""
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE id IN ({node_id_list_str});
        """
        nodes_df = con.execute(nodes_query).df()
        nodes = nodes_df.to_dict(orient="records")

        nodes = self._synthesize_missing_nodes(nodes, impacted_node_ids)
        root_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "root_node": root_node,
            "impacted_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5, as_of: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Executes recursive CTE traversal in DuckDB to compute upstream root cause dependencies starting from `start_node_id`.

        :param start_node_id: Target node canonical ID.
        :param max_depth: Maximum recursive lineage traversal depth (1 to 10).
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: Traversal payload containing 'target_node', 'upstream_nodes', 'edges', and 'depth_reached'.
        """
        con = duckdb.connect(database=":memory:")
        if not resolve_delta_or_parquet_table(con, self.nodes_dir, "nodes_view", as_of=as_of):
            return {"upstream_nodes": [], "edges": [], "target_node": None, "depth_reached": 0}
        if not resolve_delta_or_parquet_table(con, self.edges_dir, "edges_view", as_of=as_of):
            return {"upstream_nodes": [], "edges": [], "target_node": None, "depth_reached": 0}

        query = f"""
        WITH RECURSIVE upstream_traverse(source_id, target_id, type, depth) AS (
            SELECT source_id, target_id, type, 1 AS depth
            FROM edges_view
            WHERE target_id = {_quote_id(start_node_id)} AND type != 'BELONGS_TO'
            
            UNION ALL
            
            SELECT e.source_id, e.target_id, e.type, u.depth + 1
            FROM edges_view e
            JOIN upstream_traverse u ON e.target_id = u.source_id
            WHERE u.depth < {max_depth} AND e.type != 'BELONGS_TO'
        )
        SELECT DISTINCT source_id, target_id, type, depth
        FROM upstream_traverse;
        """

        edges_df = con.execute(query).df()
        edges = edges_df.to_dict(orient="records")

        upstream_node_ids = set()
        for e in edges:
            upstream_node_ids.add(e["source_id"])
            upstream_node_ids.add(e["target_id"])

        if not upstream_node_ids:
            upstream_node_ids.add(start_node_id)

        node_id_list_str = ", ".join(_quote_id(nid) for nid in upstream_node_ids)
        nodes_query = f"""
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE id IN ({node_id_list_str});
        """
        nodes_df = con.execute(nodes_query).df()
        nodes = nodes_df.to_dict(orient="records")

        nodes = self._synthesize_missing_nodes(nodes, upstream_node_ids)
        target_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "target_node": target_node,
            "upstream_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def get_nodes_by_ids(
        self, node_ids: List[str], as_of: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves full node metadata records for a given list of node IDs.

        :param node_ids: List of canonical node identifiers.
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: List of matching node metadata dictionaries in requested order.
        """
        if not node_ids:
            return []

        con = duckdb.connect(database=":memory:")
        if not resolve_delta_or_parquet_table(con, self.nodes_dir, "nodes_view", as_of=as_of):
            return []

        v_ids_str = ", ".join(_quote_id(vid) for vid in node_ids)
        query = f"""
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE id IN ({v_ids_str});
        """
        results_df = con.execute(query).df()
        records = results_df.to_dict(orient="records")
        record_map = {r["id"]: r for r in records}
        return [record_map[vid] for vid in node_ids if vid in record_map]

    def search_nodes_by_terms(
        self, query_text: str, top_k: int = 5, as_of: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Searches node metadata fields (name, id, description, type, properties) using SQL LIKE clauses.

        :param query_text: User search query or keyword phrase.
        :param top_k: Maximum number of candidate node records to return.
        :param as_of: Optional ISO 8601 timestamp string for historical time travel.
        :return: List of matching node metadata dictionaries.
        """
        con = duckdb.connect(database=":memory:")
        if not resolve_delta_or_parquet_table(con, self.nodes_dir, "nodes_view", as_of=as_of):
            return []

        terms = extract_search_terms(query_text)
        where_clauses = []
        for t in terms:
            t_escaped = t.replace("'", "''")
            where_clauses.append(f"LOWER(name) LIKE '%{t_escaped}%'")
            where_clauses.append(f"LOWER(id) LIKE '%{t_escaped}%'")
            where_clauses.append(f"LOWER(COALESCE(description, '')) LIKE '%{t_escaped}%'")
            where_clauses.append(f"LOWER(type) LIKE '%{t_escaped}%'")
            where_clauses.append(f"LOWER(CAST(properties AS VARCHAR)) LIKE '%{t_escaped}%'")

        if not where_clauses:
            return []

        where_stmt = " OR ".join(where_clauses)
        query = f"""
        SELECT id, type, name, description, properties
        FROM nodes_view
        WHERE {where_stmt}
        LIMIT {top_k * 2};
        """
        results_df = con.execute(query).df()
        return results_df.to_dict(orient="records")

    def _get_scoped_node_ids(self, graph: Dict[str, Any], start_node_id: Optional[str], as_of: Optional[str] = None) -> set:
        """Helper to compute set of node IDs connected to start_node_id (upstream + downstream)."""
        nodes = graph.get("nodes", [])
        if not nodes or not start_node_id:
            return {n["id"] for n in nodes}

        clean_start = start_node_id.strip().lower()
        if not clean_start or clean_start in ["all", "enterprise", "global", "none"]:
            return {n["id"] for n in nodes}

        matched_target_ids = set()
        for n in nodes:
            nid = n.get("id", "").lower()
            name = n.get("name", "").lower()
            if clean_start == nid or clean_start == name or clean_start in nid or clean_start in name:
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
        self, start_node_id: Optional[str], timestamp_t1: str, timestamp_t2: str
    ) -> Dict[str, Any]:
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
                if n1.get("properties") != n2.get("properties") or n1.get("description") != n2.get("description"):
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
