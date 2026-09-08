import os
import pyarrow.parquet as pq
from core import (
    LocalEmbedder,
    ArtifactWriter,
    DatasetNode,
    ColumnNode,
    Edge,
    EdgeType,
    GraphPayload,
)


def test_artifact_writer_parquet_and_vectors(tmp_path):
    ds_node = DatasetNode(id="analytics.users", name="users", description="User records")
    col_node = ColumnNode(id="analytics.users.id", name="id", dataset_id="analytics.users")
    edge = Edge(source_id="analytics.users.id", target_id="analytics.users", type=EdgeType.JOINS_WITH)

    payload = GraphPayload(nodes=[ds_node, col_node], edges=[edge])

    # Embed payload
    embedder = LocalEmbedder()
    payload = embedder.embed_payload(payload)

    writer = ArtifactWriter()
    output_paths = writer.write_all(payload, str(tmp_path))

    # Verify Nodes Parquet
    nodes_file = output_paths["nodes"]
    assert os.path.exists(nodes_file)
    nodes_table = pq.read_table(nodes_file)
    assert nodes_table.num_rows == 2
    assert "id" in nodes_table.column_names
    assert "type" in nodes_table.column_names

    # Verify Edges Parquet
    edges_file = output_paths["edges"]
    assert os.path.exists(edges_file)
    edges_table = pq.read_table(edges_file)
    assert edges_table.num_rows == 1
    assert "source_id" in edges_table.column_names

    # Verify Vectors Parquet
    vectors_file = output_paths["vectors"]
    assert os.path.exists(vectors_file)
    vectors_table = pq.read_table(vectors_file)
    assert vectors_table.num_rows == 2
    assert "vector" in vectors_table.column_names
