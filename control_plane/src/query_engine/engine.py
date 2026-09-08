import json
from typing import Dict, Any, List, Optional
from collection_agent.src.embedder.local_embedder import LocalEmbedder
from control_plane.src.query_engine.base import BaseGraphStore, BaseVectorStore
from control_plane.src.query_engine.duckdb_store import DuckDBGraphStore
from control_plane.src.query_engine.duckdb_vector_store import DuckDBVectorStore


class DuckDBQueryEngine:
    """Unified Query Engine orchestrating pluggable graph storage (`BaseGraphStore`)
    and vector index search (`BaseVectorStore`).

    Provides high-level methods for downstream blast radius analysis, upstream root cause,
    full graph visualization, and hybrid (vector + BM25/term) semantic asset discovery.

    Args:
        data_base_path: Root directory path containing graph and vector Parquet data.
        graph_store: Optional custom `BaseGraphStore` instance. Defaults to `DuckDBGraphStore`.
        vector_store: Optional custom `BaseVectorStore` instance. Defaults to `DuckDBVectorStore`.
        embedder: Optional custom `LocalEmbedder` instance. Defaults to `LocalEmbedder`.
    """

    def __init__(
        self,
        data_base_path: str,
        graph_store: Optional[BaseGraphStore] = None,
        vector_store: Optional[BaseVectorStore] = None,
        embedder: Optional[LocalEmbedder] = None,
    ):
        self.base_path = data_base_path
        self.graph_store = graph_store or DuckDBGraphStore(data_base_path)
        self.vector_store = vector_store or DuckDBVectorStore(data_base_path)
        self.embedder = embedder or LocalEmbedder()

    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        """Calculates downstream blast radius starting from a target asset node.

        Args:
            start_node_id: Node ID of the asset under assessment.
            max_depth: Maximum lineage traversal depth. Defaults to 5.

        Returns:
            Dictionary containing 'root_node', 'impacted_nodes', 'edges', and 'depth_reached'.
        """
        return self.graph_store.get_downstream_blast_radius(start_node_id, max_depth)

    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        """Calculates upstream root cause lineage starting from a target asset node.

        Args:
            start_node_id: Node ID of the affected target asset.
            max_depth: Maximum lineage traversal depth. Defaults to 5.

        Returns:
            Dictionary containing 'target_node', 'upstream_nodes', 'edges', and 'depth_reached'.
        """
        return self.graph_store.get_upstream_root_cause(start_node_id, max_depth)

    def get_full_graph(self) -> Dict[str, Any]:
        """Retrieves all nodes and edges in the lineage knowledge graph.

        Returns:
            Dictionary containing list of 'nodes' and list of 'edges'.
        """
        return self.graph_store.get_full_graph()

    def search_semantic_assets(
        self, query_text: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Executes hybrid search combining term match search via `graph_store`
        and vector similarity search via `vector_store`.

        Automatically resolves parent dataset nodes for matched column attributes so that
        column search results provide complete contextual dataset metadata.

        Args:
            query_text: Natural language user query string.
            top_k: Maximum number of primary search matches to return per retrieval strategy.

        Returns:
            List of matching node dictionaries with resolved parent relationships, capped at top_k * 2.
        """
        query_vec = self.embedder.embed_text(query_text)
        vector_node_ids = self.vector_store.search_vectors(query_vec, top_k=top_k)

        matched_nodes: List[Dict[str, Any]] = []
        seen_ids = set()

        if vector_node_ids:
            vector_nodes = self.graph_store.get_nodes_by_ids(vector_node_ids)
            for v_node in vector_nodes:
                if v_node["id"] not in seen_ids:
                    seen_ids.add(v_node["id"])
                    matched_nodes.append(v_node)

        term_matched_nodes = self.graph_store.search_nodes_by_terms(query_text, top_k=top_k)
        for t_node in term_matched_nodes:
            if t_node["id"] not in seen_ids:
                seen_ids.add(t_node["id"])
                matched_nodes.append(t_node)

        # Automatically resolve parent dataset nodes for matched Column nodes
        node_ids = {n["id"] for n in matched_nodes}
        parent_dataset_ids = set()

        for n in matched_nodes:
            props = n.get("properties")
            if isinstance(props, str):
                try:
                    props = json.loads(props)
                except (json.JSONDecodeError, TypeError):
                    props = {}
            if isinstance(props, dict) and props.get("dataset_id"):
                ds_id = props["dataset_id"]
                if ds_id not in node_ids:
                    parent_dataset_ids.add(ds_id)

        if parent_dataset_ids:
            parent_nodes = self.graph_store.get_nodes_by_ids(list(parent_dataset_ids))
            for p_node in parent_nodes:
                if p_node["id"] not in seen_ids:
                    seen_ids.add(p_node["id"])
                    matched_nodes.append(p_node)

        return matched_nodes[: top_k * 2]

