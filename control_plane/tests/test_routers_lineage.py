from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import DatasetNode, GraphPayload, ArtifactWriter
from control_plane.src.routers.lineage import router


def get_test_client():
    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


def test_get_graph_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders", description="Order facts")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.get("/api/v1/graph")
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["id"] == "analytics.orders"


def test_get_timeline_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.get("/api/v1/timeline")
    assert response.status_code == 200
    data = response.json()
    assert "timestamps" in data


def test_blast_radius_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/blast-radius",
        json={"node_id": "analytics.orders", "max_depth": 4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_node"]["id"] == "analytics.orders"
    assert "synthesized_prompt" in data


def test_root_cause_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/root-cause",
        json={"node_id": "analytics.orders", "max_depth": 4},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["target_node"]["id"] == "analytics.orders"
    assert "synthesized_prompt" in data


def test_discovery_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders", description="Customer orders")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/discovery",
        json={"query": "orders", "top_k": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["matched_nodes_count"] == 1
    assert "synthesized_prompt" in data


def test_time_travel_diff_endpoint(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/time-travel/diff",
        json={
            "node_id": "analytics.orders",
            "timestamp_t1": "2026-09-08T10:00:00Z",
            "timestamp_t2": "2026-09-08T11:00:00Z",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "diff" in data
    assert "synthesized_prompt" in data
