import os
import glob
import logging
from typing import List, Optional
import duckdb
from control_plane.src.query_engine.base import BaseVectorStore
from control_plane.src.query_engine.duckdb_store import (
    resolve_delta_or_parquet_table,
    ensure_duckdb_extensions,
    configure_duckdb_s3,
)
from core.constants import get_vectors_table_path

logger = logging.getLogger(__name__)


class DuckDBVectorStore(BaseVectorStore):
    """DuckDB VSS (Vector Similarity Search) implementation of BaseVectorStore over Parquet/Delta files.

    Performs cosine-distance vector similarity queries on embeddings stored in Parquet/Delta datasets.

    Args:
        data_base_path: Base directory or file path or s3:// URI where vector parquet/delta files are located.
        storage_options: Optional remote storage backend options (e.g. S3 credentials / endpoint).
    """

    def __init__(self, data_base_path: str, storage_options: Optional[dict] = None):
        self.data_base_path = data_base_path
        self.storage_options = storage_options
        if data_base_path.startswith("s3://"):
            self.vectors_dir = f"{data_base_path.rstrip('/')}/vectors"
        else:
            self.vectors_dir = get_vectors_table_path(data_base_path)

        # Persistent DuckDB connection with pre-loaded extensions and S3 secrets
        self.con = duckdb.connect(database=":memory:")
        self._registered_views = {}
        ensure_duckdb_extensions(self.con)
        try:
            self.con.execute("INSTALL vss; LOAD vss;")
        except Exception as e:
            logger.debug(f"DuckDB VSS extension load notice: {e}")
        if self.storage_options:
            configure_duckdb_s3(self.con, self.storage_options)

    def search_vectors(
        self,
        query_vector: List[float],
        top_k: int = 5,
        max_distance: float = 0.75,
        as_of: Optional[str] = None,
    ) -> List[str]:
        """Searches for top-k matching node IDs using DuckDB array_cosine_distance as of timestamp.

        Args:
            query_vector: High-dimensional numerical vector representation of query.
            top_k: Maximum number of top matching node IDs to return. Defaults to 5.
            max_distance: Maximum threshold for cosine distance (0.0 = identical, 1.0 = orthogonal).
                Defaults to 0.75 to filter out irrelevant candidates.
            as_of: Optional ISO 8601 timestamp string for historical time travel vector search.

        Returns:
            List of matching unique node IDs ordered by increasing cosine distance.
        """
        if not query_vector:
            return []

        try:
            con = self.con
            if not resolve_delta_or_parquet_table(
                con,
                self.vectors_dir,
                "vectors_view",
                as_of=as_of,
                storage_options=self.storage_options,
                view_cache=self._registered_views,
            ):
                return []

            dim = len(query_vector)

            query = f"""
            SELECT id, array_cosine_distance(CAST(vector AS FLOAT[{dim}]), CAST(? AS FLOAT[{dim}])) AS distance
            FROM vectors_view
            WHERE vector IS NOT NULL AND array_cosine_distance(CAST(vector AS FLOAT[{dim}]), CAST(? AS FLOAT[{dim}])) <= {float(max_distance)}
            ORDER BY distance ASC
            LIMIT {int(top_k)};
            """

            rows = con.execute(query, [query_vector, query_vector]).fetchall()
            seen = set()
            node_ids: List[str] = []
            for row in rows:
                nid = row[0]
                if nid and nid not in seen:
                    seen.add(nid)
                    node_ids.append(nid)
            return node_ids
        except Exception as e:
            logger.warning(f"DuckDB VSS vector store warning: {e}")

        return []



