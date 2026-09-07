import json
from pathlib import Path
from collection_agent.src.extractors.openlineage import OpenLineageExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_openlineage_parse_event():
    with open(FIXTURES_DIR / "openlineage_event.json") as f:
        event_data = json.load(f)

    extractor = OpenLineageExtractor()
    parsed = extractor.parse_event(event_data)

    assert parsed["pipeline_id"] == "airflow_prod.etl_orders_daily"
    assert parsed["event_type"] == "COMPLETE"
    assert parsed["run_id"] == "4c9e830e-5407-4f6c-8291-a1b7e3f89021"
    assert "snowflake://account.region.raw_db.sales.orders_raw" in parsed["inputs"]
    assert "snowflake://account.region.analytics_db.sales.fct_orders" in parsed["outputs"]

    edges = parsed["edges"]
    assert len(edges) == 2
    consumed = next(e for e in edges if e["type"] == "CONSUMED_BY")
    produced = next(e for e in edges if e["type"] == "PRODUCED_BY")
    assert consumed["source"] == "airflow_prod.etl_orders_daily"
    assert produced["source"] == "airflow_prod.etl_orders_daily"
