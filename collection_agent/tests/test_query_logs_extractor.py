import json
from pathlib import Path
from collection_agent.src.extractors.query_logs import QueryLogExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_query_logs_parse_user_access():
    with open(FIXTURES_DIR / "query_logs.json") as f:
        query_data = json.load(f)

    extractor = QueryLogExtractor()
    access_edges = extractor.parse_user_access(query_data)

    assert len(access_edges) >= 2
    alice_edges = [e for e in access_edges if e["target"] == "user:alice_analyst"]
    assert len(alice_edges) == 4
    accessed_tables = {e["source"] for e in alice_edges}
    assert "PROD_DB.PUBLIC.USERS" in accessed_tables
    assert "PROD_DB.PUBLIC.TRANSACTIONS" in accessed_tables
    assert "PROD_DB.PUBLIC.PRODUCTS" in accessed_tables


def test_query_logs_parse_join_predicates():
    with open(FIXTURES_DIR / "query_logs.json") as f:
        query_data = json.load(f)

    extractor = QueryLogExtractor()
    join_edges = extractor.parse_join_predicates(query_data)

    assert len(join_edges) == 2
    join_edge = next(e for e in join_edges if e["query_id"] == "q-1001")
    assert join_edge["source"] == "USERS.ID"
    assert join_edge["target"] == "TRANSACTIONS.USER_ID"
    assert join_edge["type"] == "JOINS_WITH"
