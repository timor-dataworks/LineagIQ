import os
import glob
from typing import List
import duckdb
from control_plane.src.query_engine.base import BaseVectorStore


class DuckDBVectorStore(BaseVectorStore):
    """DuckDB VSS (Vector Similarity Search) implementation of BaseVectorStore over Parquet files."""

    def __init__(self, data_base_path: str):
        self.data_base_path = data_base_path

    def _resolve_parquet_file(self) -> str:
        # Check standard vectors/data.parquet location first
        standard_path = os.path.join(self.data_base_path, "vectors", "data.parquet")
        if os.path.exists(standard_path):
            return standard_path

        # Fallback to direct path or searching subdirectories
        if os.path.isfile(self.data_base_path) and self.data_base_path.endswith(".parquet"):
            return self.data_base_path

        parquet_files = glob.glob(os.path.join(self.data_base_path, "**", "*.parquet"), recursive=True)
        return parquet_files[0] if parquet_files else ""

    def search_vectors(self, query_vector: List[float], top_k: int = 5) -> List[str]:
        p_file = self._resolve_parquet_file()
        if not p_file or not os.path.exists(p_file):
            return []

        try:
            con = duckdb.connect(database=":memory:")
            try:
                con.execute("INSTALL vss; LOAD vss;")
            except Exception:
                pass  # Extension may already be loaded

            dim = len(query_vector)
            p_file_escaped = p_file.replace("'", "''")

            query = f"""
            SELECT id, array_cosine_distance(CAST(vector AS FLOAT[{dim}]), CAST(? AS FLOAT[{dim}])) AS distance
            FROM read_parquet('{p_file_escaped}')
            WHERE vector IS NOT NULL
            ORDER BY distance ASC
            LIMIT {top_k * 2};
            """

            results_df = con.execute(query, [query_vector]).df()
            records = results_df.to_dict(orient="records")

            node_ids = []
            for r in records:
                if isinstance(r, dict) and "id" in r and r["id"] not in node_ids:
                    node_ids.append(r["id"])
            return node_ids
        except Exception as e:
            print(f"DuckDB VSS vector store warning: {e}")

        return []

