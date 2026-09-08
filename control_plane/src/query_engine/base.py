from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class BaseGraphStore(ABC):
    """Abstract Base Class defining the pluggable interface for Graph Storage Engines.

    Implementations (e.g., `DuckDBGraphStore`, Postgres, Neo4j) handle graph traversal,
    downstream blast radius analysis, upstream root cause discovery, metadata queries,
    and historical time-travel snapshot analysis.
    """

    @abstractmethod
    def get_full_graph(self, as_of: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves all graph nodes and lineage edges as of optional ISO 8601 timestamp.

        Args:
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'nodes' list and 'edges' list.
        """
        pass

    @abstractmethod
    def get_downstream_blast_radius(
        self, start_node_id: str, max_depth: int = 5, as_of: Optional[str] = None
    ) -> Dict[str, Any]:
        """Computes the downstream blast radius traversal starting from a target node.

        Args:
            start_node_id: Canonical target node identifier.
            max_depth: Maximum recursive traversal depth. Defaults to 5.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'root_node', 'impacted_nodes', 'edges', and 'depth_reached'.
        """
        pass

    @abstractmethod
    def get_upstream_root_cause(
        self, start_node_id: str, max_depth: int = 5, as_of: Optional[str] = None
    ) -> Dict[str, Any]:
        """Computes the upstream root cause traversal starting from a target node.

        Args:
            start_node_id: Canonical target node identifier.
            max_depth: Maximum recursive traversal depth. Defaults to 5.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            Dictionary containing 'target_node', 'upstream_nodes', 'edges', and 'depth_reached'.
        """
        pass

    @abstractmethod
    def get_nodes_by_ids(
        self, node_ids: List[str], as_of: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieves full node metadata records for a given list of node IDs.

        Args:
            node_ids: List of canonical node identifiers.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            List of matching node metadata dictionaries in requested order.
        """
        pass

    @abstractmethod
    def search_nodes_by_terms(
        self, query_text: str, top_k: int = 5, as_of: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches graph node metadata fields (name, id, description, properties) for matching keywords.

        Args:
            query_text: User search query or keyword terms.
            top_k: Maximum number of candidate node records to return.
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            List of matching node metadata dictionaries.
        """
        pass

    @abstractmethod
    def get_schema_time_travel_diff(
        self, start_node_id: str, timestamp_t1: str, timestamp_t2: str
    ) -> Dict[str, Any]:
        """Computes schema and lineage graph diff between two historical ISO 8601 timestamps.

        Args:
            start_node_id: Canonical asset identifier to scope diff assessment.
            timestamp_t1: Initial ISO 8601 timestamp string.
            timestamp_t2: Subsequent ISO 8601 timestamp string.

        Returns:
            Dictionary containing added_nodes, removed_nodes, modified_properties, and edge_changes.
        """
        pass


class BaseVectorStore(ABC):
    """Abstract Base Class defining the pluggable interface for Vector Similarity Search Engines.

    Implementations (e.g., `DuckDBVectorStore`, Qdrant, Pinecone) execute nearest-neighbor vector search.
    """

    @abstractmethod
    def search_vectors(
        self,
        query_vector: List[float],
        top_k: int = 5,
        max_distance: float = 0.75,
        as_of: Optional[str] = None,
    ) -> List[str]:
        """Searches the vector index for nearest-neighbor vectors satisfying a maximum distance threshold.

        Args:
            query_vector: L2-normalized 384-dimensional query vector.
            top_k: Maximum number of nearest-neighbor node IDs to return.
            max_distance: Maximum cosine distance threshold (default 0.75).
            as_of: Optional ISO 8601 timestamp string for historical time travel vector search.

        Returns:
            List of matching node IDs ordered by cosine distance ascending.
        """
        pass

