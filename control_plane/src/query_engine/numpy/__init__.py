"""Pure NumPy-backed graph and vector storage implementations."""

from typing import Any

from control_plane.src.query_engine.engine import DuckDBQueryEngine
from control_plane.src.query_engine.numpy.graph_store import NumpyGraphStore
from control_plane.src.query_engine.numpy.vector_store import NumpyVectorStore
from core.embedder import LocalEmbedder, get_default_embedder


class NumpyQueryEngine(DuckDBQueryEngine):
    """Query Engine configured with pure NumPy CSR graph storage and vector search."""

    def __init__(
        self,
        data_base_path: str,
        graph_store: NumpyGraphStore | None = None,
        vector_store: NumpyVectorStore | None = None,
        embedder: LocalEmbedder | None = None,
        storage_options: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        g_store = graph_store or NumpyGraphStore(data_base_path, storage_options=storage_options)
        v_store = vector_store or NumpyVectorStore(data_base_path, storage_options=storage_options)
        super().__init__(
            data_base_path=data_base_path,
            graph_store=g_store,
            vector_store=v_store,
            embedder=embedder or get_default_embedder(),
        )


__all__ = [
    "NumpyGraphStore",
    "NumpyQueryEngine",
    "NumpyVectorStore",
]
