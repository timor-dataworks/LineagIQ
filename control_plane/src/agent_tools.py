import os
import requests
from typing import Dict, Any, Optional

from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer


class LineagIQGraphRAGClient:
    """
    Client for interacting with LineagIQ Control Plane directly in-process
    or via REST API for Agentic AI workflows.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv("LINEAGIQ_CONTROL_PLANE_URL", "http://localhost:8000")

    def get_blast_radius_prompt(
        self,
        tenant_id: str,
        node_id: str,
        max_depth: int = 5,
        data_path: Optional[str] = None,
    ) -> str:
        """
        Queries downstream blast radius and returns a high-context GraphRAG prompt.
        Attempts in-process DuckDB query if data_path exists locally, or falls back to REST API.
        """
        if data_path and os.path.exists(data_path):
            engine = DuckDBQueryEngine(data_base_path=data_path)
            res = engine.get_downstream_blast_radius(start_node_id=node_id, max_depth=max_depth)
            synthesizer = PromptSynthesizer()
            return synthesizer.synthesize_blast_radius_prompt(
                start_node=res["root_node"],
                impacted_nodes=res["impacted_nodes"],
                edges=res["edges"],
            )

        url = f"{self.base_url}/api/v1/tenants/{tenant_id}/blast-radius"
        response = requests.post(
            url,
            json={"node_id": node_id, "max_depth": max_depth, "data_path": data_path},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["synthesized_prompt"]

    def get_discovery_prompt(
        self,
        tenant_id: str,
        query: str,
        top_k: int = 5,
        data_path: Optional[str] = None,
    ) -> str:
        """
        Queries semantic data discovery and returns a high-context GraphRAG prompt.
        Attempts in-process DuckDB query if data_path exists locally, or falls back to REST API.
        """
        if data_path and os.path.exists(data_path):
            engine = DuckDBQueryEngine(data_base_path=data_path)
            matched_nodes = engine.search_semantic_assets(query_text=query, top_k=top_k)
            synthesizer = PromptSynthesizer()
            return synthesizer.synthesize_discovery_prompt(query_text=query, matched_nodes=matched_nodes)

        url = f"{self.base_url}/api/v1/tenants/{tenant_id}/discovery"
        response = requests.post(
            url,
            json={"query": query, "top_k": top_k, "data_path": data_path},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["synthesized_prompt"]


# Standalone Helper Functions / Agent Tools
def get_dataset_blast_radius(
    tenant_id: str,
    dataset_id: str,
    max_depth: int = 5,
    data_path: Optional[str] = None,
) -> str:
    """
    Agentic Retriever Tool: Calculates operational downstream blast radius for a data asset.
    Returns structured graph lineage context formatted for LLM evaluation.
    """
    client = LineagIQGraphRAGClient()
    return client.get_blast_radius_prompt(
        tenant_id=tenant_id,
        node_id=dataset_id,
        max_depth=max_depth,
        data_path=data_path,
    )


def search_enterprise_data_catalog(
    tenant_id: str,
    query: str,
    top_k: int = 5,
    data_path: Optional[str] = None,
) -> str:
    """
    Agentic Retriever Tool: Searches enterprise datasets, columns, and pipelines.
    Returns matched asset definitions and schema details formatted for LLM discovery.
    """
    client = LineagIQGraphRAGClient()
    return client.get_discovery_prompt(
        tenant_id=tenant_id,
        query=query,
        top_k=top_k,
        data_path=data_path,
    )
