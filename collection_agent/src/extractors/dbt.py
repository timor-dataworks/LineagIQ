import json
from typing import Dict, Any, List


class DbtExtractor:
    """
    Extractor for dbt compilation and execution artifacts (`manifest.json` and `catalog.json`).

    Extracts models, seeds, sources, column attributes, and dbt graph lineage dependencies.
    """

    def parse_manifest(self, manifest_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parses dbt `manifest.json` data to extract dataset and pipeline model metadata.

        :param manifest_data: Loaded JSON contents of dbt manifest.json.
        :return: List of raw extracted node metadata dictionaries.
        """
        nodes = []
        raw_nodes = manifest_data.get("nodes", {})

        for node_id, node_info in raw_nodes.items():
            resource_type = node_info.get("resource_type")
            if resource_type in ("model", "seed", "source"):
                node_type = "Dataset"
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
        """
        Parses dbt `catalog.json` output to extract physical schema types and column definitions.

        :param catalog_data: Loaded JSON contents of dbt catalog.json.
        :return: List of catalog node dictionaries with detailed column metadata.
        """
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
        """
        Extracts parent-child dataset lineage dependencies (`depends_on.nodes`) from `manifest.json`.

        :param manifest_data: Loaded JSON contents of dbt manifest.json.
        :return: List of edge dictionaries with `source`, `target`, and `type` ('DERIVED_FROM').
        """
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
