"""LineagIQ Core PyArrow Schemas.

Defines standardized PyArrow schemas for Delta Lake tables and Parquet files
ensuring identical serialization/deserialization contracts across the platform.
"""

import pyarrow as pa
from core.constants import DEFAULT_EMBEDDING_DIM

# PyArrow schema definition for Graph Nodes Parquet/Delta dataset
NODE_SCHEMA = pa.schema([
    ("id", pa.string()),
    ("type", pa.string()),
    ("name", pa.string()),
    ("description", pa.string()),
    ("properties", pa.string()),
])

# PyArrow schema definition for Lineage Edges Parquet/Delta dataset
EDGE_SCHEMA = pa.schema([
    ("source_id", pa.string()),
    ("target_id", pa.string()),
    ("type", pa.string()),
    ("properties", pa.string()),
])


def get_vector_schema(dim: int = DEFAULT_EMBEDDING_DIM) -> pa.Schema:
    """Returns PyArrow schema definition for Dense Vectors Parquet/Delta dataset.

    Args:
        dim: Dimensionality of the dense vector embedding (defaults to 384).

    Returns:
        Configured PyArrow Schema instance.
    """
    return pa.schema([
        ("id", pa.string()),
        ("name", pa.string()),
        ("type", pa.string()),
        ("vector", pa.list_(pa.float32(), dim)),
    ])
