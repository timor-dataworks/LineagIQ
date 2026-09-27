import pytest
from control_plane.src.config import (
    resolve_data_path,
    STATIC_DIR,
    STATIC_INDEX_FILE,
)


def test_static_paths_configuration():
    assert STATIC_DIR.is_dir()
    assert STATIC_INDEX_FILE.is_file()
    assert STATIC_INDEX_FILE.name == "index.html"


def test_resolve_data_path_missing_raises_error(monkeypatch):
    monkeypatch.delenv("DATA_PATH", raising=False)
    with pytest.raises(ValueError, match="DATA_PATH environment variable must be set"):
        resolve_data_path()


def test_resolve_data_path_success(monkeypatch):
    monkeypatch.setenv("DATA_PATH", "/mnt/data/lake")
    assert resolve_data_path() == "/mnt/data/lake"


def test_resolve_data_path_env_s3(monkeypatch):
    monkeypatch.setenv("DATA_PATH", "s3://my-lake/data")
    assert resolve_data_path() == "s3://my-lake/data"
