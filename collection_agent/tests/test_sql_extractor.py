import json
from pathlib import Path
from collection_agent.src.extractors.sql import SqlCatalogExtractor

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_sql_parse_tables():
    with open(FIXTURES_DIR / "sql_information_schema.json") as f:
        schema_data = json.load(f)

    extractor = SqlCatalogExtractor()
    tables = extractor.parse_tables(schema_data["tables"])

    assert len(tables) == 3
    users_tbl = next(t for t in tables if t["table_name"] == "USERS")
    assert users_tbl["id"] == "PROD_DB.PUBLIC.USERS"
    assert users_tbl["type"] == "Dataset"
    prod_tbl = next(t for t in tables if t["table_name"] == "PRODUCTS")
    assert prod_tbl["id"] == "PROD_DB.PUBLIC.PRODUCTS"


def test_sql_parse_columns():
    with open(FIXTURES_DIR / "sql_information_schema.json") as f:
        schema_data = json.load(f)

    extractor = SqlCatalogExtractor()
    columns = extractor.parse_columns(schema_data["columns"])

    assert len(columns) == 10
    email_col = next(c for c in columns if c["column_name"] == "EMAIL")
    assert email_col["id"] == "PROD_DB.PUBLIC.USERS.EMAIL"
    assert email_col["data_type"] == "VARCHAR"
    assert email_col["is_nullable"] is True

    prod_cols = [c for c in columns if c["dataset_id"] == "PROD_DB.PUBLIC.PRODUCTS"]
    assert len(prod_cols) == 6


def test_sql_parse_foreign_keys():
    with open(FIXTURES_DIR / "sql_information_schema.json") as f:
        schema_data = json.load(f)

    extractor = SqlCatalogExtractor()
    fk_edges = extractor.parse_foreign_keys(schema_data["foreign_keys"])

    assert len(fk_edges) == 2
    fk = next(e for e in fk_edges if e["constraint_name"] == "FK_TXN_USERS")
    assert fk["source"] == "PROD_DB.PUBLIC.TRANSACTIONS.USER_ID"
    assert fk["target"] == "PROD_DB.PUBLIC.USERS.ID"
    assert fk["type"] == "JOINS_WITH"
    assert fk["constraint_name"] == "FK_TXN_USERS"
