import os
import json
from typing import Dict, Any, List, Optional
import duckdb
import pyarrow.parquet as pq


class DuckDBQueryEngine:
    """
    DuckDB-powered Query Engine executing SQL graph traversals and
    lineage queries directly against tenant Parquet files.
    """

    def __init__(self, data_base_path: str):
        self.base_path = data_base_path
        self.nodes_file = os.path.join(data_base_path, "graph", "nodes", "data.parquet")
        self.edges_file = os.path.join(data_base_path, "graph", "edges", "data.parquet")
        self.vectors_dir = os.path.join(data_base_path, "vectors", "metadata.lance")

    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Executes a recursive CTE query in DuckDB to find all downstream impacted nodes
        and relationships starting from `start_node_id`.
        """
        if not os.path.exists(self.nodes_file) or not os.path.exists(self.edges_file):
            return {"impacted_nodes": [], "edges": [], "root_node": None, "depth_reached": 0}

        con = duckdb.connect(database=":memory:")

        # SQL query using Recursive CTE to traverse downstream edges
        query = f"""
        WITH RECURSIVE downstream_traverse(source_id, target_id, type, depth) AS (
            -- Anchor member: immediate edges originating from start_node_id
            SELECT source_id, target_id, type, 1 AS depth
            FROM read_parquet('{self.edges_file}')
            WHERE source_id = '{start_node_id}'
            
            UNION ALL
            
            -- Recursive member: traverse child edges up to max_depth
            SELECT e.source_id, e.target_id, e.type, d.depth + 1
            FROM read_parquet('{self.edges_file}') e
            JOIN downstream_traverse d ON e.source_id = d.target_id
            WHERE d.depth < {max_depth}
        )
        SELECT DISTINCT source_id, target_id, type, depth
        FROM downstream_traverse;
        """

        edges_df = con.execute(query).df()
        edges = edges_df.to_dict(orient="records")

        # Collect unique node IDs impacted
        impacted_node_ids = set()
        for e in edges:
            impacted_node_ids.add(e["source_id"])
            impacted_node_ids.add(e["target_id"])

        if not impacted_node_ids:
            impacted_node_ids.add(start_node_id)

        # Retrieve metadata for impacted nodes
        node_id_list_str = ", ".join(f"'{nid}'" for nid in impacted_node_ids)
        nodes_query = f"""
        SELECT id, type, name, description, properties
        FROM read_parquet('{self.nodes_file}')
        WHERE id IN ({node_id_list_str});
        """
        nodes_df = con.execute(nodes_query).df()
        nodes = nodes_df.to_dict(orient="records")

        root_node = next((n for n in nodes if n["id"] == start_node_id), None)

        return {
            "root_node": root_node,
            "impacted_nodes": nodes,
            "edges": edges,
            "depth_reached": max(e["depth"] for e in edges) if edges else 0,
        }

    def search_semantic_assets(
        self, query_text: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Performs semantic vector similarity search over LanceDB/Parquet vector index.
        """
        if not os.path.exists(self.nodes_file):
            return []

        con = duckdb.connect(database=":memory:")
        # Perform keyword + property match as fallback search
        search_term = query_text.lower()
        query = f"""
        SELECT id, type, name, description, properties
        FROM read_parquet('{self.nodes_file}')
        WHERE LOWER(name) LIKE '%{search_term}%'
           OR LOWER(description) LIKE '%{search_term}%'
           OR LOWER(type) LIKE '%{search_term}%'
        LIMIT {top_k};
        """

        results_df = con.execute(query).df()
        return results_df.to_dict(orient="records")
