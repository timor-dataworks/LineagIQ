from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseGraphStore(ABC):
    """Abstract interface for graph storage engines (DuckDB, Postgres, Neo4j, etc.)."""

    @abstractmethod
    def get_full_graph(self) -> Dict[str, Any]:
        """Returns all nodes and edges in the graph."""
        pass

    @abstractmethod
    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        """Computes downstream blast radius starting from `start_node_id`."""
        pass

    @abstractmethod
    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5
    ) -> Dict[str, Any]:
        """Computes upstream root cause dependencies starting from `start_node_id`."""
        pass

    @abstractmethod
    def get_nodes_by_ids(self, node_ids: List[str]) -> List[Dict[str, Any]]:
        """Retrieves node metadata records for a list of node IDs."""
        pass

    @abstractmethod
    def search_nodes_by_terms(self, query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Searches node metadata via keyword / property search."""
        pass


class BaseVectorStore(ABC):
    """Abstract interface for vector index search engines (LanceDB, Qdrant, Pinecone, etc.)."""

    @abstractmethod
    def search_vectors(self, query_vector: List[float], top_k: int = 5) -> List[str]:
        """Searches vector index and returns list of matching node IDs."""
        pass
