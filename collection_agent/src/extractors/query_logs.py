import re
from typing import Dict, Any, List


class QueryLogExtractor:
    """
    Extractor for operational database query logs (`QUERY_HISTORY` / `ACCESS_HISTORY`).

    Parses SQL execution logs to extract user table access events (`CONSUMED_BY`)
    and column-level join predicates (`JOINS_WITH`).
    """

    def parse_user_access(self, query_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parses query execution records to extract user dataset consumption patterns.

        :param query_rows: List of query log dictionary records.
        :return: List of access edge dictionaries linking dataset tables to user IDs (`user:<username>`).
        """
        access_edges = []
        for row in query_rows:
            user = row.get("user_name")
            query_text = row.get("query_text", "")
            # Extract table references following FROM or JOIN keywords
            tables = re.findall(r'(?:FROM|JOIN)\s+([a-zA-Z0-9_\.]+)', query_text, re.IGNORECASE)
            for tbl in set(tables):
                access_edges.append({
                    "source": tbl,
                    "target": f"user:{user}",
                    "type": "CONSUMED_BY",
                    "query_id": row.get("query_id"),
                    "execution_time": row.get("start_time"),
                })
        return access_edges

    def parse_join_predicates(self, query_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Parses query text to extract explicit column equality join conditions (e.g., `t1.id = t2.user_id`).

        :param query_rows: List of query log dictionary records.
        :return: List of join edge dictionaries (`JOINS_WITH`) linking column identifiers.
        """
        join_edges = []
        for row in query_rows:
            query_text = row.get("query_text", "")
            # Match equality join predicates (e.g., table1.col1 = table2.col2)
            joins = re.findall(r'([a-zA-Z0-9_\.]+\.[a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_\.]+\.[a-zA-Z0-9_]+)', query_text)
            for col1, col2 in joins:
                join_edges.append({
                    "source": col1,
                    "target": col2,
                    "type": "JOINS_WITH",
                    "query_id": row.get("query_id"),
                })
        return join_edges
