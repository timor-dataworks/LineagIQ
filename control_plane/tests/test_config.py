import os
from control_plane.src.config import resolve_data_path, STATIC_DIR, STATIC_INDEX_FILE


def test_static_paths_configuration():
    assert STATIC_DIR.is_dir()
    assert STATIC_INDEX_FILE.is_file()
    assert STATIC_INDEX_FILE.name == "index.html"


def test_resolve_data_path_custom():
    custom = "/custom/path/to/tenant_data"
    assert resolve_data_path("tenant_a", custom) == custom


def test_resolve_data_path_default(monkeypatch):
    monkeypatch.delenv("TENANT_DATA_DIR", raising=False)
    assert resolve_data_path("tenant_b") == "/tmp/tenants/tenant_b"


def test_resolve_data_path_env_override(monkeypatch):
    monkeypatch.setenv("TENANT_DATA_DIR", "/mnt/shared_tenants")
    assert resolve_data_path("tenant_c") == "/mnt/shared_tenants"
