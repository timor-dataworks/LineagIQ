"""Facade module exporting query engine instances."""

from control_plane.src.query_engine.numpy.engine import NumpyQueryEngine

# Unified Query Engine aliases
QueryEngine = NumpyQueryEngine
UnifiedQueryEngine = QueryEngine

__all__ = [
    "NumpyQueryEngine",
    "QueryEngine",
    "UnifiedQueryEngine",
]
