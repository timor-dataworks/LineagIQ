from fastapi.testclient import TestClient
from collection_agent.src.transform import DatasetNode, GraphPayload
from collection_agent.src.storage.writer import ArtifactWriter
from control_plane.src.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_blast_radius_api(tmp_path):
    ds_node = DatasetNode(id="analytics.orders", name="orders", description="Cleaned orders")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    response = client.post(
        "/api/v1/tenants/tenant123/blast-radius",
        json={
            "node_id": "analytics.orders",
            "max_depth": 3,
            "data_path": str(tmp_path),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant123"
    assert data["target_node"]["id"] == "analytics.orders"
    assert "LINEAGIQ GRAPHRAG PROMPT" in data["synthesized_prompt"]


def test_discovery_api(tmp_path):
    ds_node = DatasetNode(id="analytics.orders", name="orders", description="Cleaned orders")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    response = client.post(
        "/api/v1/tenants/tenant123/discovery",
        json={
            "query": "orders",
            "top_k": 5,
            "data_path": str(tmp_path),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant123"
    assert data["matched_nodes_count"] == 1
    assert "LINEAGIQ GRAPHRAG PROMPT: SEMANTIC DATA DISCOVERY" in data["synthesized_prompt"]
