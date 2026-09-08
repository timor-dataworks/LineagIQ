import os
import time
import pytest
from fastapi.testclient import TestClient

from core import (
    GraphPayload,
    DatasetNode,
    ColumnNode,
    Edge,
    EdgeType,
    ArtifactWriter,
    LocalEmbedder,
)
from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.main import app, resolve_data_path


@pytest.fixture
def client():
    return TestClient(app)


def test_delta_table_commits_and_time_travel_query(tmp_path):
    writer = ArtifactWriter()
    embedder = LocalEmbedder()
    base_dir = str(tmp_path)

    # Initial graph payload (Snapshot T1)
    ds1 = DatasetNode(id="model.jaffle_shop.customers", name="customers", description="Customer table v1")
    col1 = ColumnNode(id="model.jaffle_shop.customers.id", name="id", dataset_id="model.jaffle_shop.customers")
    edge1 = Edge(source_id="model.jaffle_shop.customers.id", target_id="model.jaffle_shop.customers", type=EdgeType.BELONGS_TO)

    payload1 = GraphPayload(nodes=[ds1, col1], edges=[edge1])
    payload1 = embedder.embed_payload(payload1)

    # Commit snapshot T1 to Delta Lake
    writer.write_all(payload1, base_dir, mode="overwrite")

    engine = DuckDBQueryEngine(data_base_path=base_dir)
    timestamps_t1 = engine.get_available_timestamps()
    assert len(timestamps_t1) >= 1
    t1_iso = timestamps_t1[0]["timestamp"]

    # Sleep 1.1s to ensure distinct ISO timestamp resolution
    time.sleep(1.1)

    # Updated graph payload with added node (Snapshot T2)
    ds2 = DatasetNode(id="model.jaffle_shop.orders", name="orders", description="Orders table v2")
    col2 = ColumnNode(id="model.jaffle_shop.orders.id", name="id", dataset_id="model.jaffle_shop.orders")
    edge2 = Edge(source_id="model.jaffle_shop.orders.id", target_id="model.jaffle_shop.orders", type=EdgeType.BELONGS_TO)
    edge3 = Edge(source_id="model.jaffle_shop.customers", target_id="model.jaffle_shop.orders", type=EdgeType.DERIVED_FROM)

    payload2 = GraphPayload(nodes=[ds1, col1, ds2, col2], edges=[edge1, edge2, edge3])
    payload2 = embedder.embed_payload(payload2)

    # Commit snapshot T2 to Delta Lake (append log)
    writer.write_all(payload2, base_dir, mode="append")

    timestamps_t2 = engine.get_available_timestamps()
    assert len(timestamps_t2) >= 2
    t2_iso = timestamps_t2[-1]["timestamp"]

    # 1. Historical query at T1 should return only 2 nodes (customers, customers.id)
    graph_t1 = engine.get_full_graph(as_of=t1_iso)
    assert len(graph_t1["nodes"]) == 2
    node_ids_t1 = {n["id"] for n in graph_t1["nodes"]}
    assert "model.jaffle_shop.customers" in node_ids_t1
    assert "model.jaffle_shop.orders" not in node_ids_t1

    # 2. Historical query at T2 should return all 4 nodes
    graph_t2 = engine.get_full_graph(as_of=t2_iso)
    assert len(graph_t2["nodes"]) == 4
    node_ids_t2 = {n["id"] for n in graph_t2["nodes"]}
    assert "model.jaffle_shop.orders" in node_ids_t2

    # 3. Vector search at T1 vs T2
    search_t1 = engine.search_semantic_assets("orders", top_k=5, as_of=t1_iso)
    assert not any(n["id"] == "model.jaffle_shop.orders" for n in search_t1)

    search_t2 = engine.search_semantic_assets("orders", top_k=5, as_of=t2_iso)
    assert any(n["id"] == "model.jaffle_shop.orders" for n in search_t2)

    # 4. Schema diff between T1 and T2
    diff = engine.get_schema_time_travel_diff("model.jaffle_shop.customers", t1_iso, t2_iso)
    assert diff["added_nodes_count"] == 2
    assert diff["removed_nodes_count"] == 0
    added_ids = {n["id"] for n in diff["added_nodes"]}
    assert "model.jaffle_shop.orders" in added_ids


def test_time_travel_api_endpoints(client, tmp_path, monkeypatch):
    writer = ArtifactWriter()
    embedder = LocalEmbedder()
    base_dir = str(tmp_path)
    monkeypatch.setenv("TENANT_DATA_DIR", base_dir)

    ds1 = DatasetNode(id="model.users", name="users", description="Users catalog")
    payload1 = embedder.embed_payload(GraphPayload(nodes=[ds1], edges=[]))
    writer.write_all(payload1, base_dir, mode="overwrite")

    engine = DuckDBQueryEngine(data_base_path=base_dir)
    timestamps = engine.get_available_timestamps()
    t1_iso = timestamps[0]["timestamp"]

    # Timeline endpoint test
    res_timeline = client.get("/api/v1/tenants/test_tenant/timeline")
    assert res_timeline.status_code == 200
    timeline_json = res_timeline.json()
    assert timeline_json["timestamps_count"] >= 1

    # Graph endpoint with as_of query parameter test
    res_graph = client.get(f"/api/v1/tenants/test_tenant/graph?as_of={t1_iso}")
    assert res_graph.status_code == 200
    graph_json = res_graph.json()
    assert len(graph_json["nodes"]) == 1

    # Time Travel Diff REST API test
    res_diff = client.post(
        "/api/v1/tenants/test_tenant/time-travel/diff",
        json={"node_id": "model.users", "timestamp_t1": t1_iso, "timestamp_t2": t1_iso},
    )
    assert res_diff.status_code == 200
    diff_json = res_diff.json()
    assert "diff" in diff_json
    assert "synthesized_prompt" in diff_json
