import re
from typing import Dict, Any, List


class QueryLogExtractor:
    """
    Extractor for operational query logs (QUERY_HISTORY / ACCESS_HISTORY).
    Infers user dataset access and column-level joins.
    """

    def parse_user_access(self, query_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        access_edges = []
        for row in query_rows:
            user = row.get("user_name")
            query_text = row.get("query_text", "")
            # Simple regex search for FROM/JOIN tables in SQL text
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
        join_edges = []
        for row in query_rows:
            query_text = row.get("query_text", "")
            # Find equality join conditions e.g. a.col1 = b.col2
            joins = re.findall(r'([a-zA-Z0-9_\.]+\.[a-zA-Z0-9_]+)\s*=\s*([a-zA-Z0-9_\.]+\.[a-zA-Z0-9_]+)', query_text)
            for col1, col2 in joins:
                join_edges.append({
                    "source": col1,
                    "target": col2,
                    "type": "JOINS_WITH",
                    "query_id": row.get("query_id"),
                })
        return join_edges
