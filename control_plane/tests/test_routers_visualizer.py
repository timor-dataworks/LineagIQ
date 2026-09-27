from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient
from control_plane.src.routers.visualizer import router


def get_test_client():
    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


def test_healthz_endpoint():
    client = get_test_client()
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "lineagiq-control-plane"


def test_visualizer_endpoint():
    client = get_test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert "LineagIQ" in response.text
    assert "<html" in response.text.lower()

    # /visualizer alias
    alias_response = client.get("/visualizer")
    assert alias_response.status_code == 200
    assert "LineagIQ" in alias_response.text


def test_visualizer_missing_file(monkeypatch):
    client = get_test_client()
    monkeypatch.setattr(
        "control_plane.src.routers.visualizer.STATIC_INDEX_FILE",
        Path("/non_existent_path/index.html"),
    )
    response = client.get("/")
    assert response.status_code == 404
    assert "Visualizer index.html not found" in response.json()["detail"]


def test_app_config_endpoint(monkeypatch):
    monkeypatch.setenv("DATA_PATH", "/data/lineagiq")
    client = get_test_client()
    response = client.get("/api/v1/config")
    assert response.status_code == 200
    data = response.json()
    assert data["data_path"] == "/data/lineagiq"
    assert data["env_data_path_set"] is True
