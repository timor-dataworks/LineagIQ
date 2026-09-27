"""LineagIQ Core Artifact Writer.

Serializes normalized GraphPayload models into Delta Lake table datasets
for graph nodes, edges, and dense vector embeddings.
"""

import json
import logging
import os
from typing import Any

import pyarrow as pa
from deltalake import write_deltalake

from core.constants import (
    get_edges_table_path,
    get_nodes_table_path,
    get_vectors_table_path,
)
from core.models import GraphPayload
from core.schemas import EDGE_SCHEMA, NODE_SCHEMA, get_vector_schema

logger = logging.getLogger(__name__)


class ArtifactWriter:
    """Artifact Writer serializes normalized GraphPayload models into Delta Lake table datasets
    for graph nodes, edges, and dense vector embeddings.
    """

    NODE_SCHEMA = NODE_SCHEMA
    EDGE_SCHEMA = EDGE_SCHEMA

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

    def write_nodes_table(
        self,
        payload: GraphPayload,
        target_dir: str,
        mode: str = "overwrite",
        storage_options: dict[str, Any] | None = None,
    ) -> pa.Table:
        """Constructs PyArrow Table for nodes and writes to Delta Lake dataset directory.

        Args:
            payload: Assembled GraphPayload containing graph nodes.
            target_dir: Target directory path or S3 URI for nodes Delta Lake table.
            mode: Write mode - 'overwrite' or 'append'. Defaults to 'overwrite'.
            storage_options: Optional storage backend configurations (e.g. AWS S3 credentials/endpoint).

        Returns:
            Generated PyArrow Table instance.
        """
        if not target_dir.startswith("s3://"):
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
            write_deltalake(target_dir, table, mode=mode, storage_options=storage_options)  # type: ignore
        except Exception as e:
            logger.warning(f"Delta Lake write_nodes_table warning: {e}")
        return table

    def write_edges_table(
        self,
        payload: GraphPayload,
        target_dir: str,
        mode: str = "overwrite",
        storage_options: dict[str, Any] | None = None,
    ) -> pa.Table:
        """Constructs PyArrow Table for edges and writes to Delta Lake dataset directory.

        Args:
            payload: Assembled GraphPayload containing lineage edges.
            target_dir: Target directory path or S3 URI for edges Delta Lake table.
            mode: Write mode - 'overwrite' or 'append'. Defaults to 'overwrite'.
            storage_options: Optional storage backend configurations (e.g. AWS S3 credentials/endpoint).

        Returns:
            Generated PyArrow Table instance.
        """
        if not target_dir.startswith("s3://"):
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
            write_deltalake(target_dir, table, mode=mode, storage_options=storage_options)  # type: ignore
        except Exception as e:
            logger.warning(f"Delta Lake write_edges_table warning: {e}")
        return table

    def write_vectors_table(
        self,
        payload: GraphPayload,
        target_dir: str,
        mode: str = "overwrite",
        storage_options: dict[str, Any] | None = None,
    ) -> pa.Table:
        """Constructs PyArrow Table for vectors and writes to Delta Lake dataset directory.

        Args:
            payload: Assembled GraphPayload containing vectorized nodes.
            target_dir: Target directory path or S3 URI for vectors Delta Lake table.
            mode: Write mode - 'overwrite' or 'append'. Defaults to 'overwrite'.
            storage_options: Optional storage backend configurations (e.g. AWS S3 credentials/endpoint).

        Returns:
            Generated PyArrow Table instance.
        """
        if not target_dir.startswith("s3://"):
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
        schema = get_vector_schema(dim)

        table = pa.Table.from_pylist(vector_records, schema=schema)
        try:
            write_deltalake(target_dir, table, mode=mode, storage_options=storage_options)  # type: ignore
        except Exception as e:
            logger.warning(f"Delta Lake write_vectors_table warning: {e}")
        return table

    def write_all(
        self,
        payload: GraphPayload,
        base_dir: str,
        mode: str = "overwrite",
        storage_options: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Serializes all graph nodes, lineage edges, and vector indices into Delta Lake datasets
        under the standardized tenant storage directory layout:
        - <base_dir>/graph/nodes (Delta Lake table)
        - <base_dir>/graph/edges (Delta Lake table)
        - <base_dir>/vectors     (Delta Lake table)

        Args:
            payload: Complete GraphPayload containing all graph entities and embeddings.
            base_dir: Root directory for output tenant artifacts or S3 URI (s3://bucket/tenant).
            mode: Write mode ('overwrite' or 'append') for Delta Lake commit logs.
            storage_options: Optional storage backend configurations (e.g. AWS S3 credentials/endpoint).

        Returns:
            Dictionary mapping dataset keys ('nodes', 'edges', 'vectors') to Delta Lake table directory paths or S3 URIs.
        """
        if base_dir.startswith("s3://"):
            base_clean = base_dir.rstrip("/")
            nodes_dir = f"{base_clean}/graph/nodes"
            edges_dir = f"{base_clean}/graph/edges"
            vectors_dir = f"{base_clean}/vectors"
        else:
            nodes_dir = get_nodes_table_path(base_dir)
            edges_dir = get_edges_table_path(base_dir)
            vectors_dir = get_vectors_table_path(base_dir)

        self.write_nodes_table(payload, nodes_dir, mode=mode, storage_options=storage_options)
        self.write_edges_table(payload, edges_dir, mode=mode, storage_options=storage_options)
        self.write_vectors_table(payload, vectors_dir, mode=mode, storage_options=storage_options)

        return {
            "nodes": nodes_dir,
            "edges": edges_dir,
            "vectors": vectors_dir,
        }
