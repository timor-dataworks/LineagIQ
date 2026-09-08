import os
import json
import re
from typing import Dict, Any, List
import duckdb
from control_plane.src.query_engine.base import BaseGraphStore

STOP_WORDS = {
    "find", "show", "search", "get", "list", "where", "is", "are", "the",
    "a", "an", "for", "with", "in", "me", "dataset", "datasets", "table",
    "tables", "column", "columns", "all", "what", "which", "who", "how", "tell", "about"
}


def extract_search_terms(query_text: str) -> List[str]:
    raw_clean = query_text.lower().strip()
    words = [w for w in re.split(r'\s+', raw_clean) if w]
    filtered_words = [w for w in words if w not in STOP_WORDS]

    terms = []
    if filtered_words:
        terms.append(" ".join(filtered_words))
        for w in filtered_words:
            if w not in terms:
                terms.append(w)
    if raw_clean not in terms:
        terms.append(raw_clean)

    return [t for t in terms if len(t) >= 2]


class DuckDBGraphStore(BaseGraphStore):
    """DuckDB & Parquet implementation of BaseGraphStore."""

    def __init__(self, data_base_path: str):
        self.base_path = data_base_path
        self.nodes_file = os.path.join(data_base_path, "graph", "nodes", "data.parquet")
        self.edges_file = os.path.join(data_base_path, "graph", "edges", "data.parquet")

    def get_full_graph(self) -> Dict[str, Any]:
        if not os.path.exists(self.nodes_file) or not os.path.exists(self.edges_file):
            return {"nodes": [], "edges": []}

        con = duckdb.connect(database=":memory:")
        nodes_df = con.execute(f"SELECT id, type, name, description, properties FROM read_parquet('{self.nodes_file}')").df()
        edges_df = con.execute(f"SELECT source_id, target_id, type, properties FROM read_parquet('{self.edges_file}')").df()

        nodes = nodes_df.to_dict(orient="records")
        edges = edges_df.to_dict(orient="records")

        # Synthesize missing nodes referenced in edges so the graph is always complete
        existing_ids = {n["id"] for n in nodes}
        for e in edges:
            for nid in [e["source_id"], e["target_id"]]:
                if nid not in existing_ids:
                    existing_ids.add(nid)
                    name = nid.split(".")[-1] if "." in nid else nid
                    ntype = "Dataset" if ("source" in nid or "raw" in nid or "db." in nid or "table" in nid) else "Pipeline"
                    nodes.append({
                        "id": nid,
                        "type": ntype,
                        "name": name,
                        "description": f"External Data Asset / Source ({nid})",
                        "properties": json.dumps({"source": "graph_edge"}),
                    })

        return {"nodes": nodes, "edges": edges}

    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        if not os.path.exists(self.nodes_file) or not os.path.exists(self.edges_file):
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}

        con = duckdb.connect(database=":memory:")

        query = f"""
        WITH RECURSIVE downstream_traverse(source_id, target_id, type, depth) AS (
            SELECT source_id, target_id, type, 1 AS depth
            FROM read_parquet('{self.edges_file}')
            WHERE source_id = '{start_node_id}'
            
            UNION ALL
            
            SELECT e.source_id, e.target_id, e.type, d.depth + 1
            FROM read_parquet('{self.edges_file}') e
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

        node_id_list_str = ", ".join(f"'{nid}'" for nid in impacted_node_ids)
        nodes_query = f"""
        SELECT id, type, name, description, properties
        FROM read_parquet('{self.nodes_file}')
        WHERE id IN ({node_id_list_str});
        """
        nodes_df = con.execute(nodes_query).df()
        nodes = nodes_df.to_dict(orient="records")

        found_ids = {n["id"] for n in nodes}
        for nid in impacted_node_ids:
            if nid not in found_ids:
                name = nid.split(".")[-1] if "." in nid else nid
                ntype = "Dataset" if ("source" in nid or "raw" in nid or "db." in nid or "table" in nid) else "Pipeline"
                nodes.append({
                    "id": nid,
                    "type": ntype,
                    "name": name,
                    "description": f"External Data Asset / Pipeline ({nid})",
                    "properties": json.dumps({"source": "lineage_traversal"}),
                })

        root_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "root_node": root_node,
            "impacted_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        if not os.path.exists(self.nodes_file) or not os.path.exists(self.edges_file):
            return {"upstream_nodes": [], "edges": [], "target_node": None, "depth_reached": 0}

        con = duckdb.connect(database=":memory:")

        query = f"""
        WITH RECURSIVE upstream_traverse(source_id, target_id, type, depth) AS (
            SELECT source_id, target_id, type, 1 AS depth
            FROM read_parquet('{self.edges_file}')
            WHERE target_id = '{start_node_id}' AND type != 'BELONGS_TO'
            
            UNION ALL
            
            SELECT e.source_id, e.target_id, e.type, u.depth + 1
            FROM read_parquet('{self.edges_file}') e
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

        node_id_list_str = ", ".join(f"'{nid}'" for nid in upstream_node_ids)
        nodes_query = f"""
        SELECT id, type, name, description, properties
        FROM read_parquet('{self.nodes_file}')
        WHERE id IN ({node_id_list_str});
        """
        nodes_df = con.execute(nodes_query).df()
        nodes = nodes_df.to_dict(orient="records")

        found_ids = {n["id"] for n in nodes}
        for nid in upstream_node_ids:
            if nid not in found_ids:
                name = nid.split(".")[-1] if "." in nid else nid
                ntype = "Dataset" if ("source" in nid or "raw" in nid or "db." in nid or "table" in nid) else "Pipeline"
                nodes.append({
                    "id": nid,
                    "type": ntype,
                    "name": name,
                    "description": f"External Data Asset / Source ({nid})",
                    "properties": json.dumps({"source": "lineage_traversal"}),
                })

        target_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "target_node": target_node,
            "upstream_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def get_nodes_by_ids(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        if not node_ids or not os.path.exists(self.nodes_file):
            return []

        con = duckdb.connect(database=":memory:")
        v_ids_str = ", ".join(f"'{vid}'" for vid in node_ids)
        query = f"""
        SELECT id, type, name, description, properties
        FROM read_parquet('{self.nodes_file}')
        WHERE id IN ({v_ids_str});
        """
        results_df = con.execute(query).df()
        records = results_df.to_dict(orient="records")
        record_map = {r["id"]: r for r in records}
        return [record_map[vid] for vid in node_ids if vid in record_map]

    def search_nodes_by_terms(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if not os.path.exists(self.nodes_file):
            return []

        terms = extract_search_terms(query_text)
        where_clauses = []
        for t in terms:
            t_escaped = t.replace("'", "''")
            where_clauses.append(f"LOWER(name) LIKE '%{t_escaped}%'")
            where_clauses.append(f"LOWER(COALESCE(description, '')) LIKE '%{t_escaped}%'")
            where_clauses.append(f"LOWER(type) LIKE '%{t_escaped}%'")
            where_clauses.append(f"LOWER(CAST(properties AS VARCHAR)) LIKE '%{t_escaped}%'")

        if not where_clauses:
            return []

        con = duckdb.connect(database=":memory:")
        where_stmt = " OR ".join(where_clauses)
        query = f"""
        SELECT id, type, name, description, properties
        FROM read_parquet('{self.nodes_file}')
        WHERE {where_stmt}
        LIMIT {top_k * 2};
        """
        results_df = con.execute(query).df()
        return results_df.to_dict(orient="records")
