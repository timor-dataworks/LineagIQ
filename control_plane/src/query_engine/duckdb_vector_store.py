import os
import glob
import logging
from typing import List, Optional
import duckdb
from control_plane.src.query_engine.base import BaseVectorStore
from control_plane.src.query_engine.duckdb_store import resolve_delta_or_parquet_table
from core.constants import get_vectors_table_path

logger = logging.getLogger(__name__)


class DuckDBVectorStore(BaseVectorStore):
    """DuckDB VSS (Vector Similarity Search) implementation of BaseVectorStore over Parquet/Delta files.

    Performs cosine-distance vector similarity queries on embeddings stored in Parquet/Delta datasets.

    Args:
        data_base_path: Base directory or file path where vector parquet/delta files are located.
    """

    def __init__(self, data_base_path: str):
        self.data_base_path = data_base_path
        self.vectors_dir = get_vectors_table_path(data_base_path)

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
        try:
            con = duckdb.connect(database=":memory:")
            try:
                con.execute("INSTALL vss; LOAD vss;")
            except Exception:
                pass

            if not resolve_delta_or_parquet_table(con, self.vectors_dir, "vectors_view", as_of=as_of):
                return []

            dim = len(query_vector)

            query = f"""
            SELECT id, array_cosine_distance(CAST(vector AS FLOAT[{dim}]), CAST(? AS FLOAT[{dim}])) AS distance
            FROM vectors_view
            WHERE vector IS NOT NULL AND array_cosine_distance(CAST(vector AS FLOAT[{dim}]), CAST(? AS FLOAT[{dim}])) <= {max_distance}
            ORDER BY distance ASC
            LIMIT {top_k};
            """

            results_df = con.execute(query, [query_vector, query_vector]).df()
            records = results_df.to_dict(orient="records")

            node_ids: List[str] = []
            for r in records:
                if isinstance(r, dict) and "id" in r and r["id"] not in node_ids:
                    node_ids.append(r["id"])
            return node_ids
        except Exception as e:
            logger.warning(f"DuckDB VSS vector store warning: {e}")

        return []



