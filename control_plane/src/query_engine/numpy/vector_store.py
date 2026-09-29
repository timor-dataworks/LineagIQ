"""Pure NumPy Vector Similarity Search implementation of BaseVectorStore."""

import logging
import os
import threading
from typing import Any

import numpy as np
import pyarrow as pa
from deltalake import DeltaTable

from control_plane.src.query_engine.base import BaseVectorStore
from core.constants import FILE_DATA_PARQUET, get_vectors_table_path

logger = logging.getLogger(__name__)


class _NumpyVectorSnapshot:
    """In-memory dense vector matrix and node ID index."""

    def __init__(self, node_ids: list[str], matrix: np.ndarray) -> None:
        self.node_ids = np.array(node_ids)
        # Ensure L2 normalization for instant cosine similarity via dot product
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        self.matrix = (matrix / norms).astype(np.float32)

    def memory_footprint_bytes(self) -> int:
        return int(self.matrix.nbytes + self.node_ids.nbytes)


class NumpyVectorStore(BaseVectorStore):
    """Pure NumPy in-memory vector store implementing `BaseVectorStore`.

    Loads dense vector embeddings into contiguous float32 2D NumPy matrices.
    Executes vectorized BLAS dot product similarity calculations.

    Args:
        data_base_path: Base directory or file path or S3 URI where vector files are located.
        storage_options: Optional cloud storage backend configurations.
    """

    def __init__(
        self,
        data_base_path: str,
        storage_options: dict[str, Any] | None = None,
    ) -> None:
        self.data_base_path = data_base_path
        self.storage_options = storage_options or {}
        self.is_s3 = data_base_path.startswith("s3://")
        if self.is_s3:
            self.vectors_dir = f"{data_base_path.rstrip('/')}/vectors"
        else:
            self.vectors_dir = get_vectors_table_path(data_base_path)

        self._snapshot_cache: dict[str | None, _NumpyVectorSnapshot] = {}
        self._cache_lock = threading.Lock()

    def _load_snapshot(self, as_of: str | None = None) -> _NumpyVectorSnapshot | None:
        with self._cache_lock:
            if as_of in self._snapshot_cache:
                return self._snapshot_cache[as_of]

            node_ids: list[str] = []
            vectors_list: list[list[float]] = []

            try:
                if os.path.exists(self.vectors_dir) and DeltaTable.is_deltatable(self.vectors_dir):
                    dt = DeltaTable(self.vectors_dir, storage_options=self.storage_options)
                    if as_of:
                        dt.load_as_version(int(as_of) if as_of.isdigit() else as_of)
                    tbl = dt.to_pyarrow_table()
                else:
                    parquet_file = os.path.join(self.vectors_dir, FILE_DATA_PARQUET)
                    if os.path.exists(parquet_file):
                        tbl = pa.parquet.read_table(parquet_file)
                    else:
                        return None

                for row in tbl.to_pylist():
                    vec = row.get("vector")
                    nid = row.get("id")
                    if vec is not None and nid is not None:
                        node_ids.append(nid)
                        vectors_list.append(vec)

            except Exception as e:
                logger.warning(f"NumpyVectorStore could not load vectors table at {self.vectors_dir}: {e}")
                return None

            if not node_ids or not vectors_list:
                return None

            matrix = np.array(vectors_list, dtype=np.float32)
            snapshot = _NumpyVectorSnapshot(node_ids=node_ids, matrix=matrix)
            self._snapshot_cache[as_of] = snapshot
            return snapshot

    def search_vectors(
        self,
        query_vector: list[float],
        top_k: int = 5,
        max_distance: float = 0.75,
        as_of: str | None = None,
    ) -> list[str]:
        """Searches for top-k matching node IDs using NumPy dot-product cosine similarity.

        Args:
            query_vector: High-dimensional numerical vector representation of query.
            top_k: Maximum number of top matching node IDs to return. Defaults to 5.
            max_distance: Maximum threshold for cosine distance (default 0.75).
            as_of: Optional ISO 8601 timestamp string for historical time travel.

        Returns:
            List of matching unique node IDs ordered by increasing cosine distance.
        """
        if not query_vector:
            return []

        snapshot = self._load_snapshot(as_of=as_of)
        if not snapshot or len(snapshot.node_ids) == 0:
            return []

        q_arr = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_arr)
        if q_norm == 0.0:
            return []
        q_normed = q_arr / q_norm

        # Vectorized dot product (cosine similarity)
        sims = np.dot(snapshot.matrix, q_normed)
        # Cosine distance = 1.0 - cosine similarity
        distances = 1.0 - sims

        # Filter by max_distance
        valid_indices = np.where(distances <= float(max_distance))[0]
        if len(valid_indices) == 0:
            return []

        valid_distances = distances[valid_indices]
        k = min(int(top_k), len(valid_indices))

        if k < len(valid_indices):
            # Fast partial sort via argpartition
            top_partition = np.argpartition(valid_distances, k)[:k]
            sorted_order = top_partition[np.argsort(valid_distances[top_partition])]
        else:
            sorted_order = np.argsort(valid_distances)

        final_indices = valid_indices[sorted_order]
        matched_ids = snapshot.node_ids[final_indices]

        # Deduplicate while preserving order
        seen = set()
        result: list[str] = []
        for nid in matched_ids:
            if nid not in seen:
                seen.add(nid)
                result.append(str(nid))

        return result

    def get_in_memory_footprint_bytes(self) -> int:
        """Returns total memory allocated in NumPy matrices across cached snapshots."""
        with self._cache_lock:
            return sum(snap.memory_footprint_bytes() for snap in self._snapshot_cache.values())
