from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseGraphStore(ABC):
    """
    Abstract Base Class defining the pluggable interface for Graph Storage Engines.

    Implementations (e.g., `DuckDBGraphStore`, Postgres, Neo4j) handle graph traversal,
    downstream blast radius analysis, upstream root cause discovery, and metadata queries.
    """

    @abstractmethod
    def get_full_graph(self) -> Dict[str, Any]:
        """
        Retrieves all graph nodes and lineage edges.

        :return: Dictionary containing 'nodes' list and 'edges' list.
        """
        pass

    @abstractmethod
    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Computes the downstream blast radius traversal starting from a target node.

        :param start_node_id: Canonical target node identifier.
        :param max_depth: Maximum recursive traversal depth.
        :return: Dictionary containing 'root_node', 'impacted_nodes', 'edges', and 'depth_reached'.
        """
        pass

    @abstractmethod
    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        """
        Computes the upstream root cause traversal starting from a target node.

        :param start_node_id: Canonical target node identifier.
        :param max_depth: Maximum recursive traversal depth.
        :return: Dictionary containing 'target_node', 'upstream_nodes', 'edges', and 'depth_reached'.
        """
        pass

    @abstractmethod
    def get_nodes_by_ids(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Retrieves full node metadata records for a given list of node IDs.

        :param node_ids: List of canonical node identifiers.
        :return: List of matching node metadata dictionaries in requested order.
        """
        pass

    @abstractmethod
    def search_nodes_by_terms(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Searches graph node metadata fields (name, id, description, properties) for matching keywords.

        :param query_text: User search query or keyword terms.
        :param top_k: Maximum number of candidate node records to return.
        :return: List of matching node metadata dictionaries.
        """
        pass


class BaseVectorStore(ABC):
    """
    Abstract Base Class defining the pluggable interface for Vector Similarity Search Engines.

    Implementations (e.g., `DuckDBVectorStore`, Qdrant, Pinecone) execute nearest-neighbor vector search.
    """

    @abstractmethod
    def search_vectors(
        self, query_vector: List[float], top_k: int = 5, max_distance: float = 0.75
    ) -> List[str]:
        """
        Searches the vector index for nearest-neighbor vectors satisfying a maximum distance threshold.

        :param query_vector: L2-normalized 384-dimensional query vector.
        :param top_k: Maximum number of nearest-neighbor node IDs to return.
        :param max_distance: Maximum cosine distance threshold (default 0.75).
        :return: List of matching node IDs ordered by cosine distance ascending.
        """
        pass
