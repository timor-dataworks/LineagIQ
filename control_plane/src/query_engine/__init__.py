"""Modular Query Engine package for LineagIQ Control Plane.

Provides abstract base interfaces and high-performance pure NumPy & Delta Lake implementations
for graph lineage traversal, semantic vector similarity, and time-travel analysis.
"""

from control_plane.src.query_engine.base import (
    BaseGraphStore,
    BaseQueryEngine,
    BaseVectorStore,
)
from control_plane.src.query_engine.engine import (
    NumpyQueryEngine,
    QueryEngine,
    UnifiedQueryEngine,
)
from control_plane.src.query_engine.numpy.graph_store import NumpyGraphStore
from control_plane.src.query_engine.numpy.vector_store import NumpyVectorStore

__all__ = [
    "BaseGraphStore",
    "BaseQueryEngine",
    "BaseVectorStore",
    "NumpyGraphStore",
    "NumpyQueryEngine",
    "NumpyVectorStore",
    "QueryEngine",
    "UnifiedQueryEngine",
]
