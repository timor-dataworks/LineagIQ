"""LineagIQ Query Engine package.

Exposes pluggable graph and vector storage abstractions along with DuckDB implementations
and the unified query engine.
"""

from control_plane.src.query_engine.base import BaseGraphStore, BaseVectorStore
from control_plane.src.query_engine.duckdb_store import DuckDBGraphStore, extract_search_terms
from control_plane.src.query_engine.duckdb_vector_store import DuckDBVectorStore
from control_plane.src.query_engine.engine import DuckDBQueryEngine

__all__ = [
    "BaseGraphStore",
    "BaseVectorStore",
    "DuckDBGraphStore",
    "DuckDBVectorStore",
    "DuckDBQueryEngine",
    "extract_search_terms",
]


