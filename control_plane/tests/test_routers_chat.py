from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import DatasetNode, GraphPayload, ArtifactWriter
from control_plane.src.routers.chat import router


def get_test_client():
    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


def test_chat_blast_radius_intent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders", description="Order fact table")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/chat",
        json={"message": "What is the blast radius of orders?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Blast Radius Analysis" in data["reply"]
    assert data["target_node_id"] == "analytics.orders"


def test_chat_root_cause_intent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders", description="Order fact table")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/chat",
        json={"message": "What is the upstream root cause of orders?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "Upstream Root Cause Analysis" in data["reply"]
    assert data["target_node_id"] == "analytics.orders"


def test_chat_discovery_intent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    ds = DatasetNode(id="analytics.orders", name="orders", description="Order fact table")
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[ds], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/chat",
        json={"message": "orders"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["matched_nodes"]) >= 1


def test_chat_general_help_intent(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    writer = ArtifactWriter()
    writer.write_all(GraphPayload(nodes=[], edges=[]), str(tmp_path))

    response = client.post(
        "/api/v1/chat",
        json={"message": "Hello, how does this work?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "LineagIQ Knowledge Graph active" in data["reply"]


def test_chat_missing_message(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    client = get_test_client()
    response = client.post(
        "/api/v1/chat",
        json={},
    )
    # Validation error since message is required
    assert response.status_code == 422
