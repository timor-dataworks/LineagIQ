import pytest
from collection_agent.src.transform import (
    NodeType,
    EdgeType,
    DatasetNode,
    ColumnNode,
    PipelineNode,
    BusinessTermNode,
    Edge,
    GraphPayload,
)


def test_dataset_node_creation():
    node = DatasetNode(
        id="raw_db.analytics.stg_customers",
        name="stg_customers",
        database="raw_db",
        schema="analytics",
        description="Staged customer records",
        owner="analytics_team",
    )

    assert node.id == "raw_db.analytics.stg_customers"
    assert node.type == NodeType.DATASET
    assert node.name == "stg_customers"
    assert node.schema_name == "analytics"
    assert node.owner == "analytics_team"


def test_column_node_creation():
    node = ColumnNode(
        id="raw_db.analytics.stg_customers.customer_id",
        name="customer_id",
        dataset_id="raw_db.analytics.stg_customers",
        data_type="INTEGER",
        is_nullable=False,
        ordinal_position=1,
    )

    assert node.type == NodeType.COLUMN
    assert node.dataset_id == "raw_db.analytics.stg_customers"
    assert node.is_nullable is False


def test_edge_creation():
    edge = Edge(
        source_id="model.jaffle_shop.stg_customers",
        target_id="model.jaffle_shop.orders",
        type=EdgeType.DERIVED_FROM,
        properties={"transformation": "SQL SELECT"},
    )

    assert edge.source_id == "model.jaffle_shop.stg_customers"
    assert edge.target_id == "model.jaffle_shop.orders"
    assert edge.type == EdgeType.DERIVED_FROM
    assert edge.properties["transformation"] == "SQL SELECT"


def test_graph_payload_validation():
    ds_node = DatasetNode(
        id="analytics.orders",
        name="orders",
    )
    pipe_node = PipelineNode(
        id="dbt.orders_model",
        name="orders_model",
        resource_type="model",
    )
    edge = Edge(
        source_id="dbt.orders_model",
        target_id="analytics.orders",
        type=EdgeType.PRODUCED_BY,
    )

    payload = GraphPayload(nodes=[ds_node, pipe_node], edges=[edge])

    assert len(payload.nodes) == 2
    assert len(payload.edges) == 1
    assert payload.nodes[0].type == NodeType.DATASET
    assert payload.edges[0].type == EdgeType.PRODUCED_BY
