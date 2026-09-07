from collection_agent.src.transform import DatasetNode, GraphPayload
from collection_agent.src.storage.writer import ArtifactWriter
from control_plane.src.agy_integration import run_agy_blast_radius, run_agy_discovery


def test_agy_integration_blast_radius(tmp_path):
    ds_node = DatasetNode(id="analytics.users", name="users", description="Users table")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    prompt = run_agy_blast_radius("test_tenant", "analytics.users", data_path=str(tmp_path))
    assert "LINEAGIQ GRAPHRAG PROMPT" in prompt
    assert "users" in prompt


def test_agy_integration_discovery(tmp_path):
    ds_node = DatasetNode(id="analytics.users", name="users", description="Users table")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    prompt = run_agy_discovery("test_tenant", "users", data_path=str(tmp_path))
    assert "SEMANTIC DATA DISCOVERY" in prompt
    assert "users" in prompt
