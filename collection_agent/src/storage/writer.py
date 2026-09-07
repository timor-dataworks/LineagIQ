import os
import json
from pathlib import Path
from typing import Dict, Any, List
import pyarrow as pa
import pyarrow.parquet as pq
from collection_agent.src.transform.models import GraphPayload


class ArtifactWriter:
    """
    Artifact Writer serializes normalized GraphPayload data into Parquet
    columnar files and LanceDB vector table formats.
    """

    def write_nodes_parquet(self, payload: GraphPayload, output_file: str) -> str:
        """Serializes GraphPayload nodes into a Snappy-compressed Parquet file."""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        node_records = []
        for n in payload.nodes:
            node_records.append({
                "id": n.id,
                "type": n.type.value,
                "name": n.name,
                "description": n.description or "",
                "properties": json.dumps(n.properties),
            })

        schema = pa.schema([
            ("id", pa.string()),
            ("type", pa.string()),
            ("name", pa.string()),
            ("description", pa.string()),
            ("properties", pa.string()),
        ])

        table = pa.Table.from_pylist(node_records, schema=schema)
        pq.write_table(table, output_file, compression="snappy")
        return output_file

    def write_edges_parquet(self, payload: GraphPayload, output_file: str) -> str:
        """Serializes GraphPayload edges into a Snappy-compressed Parquet file."""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        edge_records = []
        for e in payload.edges:
            edge_records.append({
                "source_id": e.source_id,
                "target_id": e.target_id,
                "type": e.type.value,
                "properties": json.dumps(e.properties),
            })

        schema = pa.schema([
            ("source_id", pa.string()),
            ("target_id", pa.string()),
            ("type", pa.string()),
            ("properties", pa.string()),
        ])

        table = pa.Table.from_pylist(edge_records, schema=schema)
        pq.write_table(table, output_file, compression="snappy")
        return output_file

    def write_vectors_lancedb(self, payload: GraphPayload, output_dir: str) -> str:
        """Serializes Node vector embeddings into a LanceDB vector dataset/Parquet index."""
        os.makedirs(output_dir, exist_ok=True)
        
        vector_records = []
        for n in payload.nodes:
            if n.embedding:
                vector_records.append({
                    "id": n.id,
                    "name": n.name,
                    "type": n.type.value,
                    "vector": n.embedding,
                })

        dim = len(vector_records[0]["vector"]) if vector_records else 384
        schema = pa.schema([
            ("id", pa.string()),
            ("name", pa.string()),
            ("type", pa.string()),
            ("vector", pa.list_(pa.float32(), dim)),
        ])

        table = pa.Table.from_pylist(vector_records, schema=schema)
        
        try:
            import lancedb
            db = lancedb.connect(output_dir)
            db.create_table("metadata", data=table, mode="overwrite")
        except ImportError:
            # Fallback to PyArrow dataset format if lancedb is not installed
            output_parquet = os.path.join(output_dir, "metadata_vectors.parquet")
            pq.write_table(table, output_parquet, compression="snappy")

        return output_dir

    def write_all(self, payload: GraphPayload, base_dir: str) -> Dict[str, str]:
        """Serializes nodes, edges, and vector indices to the standard storage layout."""
        nodes_path = os.path.join(base_dir, "graph", "nodes", "data.parquet")
        edges_path = os.path.join(base_dir, "graph", "edges", "data.parquet")
        vectors_dir = os.path.join(base_dir, "vectors", "metadata.lance")

        self.write_nodes_parquet(payload, nodes_path)
        self.write_edges_parquet(payload, edges_path)
        self.write_vectors_lancedb(payload, vectors_dir)

        return {
            "nodes": nodes_path,
            "edges": edges_path,
            "vectors": vectors_dir,
        }
