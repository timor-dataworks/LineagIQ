import os
from typing import List
from control_plane.src.query_engine.base import BaseVectorStore


class LanceDBVectorStore(BaseVectorStore):
    """LanceDB implementation of BaseVectorStore."""

    def __init__(self, vectors_dir: str):
        self.vectors_dir = vectors_dir

    def search_vectors(self, query_vector: List[float], top_k: int = 5) -> List[str]:
        if not os.path.exists(self.vectors_dir):
            return []

        try:
            import lancedb
            db = lancedb.connect(self.vectors_dir)
            tables = db.list_tables() if hasattr(db, "list_tables") else db.table_names()
            if "metadata" in tables:
                tbl = db.open_table("metadata")
                vector_results = tbl.search(query_vector).limit(top_k * 2).to_list()
                node_ids = []
                for r in vector_results:
                    if isinstance(r, dict) and "id" in r and r["id"] not in node_ids:
                        node_ids.append(r["id"])
                return node_ids
        except Exception as e:
            print(f"LanceDB vector store warning: {e}")

        return []
