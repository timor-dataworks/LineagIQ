import pytest
from collection_agent.src.embedder.local_embedder import LocalEmbedder
from collection_agent.src.transform.models import DatasetNode, ColumnNode, GraphPayload


def test_local_embedder_vector_generation():
    embedder = LocalEmbedder()
    vec = embedder.embed_text("Type: Dataset | Name: stg_customers | Description: Customer table")

    assert len(vec) == 384
    # Check L2 normalized magnitude approximately 1.0
    norm = sum(x * x for x in vec) ** 0.5
    assert pytest.approx(norm, abs=1e-3) == 1.0


def test_local_embedder_payload():
    ds_node = DatasetNode(id="ds1", name="orders", description="Order transactions")
    col_node = ColumnNode(id="col1", name="id", dataset_id="ds1")
    payload = GraphPayload(nodes=[ds_node, col_node], edges=[])

    embedder = LocalEmbedder()
    embedded_payload = embedder.embed_payload(payload)

    for node in embedded_payload.nodes:
        assert node.embedding is not None
        assert len(node.embedding) == 384
