"""LineagIQ Query Engine package.

Exposes pluggable graph, vector, and query engine abstractions along with DuckDB
and pure NumPy implementations and storage utilities.
"""

from control_plane.src.query_engine.base import (
    BaseGraphStore,
    BaseQueryEngine,
    BaseVectorStore,
)
from control_plane.src.query_engine.duckdb import (
    DuckDBGraphStore,
    DuckDBVectorStore,
    clear_duckdb_caches,
    configure_duckdb_s3,
    ensure_duckdb_extensions,
    get_available_timestamps,
    get_shared_duckdb_connection,
    get_shared_view_cache,
    resolve_delta_or_parquet_table,
    resolve_delta_table,
)
from control_plane.src.query_engine.engine import DuckDBQueryEngine, UnifiedQueryEngine
from control_plane.src.query_engine.numpy import (
    NumpyGraphStore,
    NumpyQueryEngine,
    NumpyVectorStore,
)
from core.utils import extract_search_terms

__all__ = [
    "BaseGraphStore",
    "BaseQueryEngine",
    "BaseVectorStore",
    "DuckDBGraphStore",
    "DuckDBQueryEngine",
    "DuckDBVectorStore",
    "NumpyGraphStore",
    "NumpyQueryEngine",
    "NumpyVectorStore",
    "UnifiedQueryEngine",
    "clear_duckdb_caches",
    "configure_duckdb_s3",
    "ensure_duckdb_extensions",
    "extract_search_terms",
    "get_available_timestamps",
    "get_shared_duckdb_connection",
    "get_shared_view_cache",
    "resolve_delta_or_parquet_table",
    "resolve_delta_table",
]
