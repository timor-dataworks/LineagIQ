"""LineagIQ Core Package.

Shared domain models, vector embeddings, storage schemas, and path conventions
for the LineagIQ platform.
"""

from core.constants import (
    DEFAULT_EMBEDDING_DIM,
    FILE_DATA_PARQUET,
    PATH_GRAPH_EDGES,
    PATH_GRAPH_NODES,
    PATH_VECTORS,
    TABLE_EDGES,
    TABLE_NODES,
    TABLE_VECTORS,
    get_edges_table_path,
    get_nodes_table_path,
    get_vectors_table_path,
)
from core.embedder import (
    LocalEmbedder,
    get_default_embedder,
)
from core.graph_builder import (
    GraphBuilder,
)
from core.models import (
    BusinessTermNode,
    ColumnNode,
    DatasetNode,
    Edge,
    EdgeType,
    GraphPayload,
    Node,
    NodeType,
    PipelineNode,
    UserTeamNode,
)
from core.schemas import (
    EDGE_SCHEMA,
    NODE_SCHEMA,
    get_vector_schema,
)
from core.utils import (
    STOP_WORDS,
    extract_search_terms,
    parse_iso_to_epoch_ms,
)
from core.writer import (
    ArtifactWriter,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
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
