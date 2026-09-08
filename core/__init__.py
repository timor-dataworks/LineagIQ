"""LineagIQ Core Package.

Shared domain models, vector embeddings, storage schemas, and path conventions
for the LineagIQ platform.
"""

from core.models import (
    NodeType,
    EdgeType,
    Node,
    DatasetNode,
    ColumnNode,
    PipelineNode,
    UserTeamNode,
    BusinessTermNode,
    Edge,
    GraphPayload,
)

from core.constants import (
    TABLE_NODES,
    TABLE_EDGES,
    TABLE_VECTORS,
    PATH_GRAPH_NODES,
    PATH_GRAPH_EDGES,
    PATH_VECTORS,
    FILE_DATA_PARQUET,
    DEFAULT_EMBEDDING_DIM,
    get_nodes_table_path,
    get_edges_table_path,
    get_vectors_table_path,
)

from core.schemas import (
    NODE_SCHEMA,
    EDGE_SCHEMA,
    get_vector_schema,
)

from core.embedder import (
    LocalEmbedder,
    get_default_embedder,
)

from core.writer import (
    ArtifactWriter,
)

from core.graph_builder import (
    GraphBuilder,
)

from core.utils import (
    parse_iso_to_epoch_ms,
    extract_search_terms,
    STOP_WORDS,
)

__all__ = [
    # Models
    "NodeType",
    "EdgeType",
    "Node",
    "DatasetNode",
    "ColumnNode",
    "PipelineNode",
    "UserTeamNode",
    "BusinessTermNode",
    "Edge",
    "GraphPayload",
    # Constants
    "TABLE_NODES",
    "TABLE_EDGES",
    "TABLE_VECTORS",
    "PATH_GRAPH_NODES",
    "PATH_GRAPH_EDGES",
    "PATH_VECTORS",
    "FILE_DATA_PARQUET",
    "DEFAULT_EMBEDDING_DIM",
    "get_nodes_table_path",
    "get_edges_table_path",
    "get_vectors_table_path",
    # Schemas
    "NODE_SCHEMA",
    "EDGE_SCHEMA",
    "get_vector_schema",
    # Embedder
    "LocalEmbedder",
    "get_default_embedder",
    # Writer & Builder
    "ArtifactWriter",
    "GraphBuilder",
    # Utils
    "parse_iso_to_epoch_ms",
    "extract_search_terms",
    "STOP_WORDS",
]
