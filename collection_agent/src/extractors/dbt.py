import json
from typing import Dict, Any, List


class DbtExtractor:
    """
    Extractor for dbt compilation artifacts (manifest.json and catalog.json).
    """

    def parse_manifest(self, manifest_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        nodes = []
        raw_nodes = manifest_data.get("nodes", {})
        
        for node_id, node_info in raw_nodes.items():
            if node_info.get("resource_type") in ("model", "seed", "source"):
                node_type = "Dataset" if node_info.get("resource_type") in ("model", "seed", "source") else "Pipeline"
                extracted_node = {
                    "id": node_id,
                    "type": node_type,
                    "name": node_info.get("name"),
                    "schema": node_info.get("schema"),
                    "database": node_info.get("database"),
                    "description": node_info.get("description", ""),
                    "meta": node_info.get("meta", {}),
                    "columns": list(node_info.get("columns", {}).keys()),
                    "depends_on": node_info.get("depends_on", {}).get("nodes", []),
                }
                nodes.append(extracted_node)
        return nodes

    def parse_catalog(self, catalog_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        catalog_nodes = []
        raw_nodes = catalog_data.get("nodes", {})
        
        for node_id, node_info in raw_nodes.items():
            metadata = node_info.get("metadata", {})
            columns_info = node_info.get("columns", {})
            
            catalog_node = {
                "id": node_id,
                "type": metadata.get("type"),
                "database": metadata.get("database"),
                "schema": metadata.get("schema"),
                "name": metadata.get("name"),
                "owner": metadata.get("owner"),
                "columns": [
                    {
                        "name": col_name,
                        "type": col_data.get("type"),
                        "comment": col_data.get("comment", ""),
                        "index": col_data.get("index"),
                    }
                    for col_name, col_data in columns_info.items()
                ],
            }
            catalog_nodes.append(catalog_node)
        return catalog_nodes

    def extract_lineage(self, manifest_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        edges = []
        raw_nodes = manifest_data.get("nodes", {})
        
        for node_id, node_info in raw_nodes.items():
            depends_on = node_info.get("depends_on", {}).get("nodes", [])
            for dep_id in depends_on:
                edges.append({
                    "source": dep_id,
                    "target": node_id,
                    "type": "DERIVED_FROM",
                })
        return edges
