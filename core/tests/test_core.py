import os
import pytest
from core.models import (
    NodeType,
    EdgeType,
    Node,
    DatasetNode,
    ColumnNode,
    PipelineNode,
    UserTeamNode,
    BusinessTermNode,
    Edge,
    GraphPayload,
)
from core.constants import (
    TABLE_NODES,
    TABLE_EDGES,
    TABLE_VECTORS,
    get_nodes_table_path,
    get_edges_table_path,
    get_vectors_table_path,
)
from core.schemas import NODE_SCHEMA, EDGE_SCHEMA, get_vector_schema
from core.embedder import LocalEmbedder, get_default_embedder
from core.writer import ArtifactWriter
from core.utils import parse_iso_to_epoch_ms, extract_search_terms


def test_core_ontology_models():
    ds = DatasetNode(id="raw_orders", name="raw_orders", database="analytics", schema="public")
    assert ds.type == NodeType.DATASET
    assert ds.database == "analytics"

    col = ColumnNode(id="raw_orders.id", name="id", dataset_id="raw_orders", data_type="BIGINT")
    assert col.type == NodeType.COLUMN
    assert col.dataset_id == "raw_orders"

    pipe = PipelineNode(id="pipe_1", name="dbt_run", resource_type="model")
    assert pipe.type == NodeType.PIPELINE

    edge = Edge(source_id=pipe.id, target_id=ds.id, type=EdgeType.PRODUCED_BY)
    assert edge.type == EdgeType.PRODUCED_BY

    payload = GraphPayload(nodes=[ds, col, pipe], edges=[edge])
    assert len(payload.nodes) == 3
    assert len(payload.edges) == 1


def test_core_constants_and_paths():
    base = "/tmp/test_tenant"
    assert get_nodes_table_path(base) == os.path.join(base, "graph", "nodes")
    assert get_edges_table_path(base) == os.path.join(base, "graph", "edges")
    assert get_vectors_table_path(base) == os.path.join(base, "vectors")


def test_core_schemas():
    assert "id" in NODE_SCHEMA.names
    assert "properties" in NODE_SCHEMA.names
    assert "source_id" in EDGE_SCHEMA.names
    v_schema = get_vector_schema(384)
    assert "vector" in v_schema.names


def test_core_embedder_caching():
    embedder1 = get_default_embedder()
    embedder2 = get_default_embedder()
    assert embedder1 is embedder2

    vec = embedder1.embed_text("customer transactions table")
    assert len(vec) == 384
    # Unit normalized
    norm = sum(x * x for x in vec) ** 0.5
    assert pytest.approx(norm, rel=1e-3) == 1.0


def test_core_utils():
    # ISO timestamp parsing
    epoch = parse_iso_to_epoch_ms("2026-09-08T10:00:00Z")
    assert epoch is not None
    assert epoch > 0

    # Invalid timestamp returns None
    assert parse_iso_to_epoch_ms("not-a-date") is None
    assert parse_iso_to_epoch_ms(None) is None

    # Search term extraction
    terms = extract_search_terms("find the customer table where email is listed")
    assert "customer" in terms
    assert "email" in terms
    assert "find" not in terms


def test_core_writer_roundtrip(tmp_path):
    writer = ArtifactWriter()
    ds = DatasetNode(id="users", name="users", description="User records")
    edge = Edge(source_id="app", target_id="users", type=EdgeType.PRODUCED_BY)
    embedder = get_default_embedder()
    payload = GraphPayload(nodes=[ds], edges=[edge])
    payload = embedder.embed_payload(payload)

    target_dir = str(tmp_path / "tenant_data")
    artifacts = writer.write_all(payload, target_dir)

    assert os.path.exists(artifacts["nodes"])
    assert os.path.exists(artifacts["edges"])
    assert os.path.exists(artifacts["vectors"])
