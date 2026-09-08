from core import DatasetNode, GraphPayload, ArtifactWriter
from control_plane.src.agent_tools import (
    LineagIQGraphRAGClient,
    get_dataset_blast_radius,
    search_enterprise_data_catalog,
)


def test_agent_tools_in_process(tmp_path):
    ds_node = DatasetNode(id="analytics.customers", name="customers", description="Customer table")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    client = LineagIQGraphRAGClient()

    # Test in-process blast radius prompt retrieval
    prompt_br = client.get_blast_radius_prompt(
        tenant_id="test_tenant",
        node_id="analytics.customers",
        data_path=str(tmp_path),
    )
    assert "LINEAGIQ GRAPHRAG PROMPT" in prompt_br
    assert "customers" in prompt_br

    # Test in-process discovery prompt retrieval
    prompt_disc = client.get_discovery_prompt(
        tenant_id="test_tenant",
        query="customers",
        data_path=str(tmp_path),
    )
    assert "SEMANTIC DATA DISCOVERY" in prompt_disc
    assert "customers" in prompt_disc


def test_standalone_retriever_tools(tmp_path):
    ds_node = DatasetNode(id="analytics.orders", name="orders", description="Order transactions")
    payload = GraphPayload(nodes=[ds_node], edges=[])
    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    prompt_br = get_dataset_blast_radius("test_tenant", "analytics.orders", data_path=str(tmp_path))
    assert "orders" in prompt_br

    prompt_disc = search_enterprise_data_catalog("test_tenant", "orders", data_path=str(tmp_path))
    assert "orders" in prompt_disc
