import json
from pathlib import Path
from collection_agent.src.extractors.dbt import DbtExtractor
from collection_agent.src.extractors.sql import SqlCatalogExtractor
from collection_agent.src.extractors.query_logs import QueryLogExtractor
from collection_agent.src.extractors.openlineage import OpenLineageExtractor
from collection_agent.src.transform.graph_builder import GraphBuilder
from collection_agent.src.transform.models import NodeType, EdgeType

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_graph_builder_dbt_ingestion():
    with open(FIXTURES_DIR / "dbt_manifest.json") as f:
        manifest_data = json.load(f)
    with open(FIXTURES_DIR / "dbt_catalog.json") as f:
        catalog_data = json.load(f)

    dbt_ext = DbtExtractor()
    manifest_nodes = dbt_ext.parse_manifest(manifest_data)
    catalog_nodes = dbt_ext.parse_catalog(catalog_data)
    lineage_edges = dbt_ext.extract_lineage(manifest_data)

    builder = GraphBuilder()
    builder.ingesting_dbt(manifest_nodes, catalog_nodes, lineage_edges)
    payload = builder.to_payload()

    assert len(payload.nodes) > 0
    assert len(payload.edges) == 13

    node_types = {n.type for n in payload.nodes}
    assert NodeType.DATASET in node_types
    assert NodeType.COLUMN in node_types


def test_graph_builder_sql_ingestion():
    with open(FIXTURES_DIR / "sql_information_schema.json") as f:
        schema_data = json.load(f)

    sql_ext = SqlCatalogExtractor()
    tables = sql_ext.parse_tables(schema_data["tables"])
    columns = sql_ext.parse_columns(schema_data["columns"])
    fks = sql_ext.parse_foreign_keys(schema_data["foreign_keys"])

    builder = GraphBuilder()
    builder.ingesting_sql_catalog(tables, columns, fks)
    payload = builder.to_payload()

    assert len(payload.nodes) == 12  # 3 tables + 9 columns
    assert len(payload.edges) == 10  # 9 BELONGS_TO + 1 JOINS_WITH
    assert EdgeType.JOINS_WITH in {e.type for e in payload.edges}


def test_graph_builder_query_logs_ingestion():
    with open(FIXTURES_DIR / "query_logs.json") as f:
        query_data = json.load(f)

    ql_ext = QueryLogExtractor()
    access_edges = ql_ext.parse_user_access(query_data)
    join_edges = ql_ext.parse_join_predicates(query_data)

    builder = GraphBuilder()
    builder.ingesting_query_logs(access_edges, join_edges)
    payload = builder.to_payload()

    users = [n for n in payload.nodes if n.type in (NodeType.USER, NodeType.TEAM)]
    assert len(users) == 2  # alice_analyst and bob_engineer
    consumed_edges = [e for e in payload.edges if e.type == EdgeType.CONSUMED_BY]
    assert len(consumed_edges) >= 2


def test_graph_builder_openlineage_ingestion():
    with open(FIXTURES_DIR / "openlineage_event.json") as f:
        event_data = json.load(f)

    ol_ext = OpenLineageExtractor()
    parsed_event = ol_ext.parse_event(event_data)

    builder = GraphBuilder()
    builder.ingesting_openlineage(parsed_event)
    payload = builder.to_payload()

    assert len(payload.nodes) == 3  # 1 pipeline + 2 datasets
    assert len(payload.edges) == 2


def test_column_alias_resolution_for_unqualified_names():
    from collection_agent.src.transform.models import DatasetNode, ColumnNode, Edge, EdgeType

    builder = GraphBuilder()
    ds = DatasetNode(id="PROD_DB.PUBLIC.USERS", name="USERS", schema_name="PUBLIC", database="PROD_DB")
    col = ColumnNode(id="PROD_DB.PUBLIC.USERS.ID", name="ID", dataset_id="PROD_DB.PUBLIC.USERS")

    builder.add_node(ds)
    builder.add_node(col)

    # Edge referencing short alias USERS.ID
    builder.add_edge(Edge(source_id="USERS.ID", target_id="PROD_DB.PUBLIC.TRANSACTIONS.USER_ID", type=EdgeType.JOINS_WITH))

    payload = builder.to_payload()
    node_ids = {n.id for n in payload.nodes}

    # Must resolve USERS.ID -> PROD_DB.PUBLIC.USERS.ID without creating duplicate USERS.ID node
    assert "USERS.ID" not in node_ids
    assert "PROD_DB.PUBLIC.USERS.ID" in node_ids
    assert payload.edges[0].source_id == "PROD_DB.PUBLIC.USERS.ID"

