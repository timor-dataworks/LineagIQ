"""LineagIQ Core Storage & Path Constants.

Defines standardized dataset table names, directory paths, and path resolution helpers
shared across ingestion writers, DuckDB query engines, and cloud sync utilities.
"""

import os

# Table Identifiers
TABLE_NODES = "nodes"
TABLE_EDGES = "edges"
TABLE_VECTORS = "vectors"

# Default Storage Subdirectory Paths
PATH_GRAPH_NODES = os.path.join("graph", "nodes")
PATH_GRAPH_EDGES = os.path.join("graph", "edges")
PATH_VECTORS = "vectors"

# Standard File Names
FILE_DATA_PARQUET = "data.parquet"
FILE_NODES_PARQUET = "nodes.parquet"
FILE_EDGES_PARQUET = "edges.parquet"
FILE_VECTORS_PARQUET = "vectors.parquet"

# Default Embedding Dimension
DEFAULT_EMBEDDING_DIM = 384


def get_nodes_table_path(base_dir: str) -> str:
    """Returns the standardized directory path for graph nodes dataset.

    Args:
        base_dir: Base directory path for tenant data.

    Returns:
        Absolute or relative path to the nodes dataset directory.
    """
    return os.path.join(base_dir, PATH_GRAPH_NODES)


def get_edges_table_path(base_dir: str) -> str:
    """Returns the standardized directory path for graph edges dataset.

    Args:
        base_dir: Base directory path for tenant data.

    Returns:
        Absolute or relative path to the edges dataset directory.
    """
    return os.path.join(base_dir, PATH_GRAPH_EDGES)


def get_vectors_table_path(base_dir: str) -> str:
    """Returns the standardized directory path for vector embeddings dataset.

    Args:
        base_dir: Base directory path for tenant data.

    Returns:
        Absolute or relative path to the vectors dataset directory.
    """
    return os.path.join(base_dir, PATH_VECTORS)
