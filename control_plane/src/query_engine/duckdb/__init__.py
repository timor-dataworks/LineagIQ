"""DuckDB-backed query engine storage implementations and connection utilities."""

from control_plane.src.query_engine.duckdb.connection import (
    clear_duckdb_caches,
    configure_duckdb_s3,
    ensure_duckdb_extensions,
    fetchall_dicts,
    get_shared_duckdb_connection,
    get_shared_view_cache,
    quote_id,
    resolve_iam_credentials,
)
from control_plane.src.query_engine.duckdb.delta import (
    get_available_timestamps,
    resolve_delta_or_parquet_table,
    resolve_delta_table,
)
from control_plane.src.query_engine.duckdb.graph_store import DuckDBGraphStore
from control_plane.src.query_engine.duckdb.vector_store import DuckDBVectorStore

__all__ = [
    "DuckDBGraphStore",
    "DuckDBVectorStore",
    "clear_duckdb_caches",
    "configure_duckdb_s3",
    "ensure_duckdb_extensions",
    "fetchall_dicts",
    "get_available_timestamps",
    "get_shared_duckdb_connection",
    "get_shared_view_cache",
    "quote_id",
    "resolve_delta_or_parquet_table",
    "resolve_delta_table",
    "resolve_iam_credentials",
]
