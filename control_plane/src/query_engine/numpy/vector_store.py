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
from core.utils import parse_iso_to_epoch_ms

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
    """Pure NumPy-backed Vector Store executing vectorized cosine similarity.

    Reads vector tables from Delta Lake or Parquet, builds an in-memory normalized
    float32 matrix, and executes BLAS dot-product similarity searches with top-k filtering.

    Args:
        data_base_path: Root directory path or S3 URI where Delta Lake vector tables reside.
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

    def _resolve_target_version(self, dt: DeltaTable, as_of: str | None) -> tuple[int | None, bool]:
        """Resolves target version number and whether as_of precedes all history.

        Returns: (target_version, is_before_history)
        """
        if as_of is None:
            return None, False
        if isinstance(as_of, int) or (isinstance(as_of, str) and as_of.isdigit()):
            return int(as_of), False

        target_ms = parse_iso_to_epoch_ms(as_of)
        if target_ms is None:
            return None, False

        try:
            history = dt.history()
        except Exception:
            return None, False

        if not history:
            return None, False

        sorted_commits = sorted(history, key=lambda x: x.get("timestamp", 0))
        earliest_ms = sorted_commits[0].get("timestamp", 0)
        if target_ms + 100 < earliest_ms:
            return None, True

        target_ver = sorted_commits[0].get("version", 0)
        for commit in sorted_commits:
            commit_ms = commit.get("timestamp", 0)
            if commit_ms <= target_ms + 100:
                target_ver = commit.get("version", 0)
        return target_ver, False

    def _load_snapshot(self, as_of: str | None = None) -> _NumpyVectorSnapshot | None:
        with self._cache_lock:
            if as_of in self._snapshot_cache:
                return self._snapshot_cache[as_of]

            try:
                if os.path.exists(self.vectors_dir) and DeltaTable.is_deltatable(self.vectors_dir):
                    dt = DeltaTable(self.vectors_dir, storage_options=self.storage_options)
                    target_ver, is_before = self._resolve_target_version(dt, as_of)
                    if is_before:
                        return None
                    if target_ver is not None:
                        dt.load_as_version(target_ver)
                    tbl = dt.to_pyarrow_table()
                else:
                    parquet_file = os.path.join(self.vectors_dir, FILE_DATA_PARQUET)
                    if os.path.exists(parquet_file):
                        tbl = pa.parquet.read_table(parquet_file)
                    else:
                        return None

                node_map: dict[str, list[float]] = {}
                for row in tbl.to_pylist():
                    vec = row.get("vector")
                    nid = row.get("id")
                    if vec is not None and nid is not None:
                        node_map[nid] = vec

                if not node_map:
                    return None

                node_ids = list(node_map.keys())
                vectors_list = list(node_map.values())
                matrix = np.array(vectors_list, dtype=np.float32)
                snapshot = _NumpyVectorSnapshot(node_ids=node_ids, matrix=matrix)
                self._snapshot_cache[as_of] = snapshot
                return snapshot

            except Exception as e:
                logger.warning(f"NumpyVectorStore could not load vectors table at {self.vectors_dir}: {e}")
                return None

    def search_vectors(
        self,
        query_vector: list[float],
        top_k: int = 5,
        max_distance: float = 0.75,
        as_of: str | None = None,
    ) -> list[str]:
        """Searches vector index for nearest-neighbor vectors using BLAS cosine similarity."""
        snapshot = self._load_snapshot(as_of=as_of)
        if snapshot is None or len(snapshot.node_ids) == 0:
            return []

        q_arr = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_arr)
        if q_norm == 0.0:
            return []
        q_normed = q_arr / q_norm

        similarities = snapshot.matrix @ q_normed
        distances = 1.0 - similarities

        valid_mask = distances <= max_distance
        if not np.any(valid_mask):
            return []

        valid_indices = np.where(valid_mask)[0]
        valid_distances = distances[valid_indices]

        num_valid = len(valid_indices)
        k = min(top_k, num_valid)

        if k == num_valid:
            top_k_sub_idx = np.argsort(valid_distances)
        else:
            top_k_sub_idx = np.argpartition(valid_distances, k - 1)[:k]
            top_k_sub_idx = top_k_sub_idx[np.argsort(valid_distances[top_k_sub_idx])]

        best_indices = valid_indices[top_k_sub_idx]
        return snapshot.node_ids[best_indices].tolist()

    def get_in_memory_footprint_bytes(self) -> int:
        with self._cache_lock:
            return sum(snap.memory_footprint_bytes() for snap in self._snapshot_cache.values())
