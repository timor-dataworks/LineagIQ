import pytest


@pytest.fixture(autouse=True)
def setup_test_env(request, monkeypatch):
    """Sets default test environment variables for the test suite.

    If a test uses the `tmp_path` fixture, DATA_PATH is automatically
    pointed to `tmp_path` so server-side data resolution locates test artifacts.
    """
    if "tmp_path" in request.fixturenames:
        tmp_path = request.getfixturevalue("tmp_path")
        monkeypatch.setenv("DATA_PATH", str(tmp_path))
    else:
        monkeypatch.setenv("DATA_PATH", "/tmp/lineagiq_data")
