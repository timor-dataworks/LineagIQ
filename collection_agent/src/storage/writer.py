import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import pyarrow as pa
import pyarrow.parquet as pq
from deltalake import write_deltalake
from collection_agent.src.transform.models import GraphPayload

logger = logging.getLogger(__name__)


class ArtifactWriter:
    """Artifact Writer serializes normalized GraphPayload models into Delta Lake table datasets
    and Snappy-compressed Parquet columnar files for graph nodes, edges, and dense vector embeddings.
    """

    # Static PyArrow schema definition for Graph Nodes Parquet/Delta dataset
    NODE_SCHEMA = pa.schema([
        ("id", pa.string()),
        ("type", pa.string()),
        ("name", pa.string()),
        ("description", pa.string()),
        ("properties", pa.string()),
    ])

    # Static PyArrow schema definition for Lineage Edges Parquet/Delta dataset
    EDGE_SCHEMA = pa.schema([
        ("source_id", pa.string()),
        ("target_id", pa.string()),
        ("type", pa.string()),
        ("properties", pa.string()),
    ])

    def _extract_node_properties(self, node: Any) -> str:
        """Helper method to extract extra subclass attributes (e.g., database, schema, data_type)
        and merge them with `node.properties` into a unified JSON string representation.

        Args:
            node: LineagIQ Node model instance.

        Returns:
            JSON-formatted string of all node properties and subclass attributes.
        """
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

    def write_nodes_table(self, payload: GraphPayload, target_dir: str, mode: str = "overwrite") -> pa.Table:
        """Constructs PyArrow Table for nodes and writes to Delta Lake dataset directory.

        Args:
            payload: Assembled GraphPayload containing graph nodes.
            target_dir: Target directory path for nodes Delta Lake table.
            mode: Write mode - 'overwrite' or 'append'. Defaults to 'overwrite'.

        Returns:
            Generated PyArrow Table instance.
        """
        os.makedirs(target_dir, exist_ok=True)
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
        table = pa.Table.from_pylist(node_records, schema=self.NODE_SCHEMA)
        try:
            write_deltalake(target_dir, table, mode=mode)
        except Exception as e:
            logger.warning(f"Delta Lake write_nodes_table warning: {e}")
        return table

    def write_edges_table(self, payload: GraphPayload, target_dir: str, mode: str = "overwrite") -> pa.Table:
        """Constructs PyArrow Table for edges and writes to Delta Lake dataset directory.

        Args:
            payload: Assembled GraphPayload containing lineage edges.
            target_dir: Target directory path for edges Delta Lake table.
            mode: Write mode - 'overwrite' or 'append'. Defaults to 'overwrite'.

        Returns:
            Generated PyArrow Table instance.
        """
        os.makedirs(target_dir, exist_ok=True)
        edge_records = [
            {
                "source_id": e.source_id,
                "target_id": e.target_id,
                "type": e.type.value if hasattr(e.type, "value") else str(e.type),
                "properties": json.dumps(e.properties or {}),
            }
            for e in payload.edges
        ]
        table = pa.Table.from_pylist(edge_records, schema=self.EDGE_SCHEMA)
        try:
            write_deltalake(target_dir, table, mode=mode)
        except Exception as e:
            logger.warning(f"Delta Lake write_edges_table warning: {e}")
        return table

    def write_vectors_table(self, payload: GraphPayload, target_dir: str, mode: str = "overwrite") -> pa.Table:
        """Constructs PyArrow Table for vectors and writes to Delta Lake dataset directory.

        Args:
            payload: Assembled GraphPayload containing vectorized nodes.
            target_dir: Target directory path for vectors Delta Lake table.
            mode: Write mode - 'overwrite' or 'append'. Defaults to 'overwrite'.

        Returns:
            Generated PyArrow Table instance.
        """
        os.makedirs(target_dir, exist_ok=True)
        vector_records = [
            {
                "id": n.id,
                "name": n.name,
                "type": n.type.value if hasattr(n.type, "value") else str(n.type),
                "vector": [float(x) for x in n.embedding],
            }
            for n in payload.nodes
            if n.embedding
        ]

        dim = len(vector_records[0]["vector"]) if vector_records else 384
        schema = pa.schema([
            ("id", pa.string()),
            ("name", pa.string()),
            ("type", pa.string()),
            ("vector", pa.list_(pa.float32(), dim)),
        ])

        table = pa.Table.from_pylist(vector_records, schema=schema)
        try:
            write_deltalake(target_dir, table, mode=mode)
        except Exception as e:
            logger.warning(f"Delta Lake write_vectors_table warning: {e}")
        return table

    def write_nodes_parquet(self, payload: GraphPayload, output_file: str) -> str:
        """Serializes GraphPayload nodes into a Snappy-compressed Parquet file.

        Args:
            payload: Assembled GraphPayload containing graph nodes.
            output_file: Target file path for nodes.parquet.

        Returns:
            Path to the generated nodes Parquet file.
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        node_dir = os.path.dirname(output_file)
        table = self.write_nodes_table(payload, node_dir, mode="overwrite")
        pq.write_table(table, output_file, compression="snappy")
        return output_file

    def write_edges_parquet(self, payload: GraphPayload, output_file: str) -> str:
        """Serializes GraphPayload edges into a Snappy-compressed Parquet file.

        Args:
            payload: Assembled GraphPayload containing lineage edges.
            output_file: Target file path for edges.parquet.

        Returns:
            Path to the generated edges Parquet file.
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        edge_dir = os.path.dirname(output_file)
        table = self.write_edges_table(payload, edge_dir, mode="overwrite")
        pq.write_table(table, output_file, compression="snappy")
        return output_file

    def write_vectors_parquet(self, payload: GraphPayload, output_file: str) -> str:
        """Serializes Node vector embeddings into a Snappy-compressed Parquet file.

        Args:
            payload: Assembled GraphPayload containing vectorized nodes.
            output_file: Target file path for vectors/data.parquet.

        Returns:
            Path to the generated vectors Parquet file.
        """
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        vec_dir = os.path.dirname(output_file)
        table = self.write_vectors_table(payload, vec_dir, mode="overwrite")
        pq.write_table(table, output_file, compression="snappy")
        return output_file

    def write_all(self, payload: GraphPayload, base_dir: str, mode: str = "overwrite") -> Dict[str, str]:
        """Serializes all graph nodes, lineage edges, and vector indices into Delta Lake datasets
        and standard Parquet files under tenant storage directory layout:
        - <base_dir>/graph/nodes (Delta Lake table directory & data.parquet)
        - <base_dir>/graph/edges (Delta Lake table directory & data.parquet)
        - <base_dir>/vectors (Delta Lake table directory & data.parquet)

        Args:
            payload: Complete GraphPayload containing all graph entities and embeddings.
            base_dir: Root directory for output tenant artifacts.
            mode: Write mode ('overwrite' or 'append') for Delta Lake commit logs.

        Returns:
            Dictionary mapping asset names ('nodes', 'edges', 'vectors') to absolute Parquet file paths.
        """
        nodes_dir = os.path.join(base_dir, "graph", "nodes")
        edges_dir = os.path.join(base_dir, "graph", "edges")
        vectors_dir = os.path.join(base_dir, "vectors")

        nodes_table = self.write_nodes_table(payload, nodes_dir, mode=mode)
        edges_table = self.write_edges_table(payload, edges_dir, mode=mode)
        vectors_table = self.write_vectors_table(payload, vectors_dir, mode=mode)

        nodes_parquet = os.path.join(nodes_dir, "data.parquet")
        edges_parquet = os.path.join(edges_dir, "data.parquet")
        vectors_parquet = os.path.join(vectors_dir, "data.parquet")

        pq.write_table(nodes_table, nodes_parquet, compression="snappy")
        pq.write_table(edges_table, edges_parquet, compression="snappy")
        pq.write_table(vectors_table, vectors_parquet, compression="snappy")

        return {
            "nodes": nodes_parquet,
            "edges": edges_parquet,
            "vectors": vectors_parquet,
        }

