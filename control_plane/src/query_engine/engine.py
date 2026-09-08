import json
from typing import Dict, Any, List, Optional
from collection_agent.src.embedder.local_embedder import LocalEmbedder
from control_plane.src.query_engine.base import BaseGraphStore, BaseVectorStore
from control_plane.src.query_engine.duckdb_store import DuckDBGraphStore, get_available_timestamps
from control_plane.src.query_engine.duckdb_vector_store import DuckDBVectorStore


class DuckDBQueryEngine:
    """Unified Query Engine orchestrating pluggable graph storage (`BaseGraphStore`)
    and vector index search (`BaseVectorStore`).

    Provides high-level methods for downstream blast radius analysis, upstream root cause,
    full graph visualization, hybrid (vector + BM25/term) semantic asset discovery,
    and historical Delta Lake time-travel analysis.

    Args:
        data_base_path: Root directory path containing graph and vector Parquet/Delta data.
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
        self, start_node_id: str, max_depth: int = 5, as_of: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculates downstream blast radius starting from a target asset node.

        Args:
            start_node_id: Node ID of the asset under assessment.
            max_depth: Maximum lineage traversal depth. Defaults to 5.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'root_node', 'impacted_nodes', 'edges', and 'depth_reached'.
        """
        return self.graph_store.get_downstream_blast_radius(start_node_id, max_depth, as_of=as_of)

    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5, as_of: Optional[str] = None
    ) -> Dict[str, Any]:
        """Calculates upstream root cause lineage starting from a target asset node.

        Args:
            start_node_id: Node ID of the affected target asset.
            max_depth: Maximum lineage traversal depth. Defaults to 5.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'target_node', 'upstream_nodes', 'edges', and 'depth_reached'.
        """
        return self.graph_store.get_upstream_root_cause(start_node_id, max_depth, as_of=as_of)

    def get_full_graph(self, as_of: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves all nodes and edges in the lineage knowledge graph as of timestamp.

        Args:
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing list of 'nodes' and list of 'edges'.
        """
        return self.graph_store.get_full_graph(as_of=as_of)

    def get_available_timestamps(self) -> List[Dict[str, Any]]:
        """Retrieves commit history timestamps from tenant Delta Lake table logs.

        Returns:
            List of dictionaries with 'version', 'timestamp', and 'operation'.
        """
        return get_available_timestamps(self.base_path)

    def get_schema_time_travel_diff(
        self, start_node_id: str, timestamp_t1: str, timestamp_t2: str
    ) -> Dict[str, Any]:
        """Computes schema and lineage graph diff between two historical ISO 8601 timestamps.

        Args:
            start_node_id: Canonical asset identifier to scope diff assessment.
            timestamp_t1: Initial ISO 8601 timestamp string.
            timestamp_t2: Subsequent ISO 8601 timestamp string.

        Returns:
            Dictionary containing added_nodes, removed_nodes, modified_nodes, and edge_changes.
        """
        return self.graph_store.get_schema_time_travel_diff(start_node_id, timestamp_t1, timestamp_t2)

    def search_semantic_assets(
        self, query_text: str, top_k: int = 5, as_of: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Executes hybrid search combining term match search via `graph_store`
        and vector similarity search via `vector_store`.

        Automatically resolves parent dataset nodes for matched column attributes so that
        column search results provide complete contextual dataset metadata.

        Args:
            query_text: Natural language user query string.
            top_k: Maximum number of primary search matches to return per retrieval strategy.
            as_of: Optional ISO 8601 timestamp string for historical vector/graph search.

        Returns:
            List of matching node dictionaries with resolved parent relationships, capped at top_k * 2.
        """
        query_vec = self.embedder.embed_text(query_text)
        vector_node_ids = self.vector_store.search_vectors(query_vec, top_k=top_k, as_of=as_of)

        matched_nodes: List[Dict[str, Any]] = []
        seen_ids = set()

        if vector_node_ids:
            vector_nodes = self.graph_store.get_nodes_by_ids(vector_node_ids, as_of=as_of)
            for v_node in vector_nodes:
                if v_node["id"] not in seen_ids:
                    seen_ids.add(v_node["id"])
                    matched_nodes.append(v_node)

        term_matched_nodes = self.graph_store.search_nodes_by_terms(query_text, top_k=top_k, as_of=as_of)
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
            parent_nodes = self.graph_store.get_nodes_by_ids(list(parent_dataset_ids), as_of=as_of)
            for p_node in parent_nodes:
                if p_node["id"] not in seen_ids:
                    seen_ids.add(p_node["id"])
                    matched_nodes.append(p_node)

        return matched_nodes[: top_k * 2]


