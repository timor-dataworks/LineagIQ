from fastapi.testclient import TestClient
from core import DatasetNode, GraphPayload, ArtifactWriter
from control_plane.src.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_graph_visualizer_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "LineagIQ Control Plane - Knowledge Graph Visualizer" in response.text


def test_get_tenant_graph(tmp_path):
    ds_node = DatasetNode(id="analytics.orders", name="orders", description="Cleaned orders")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    response = client.get(f"/api/v1/tenants/tenant123/graph?data_path={tmp_path}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["nodes"]) == 1
    assert data["nodes"][0]["name"] == "orders"


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


def test_blast_radius_api_empty_path(tmp_path):
    response = client.post(
        "/api/v1/tenants/empty_tenant/blast-radius",
        json={
            "node_id": "non_existent_node",
            "max_depth": 3,
            "data_path": str(tmp_path / "non_existent"),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "empty_tenant"
    assert data["depth_reached"] == 0
    assert data["impacted_nodes_count"] == 0


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


def test_lineage_ai_chat_api(tmp_path):
    ds_node = DatasetNode(id="analytics.orders", name="orders", description="Cleaned orders")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    response = client.post(
        "/api/v1/tenants/tenant123/chat",
        json={
            "message": "What is the blast radius of orders?",
            "data_path": str(tmp_path),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant123"
    assert "Blast Radius Analysis" in data["reply"]
    assert "synthesized_prompt" in data


def test_root_cause_api(tmp_path):
    ds_node = DatasetNode(id="analytics.orders", name="orders", description="Cleaned orders")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    response = client.post(
        "/api/v1/tenants/tenant123/root-cause",
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
    assert "UPSTREAM ROOT CAUSE" in data["synthesized_prompt"]


def test_lineage_ai_chat_root_cause_intent(tmp_path):
    ds_node = DatasetNode(id="analytics.orders", name="orders", description="Cleaned orders")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    response = client.post(
        "/api/v1/tenants/tenant123/chat",
        json={
            "message": "What is the upstream root cause of orders?",
            "data_path": str(tmp_path),
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == "tenant123"
    assert "Upstream Root Cause Analysis" in data["reply"]
    assert "<strong>" in data["reply"]
    assert "synthesized_prompt" in data
    assert "FORMATTING RULE: Format your response using clean, semantic HTML tags" in data["synthesized_prompt"]


def test_clean_latex_to_unicode():
    from control_plane.src.main import clean_latex_to_unicode

    assert clean_latex_to_unicode("raw_customers $\\rightarrow$ stg_customers") == "raw_customers → stg_customers"
    assert clean_latex_to_unicode("source $\\to$ target") == "source → target"
    assert clean_latex_to_unicode("model_a \\rightarrow model_b") == "model_a → model_b"
    assert clean_latex_to_unicode("$\\text{raw\\_orders} \\rightarrow \\text{stg\\_orders}$") == "raw_orders → stg_orders"
    assert clean_latex_to_unicode("target $\\leftarrow$ source") == "target ← source"
    assert clean_latex_to_unicode("a $\\Rightarrow$ b") == "a ⇒ b"
    assert clean_latex_to_unicode("x $\\approx$ y") == "x ≈ y"
    assert clean_latex_to_unicode(None) is None
    assert clean_latex_to_unicode("") == ""

