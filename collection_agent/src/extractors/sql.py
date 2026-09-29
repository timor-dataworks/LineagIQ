from typing import Any


class SqlCatalogExtractor:
    """
    Extractor for SQL `INFORMATION_SCHEMA` metadata, including tables, views, columns, and foreign key constraints.
    """

    def parse_tables(self, table_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Parses `INFORMATION_SCHEMA.TABLES` records into normalized dataset model dicts.

        :param table_rows: List of dictionary records from INFORMATION_SCHEMA.TABLES.
        :return: List of dataset dictionaries with fully-qualified catalog.schema.table IDs.
        """
        tables = []
        for row in table_rows:
            cat = row.get("table_catalog", "")
            sch = row.get("table_schema", "")
            tbl = row.get("table_name", "")
            table_id = f"{cat}.{sch}.{tbl}".strip(".")
            tables.append(
                {
                    "id": table_id,
                    "type": "Dataset",
                    "table_catalog": row.get("table_catalog"),
                    "table_schema": row.get("table_schema"),
                    "table_name": row.get("table_name"),
                    "table_type": row.get("table_type", "BASE TABLE"),
                }
            )
        return tables

    def parse_columns(self, column_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Parses `INFORMATION_SCHEMA.COLUMNS` records into normalized column model dicts.

        :param column_rows: List of dictionary records from INFORMATION_SCHEMA.COLUMNS.
        :return: List of column dictionaries linked to parent dataset IDs.
        """
        columns = []
        for row in column_rows:
            cat = row.get("table_catalog", "")
            sch = row.get("table_schema", "")
            tbl = row.get("table_name", "")
            dataset_id = f"{cat}.{sch}.{tbl}".strip(".")
            col_name = row.get("column_name")
            columns.append(
                {
                    "id": f"{dataset_id}.{col_name}",
                    "type": "Column",
                    "dataset_id": dataset_id,
                    "column_name": col_name,
                    "data_type": row.get("data_type"),
                    "is_nullable": row.get("is_nullable") == "YES",
                    "ordinal_position": row.get("ordinal_position"),
                }
            )
        return columns

    def parse_foreign_keys(self, constraint_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Parses foreign key constraint records into column join relationship edges (`JOINS_WITH`).

        :param constraint_rows: List of foreign key constraint dictionary records.
        :return: List of edge dictionaries with `source`, `target`, and `constraint_name`.
        """
        edges = []
        for row in constraint_rows:
            fk_parts = [row.get(k) for k in ("fk_catalog", "fk_schema", "fk_table", "fk_column")]
            pk_parts = [row.get(k) for k in ("pk_catalog", "pk_schema", "pk_table", "pk_column")]
            source_col = ".".join(str(p) for p in fk_parts if p)
            target_col = ".".join(str(p) for p in pk_parts if p)
            if source_col and target_col:
                edges.append(
                    {
                        "source": source_col,
                        "target": target_col,
                        "type": "JOINS_WITH",
                        "constraint_name": row.get("constraint_name"),
                    }
                )
        return edges
