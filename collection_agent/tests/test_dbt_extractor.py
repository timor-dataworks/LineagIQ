import json
from pathlib import Path
from collection_agent.src.extractors.dbt import DbtExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_dbt_parse_manifest():
    with open(FIXTURES_DIR / "dbt_manifest.json") as f:
        manifest_data = json.load(f)

    extractor = DbtExtractor()
    nodes = extractor.parse_manifest(manifest_data)

    assert len(nodes) == 2
    stg_cust = next(n for n in nodes if n["name"] == "stg_customers")
    assert stg_cust["type"] == "Dataset"
    assert stg_cust["database"] == "raw_db"
    assert stg_cust["schema"] == "analytics"
    assert "customer_id" in stg_cust["columns"]
    assert "source.jaffle_shop.raw_customers" in stg_cust["depends_on"]


def test_dbt_parse_catalog():
    with open(FIXTURES_DIR / "dbt_catalog.json") as f:
        catalog_data = json.load(f)

    extractor = DbtExtractor()
    catalog_nodes = extractor.parse_catalog(catalog_data)

    assert len(catalog_nodes) == 1
    node = catalog_nodes[0]
    assert node["name"] == "stg_customers"
    assert node["owner"] == "analytics_admin"
    assert len(node["columns"]) == 2
    assert node["columns"][0]["name"] == "customer_id"
    assert node["columns"][0]["type"] == "NUMBER"


def test_dbt_extract_lineage():
    with open(FIXTURES_DIR / "dbt_manifest.json") as f:
        manifest_data = json.load(f)

    extractor = DbtExtractor()
    edges = extractor.extract_lineage(manifest_data)

    assert len(edges) == 2
    derived_edge = next(e for e in edges if e["target"] == "model.jaffle_shop.orders")
    assert derived_edge["source"] == "model.jaffle_shop.stg_customers"
    assert derived_edge["type"] == "DERIVED_FROM"
