from typing import Dict, Any, List


class SqlCatalogExtractor:
    """
    Extractor for SQL INFORMATION_SCHEMA metadata tables and constraints.
    """

    def parse_tables(self, table_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        tables = []
        for row in table_rows:
            tables.append({
                "id": f"{row.get('table_catalog', '')}.{row.get('table_schema', '')}.{row.get('table_name', '')}",
                "type": "Dataset",
                "table_catalog": row.get("table_catalog"),
                "table_schema": row.get("table_schema"),
                "table_name": row.get("table_name"),
                "table_type": row.get("table_type", "BASE TABLE"),
            })
        return tables

    def parse_columns(self, column_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        columns = []
        for row in column_rows:
            dataset_id = f"{row.get('table_catalog', '')}.{row.get('table_schema', '')}.{row.get('table_name', '')}"
            col_name = row.get("column_name")
            columns.append({
                "id": f"{dataset_id}.{col_name}",
                "type": "Column",
                "dataset_id": dataset_id,
                "column_name": col_name,
                "data_type": row.get("data_type"),
                "is_nullable": row.get("is_nullable") == "YES",
                "ordinal_position": row.get("ordinal_position"),
            })
        return columns

    def parse_foreign_keys(self, constraint_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        edges = []
        for row in constraint_rows:
            source_col = f"{row.get('fk_catalog')}.{row.get('fk_schema')}.{row.get('fk_table')}.{row.get('fk_column')}"
            target_col = f"{row.get('pk_catalog')}.{row.get('pk_schema')}.{row.get('pk_table')}.{row.get('pk_column')}"
            edges.append({
                "source": source_col,
                "target": target_col,
                "type": "JOINS_WITH",
                "constraint_name": row.get("constraint_name"),
            })
        return edges
