import os
from collection_agent.src.transform import (
    DatasetNode,
    PipelineNode,
    ColumnNode,
    Edge,
    EdgeType,
    GraphPayload,
)
from collection_agent.src.storage.writer import ArtifactWriter
from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer


def test_duckdb_blast_radius_traversal(tmp_path):
    # Construct a sample graph: Raw Customers -> Stg Customers Model -> Orders Model
    raw_ds = DatasetNode(id="raw.customers", name="raw_customers", description="Raw landing table")
    stg_pipe = PipelineNode(id="dbt.stg_customers", name="stg_customers", resource_type="model")
    stg_ds = DatasetNode(id="analytics.stg_customers", name="stg_customers", description="Staged customers")
    orders_pipe = PipelineNode(id="dbt.orders", name="orders", resource_type="model")

    edge1 = Edge(source_id="raw.customers", target_id="dbt.stg_customers", type=EdgeType.CONSUMED_BY)
    edge2 = Edge(source_id="dbt.stg_customers", target_id="analytics.stg_customers", type=EdgeType.PRODUCED_BY)
    edge3 = Edge(source_id="analytics.stg_customers", target_id="dbt.orders", type=EdgeType.CONSUMED_BY)

    payload = GraphPayload(
        nodes=[raw_ds, stg_pipe, stg_ds, orders_pipe],
        edges=[edge1, edge2, edge3],
    )

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    engine = DuckDBQueryEngine(data_base_path=str(tmp_path))
    result = engine.get_downstream_blast_radius("raw.customers", max_depth=5)

    assert result["root_node"]["id"] == "raw.customers"
    assert len(result["impacted_nodes"]) == 4
    assert len(result["edges"]) == 3
    assert result["depth_reached"] == 3

    # Test Prompt Synthesis
    synthesizer = PromptSynthesizer()
    prompt = synthesizer.synthesize_blast_radius_prompt(
        start_node=result["root_node"],
        impacted_nodes=result["impacted_nodes"],
        edges=result["edges"],
    )

    assert "LINEAGIQ GRAPHRAG PROMPT" in prompt
    assert "raw_customers" in prompt
    assert "dbt.orders" in prompt
