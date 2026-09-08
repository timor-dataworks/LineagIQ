import os
import json
from typing import Dict, Any, List, Optional
from collection_agent.src.embedder.local_embedder import LocalEmbedder
from control_plane.src.query_engine.base import BaseGraphStore, BaseVectorStore
from control_plane.src.query_engine.duckdb_store import DuckDBGraphStore
from control_plane.src.query_engine.duckdb_vector_store import DuckDBVectorStore


class DuckDBQueryEngine:
    """
    Unified Query Engine orchestrating pluggable graph storage (`BaseGraphStore`)
    and vector index search (`BaseVectorStore`).
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
        return self.graph_store.get_downstream_blast_radius(start_node_id, max_depth)

    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        return self.graph_store.get_upstream_root_cause(start_node_id, max_depth)

    def get_full_graph(self) -> Dict[str, Any]:
        return self.graph_store.get_full_graph()

    def search_semantic_assets(
        self, query_text: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Executes hybrid search combining term match search via `graph_store`
        and vector similarity search via `vector_store`, automatically resolving
        parent dataset nodes for matched column attributes.
        """
        query_vec = self.embedder.embed_text(query_text)
        vector_node_ids = self.vector_store.search_vectors(query_vec, top_k=top_k)

        matched_nodes = []
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
                except Exception:
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

        return matched_nodes[:top_k * 2]
