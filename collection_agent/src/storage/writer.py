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
    columnar files for nodes, edges, and vector embeddings.
    """

    def _extract_node_properties(self, node: Any) -> str:
        """Helper to extract extra subclass fields and merge into properties JSON."""
        extra_props = (
            node.model_dump(
                exclude={"id", "type", "name", "description", "properties", "embedding"},
                exclude_none=True,
                by_alias=True,
            )
            if hasattr(node, "model_dump")
            else {}
        )
        combined = {**extra_props, **(node.properties or {})}
        return json.dumps(combined)

    def write_nodes_parquet(self, payload: GraphPayload, output_file: str) -> str:
        """Serializes GraphPayload nodes into a Snappy-compressed Parquet file."""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        node_records = [
            {
                "id": n.id,
                "type": n.type.value if hasattr(n.type, "value") else str(n.type),
                "name": n.name,
                "description": n.description or "",
                "properties": self._extract_node_properties(n),
            }
            for n in payload.nodes
        ]

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

    def write_vectors_parquet(self, payload: GraphPayload, output_file: str) -> str:
        """Serializes Node vector embeddings into a Snappy-compressed Parquet file for DuckDB VSS."""
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        vector_records = []
        for n in payload.nodes:
            if n.embedding:
                vector_records.append({
                    "id": n.id,
                    "name": n.name,
                    "type": n.type.value if hasattr(n.type, "value") else str(n.type),
                    "vector": [float(x) for x in n.embedding],
                })

        dim = len(vector_records[0]["vector"]) if vector_records else 384
        schema = pa.schema([
            ("id", pa.string()),
            ("name", pa.string()),
            ("type", pa.string()),
            ("vector", pa.list_(pa.float32(), dim)),
        ])

        table = pa.Table.from_pylist(vector_records, schema=schema)
        pq.write_table(table, output_file, compression="snappy")
        return output_file

    def write_all(self, payload: GraphPayload, base_dir: str) -> Dict[str, str]:
        """Serializes nodes, edges, and vector indices to standard DuckDB/Parquet storage layout."""
        nodes_path = os.path.join(base_dir, "graph", "nodes", "data.parquet")
        edges_path = os.path.join(base_dir, "graph", "edges", "data.parquet")
        vectors_path = os.path.join(base_dir, "vectors", "data.parquet")

        self.write_nodes_parquet(payload, nodes_path)
        self.write_edges_parquet(payload, edges_path)
        self.write_vectors_parquet(payload, vectors_path)

        return {
            "nodes": nodes_path,
            "edges": edges_path,
            "vectors": vectors_path,
        }

