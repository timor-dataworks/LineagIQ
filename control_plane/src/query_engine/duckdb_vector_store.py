"""DuckDB vector store module (backward-compatibility facade).

Re-exports DuckDBVectorStore from `query_engine.duckdb.vector_store`.
"""

from control_plane.src.query_engine.duckdb.vector_store import DuckDBVectorStore

__all__ = ["DuckDBVectorStore"]
