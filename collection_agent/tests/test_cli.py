import os

from collection_agent.src.cli import run_pipeline


def test_end_to_end_pipeline_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    res = run_pipeline(sync_s3=False, load_demo=False)

    assert res["nodes_count"] == 0
    assert res["edges_count"] == 0
    assert os.path.exists(res["artifacts"]["nodes"])
    assert os.path.exists(res["artifacts"]["edges"])
    assert os.path.exists(res["artifacts"]["vectors"])


def test_end_to_end_pipeline_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    res = run_pipeline(sync_s3=False, load_demo=True)

    assert res["nodes_count"] > 0
    assert res["edges_count"] > 0
    assert os.path.exists(res["artifacts"]["nodes"])
    assert os.path.exists(res["artifacts"]["edges"])
    assert os.path.exists(res["artifacts"]["vectors"])


def test_end_to_end_pipeline_openlineage(tmp_path, monkeypatch):
    from pathlib import Path

    ol_fixture = Path(__file__).parent / "fixtures" / "openlineage_event.json"
    monkeypatch.setenv("DATA_PATH", str(tmp_path))
    res = run_pipeline(sync_s3=False, openlineage=str(ol_fixture), load_demo=False)

    assert res["nodes_count"] > 0
    assert res["edges_count"] > 0
    assert os.path.exists(res["artifacts"]["nodes"])
    assert os.path.exists(res["artifacts"]["edges"])
    assert os.path.exists(res["artifacts"]["vectors"])
