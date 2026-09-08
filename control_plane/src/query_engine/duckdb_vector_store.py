import os
import glob
import logging
from typing import List
import duckdb
from control_plane.src.query_engine.base import BaseVectorStore

logger = logging.getLogger(__name__)


class DuckDBVectorStore(BaseVectorStore):
    """DuckDB VSS (Vector Similarity Search) implementation of BaseVectorStore over Parquet files.

    Performs cosine-distance vector similarity queries on embeddings stored in Parquet datasets.

    Args:
        data_base_path: Base directory or file path where vector parquet files are located.
    """

    def __init__(self, data_base_path: str):
        self.data_base_path = data_base_path

    def _resolve_parquet_file(self) -> str:
        """Resolves the target vector Parquet file location.

        Checks standard 'vectors/data.parquet' location first, then direct file paths,
        and finally recursively glob searches subdirectories for '.parquet' files.

        Returns:
            Absolute path to the resolved vector Parquet file, or an empty string if none found.
        """
        # Check standard vectors/data.parquet location first
        standard_path = os.path.join(self.data_base_path, "vectors", "data.parquet")
        if os.path.exists(standard_path):
            return standard_path

        # Fallback to direct file path
        if os.path.isfile(self.data_base_path) and self.data_base_path.endswith(".parquet"):
            return self.data_base_path

        # Recursive search for parquet files in directory tree
        parquet_files = glob.glob(os.path.join(self.data_base_path, "**", "*.parquet"), recursive=True)
        return parquet_files[0] if parquet_files else ""

    def search_vectors(
        self, query_vector: List[float], top_k: int = 5, max_distance: float = 0.75
    ) -> List[str]:
        """Searches for top-k matching node IDs using DuckDB array_cosine_distance.

        Args:
            query_vector: High-dimensional numerical vector representation of query.
            top_k: Maximum number of top matching node IDs to return. Defaults to 5.
            max_distance: Maximum threshold for cosine distance (0.0 = identical, 1.0 = orthogonal).
                Defaults to 0.75 to filter out irrelevant candidates.

        Returns:
            List of matching unique node IDs ordered by increasing cosine distance.
        """
        p_file = self._resolve_parquet_file()
        if not p_file or not os.path.exists(p_file):
            return []

        try:
            con = duckdb.connect(database=":memory:")
            try:
                con.execute("INSTALL vss; LOAD vss;")
            except Exception:
                # Extension may already be loaded in DuckDB build
                pass

            dim = len(query_vector)
            p_file_escaped = p_file.replace("'", "''")

            query = f"""
            SELECT id, array_cosine_distance(CAST(vector AS FLOAT[{dim}]), CAST(? AS FLOAT[{dim}])) AS distance
            FROM read_parquet('{p_file_escaped}')
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


