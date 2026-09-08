import os
from typing import Optional
import requests

from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer


class LineagIQGraphRAGClient:
    """Client for interacting with LineagIQ Control Plane directly in-process or via REST API.

    Provides methods to query blast radius and semantic asset discovery prompts for
    Agentic AI integration workflows.

    Args:
        base_url: Base URL endpoint for LineagIQ Control Plane REST API.
            Defaults to environment variable `LINEAGIQ_CONTROL_PLANE_URL` or `http://localhost:8000`.
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
        """Queries downstream blast radius and returns a high-context GraphRAG prompt.

        Attempts in-process DuckDB query if data_path exists locally, or falls back to REST API.

        Args:
            tenant_id: Tenant Identifier string.
            node_id: Unique asset identifier for target node.
            max_depth: Maximum lineage traversal depth. Defaults to 5.
            data_path: Optional local path to tenant Parquet dataset directory.

        Returns:
            Synthesized GraphRAG prompt string ready for LLM prompt context injection.
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
        """Queries semantic data discovery and returns a high-context GraphRAG prompt.

        Attempts in-process DuckDB query if data_path exists locally, or falls back to REST API.

        Args:
            tenant_id: Tenant Identifier string.
            query: Natural language asset search query string.
            top_k: Maximum number of top matching assets to retrieve. Defaults to 5.
            data_path: Optional local path to tenant Parquet dataset directory.

        Returns:
            Synthesized GraphRAG discovery prompt string ready for LLM prompt context injection.
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

    def get_time_travel_diff_prompt(
        self,
        tenant_id: str,
        node_id: str,
        timestamp_t1: str,
        timestamp_t2: str,
        data_path: Optional[str] = None,
    ) -> str:
        """Queries historical schema and lineage diff between T1 and T2 and returns GraphRAG prompt.

        Args:
            tenant_id: Tenant Identifier string.
            node_id: Target asset identifier.
            timestamp_t1: Initial ISO 8601 timestamp string.
            timestamp_t2: Subsequent ISO 8601 timestamp string.
            data_path: Optional local path to tenant dataset directory.

        Returns:
            Synthesized GraphRAG prompt string ready for LLM prompt context injection.
        """
        if data_path and os.path.exists(data_path):
            engine = DuckDBQueryEngine(data_base_path=data_path)
            diff_res = engine.get_schema_time_travel_diff(
                start_node_id=node_id, timestamp_t1=timestamp_t1, timestamp_t2=timestamp_t2
            )
            synthesizer = PromptSynthesizer()
            return synthesizer.synthesize_time_travel_diff_prompt(
                node_id=node_id, timestamp_t1=timestamp_t1, timestamp_t2=timestamp_t2, diff_result=diff_res
            )

        url = f"{self.base_url}/api/v1/tenants/{tenant_id}/time-travel/diff"
        response = requests.post(
            url,
            json={
                "node_id": node_id,
                "timestamp_t1": timestamp_t1,
                "timestamp_t2": timestamp_t2,
                "data_path": data_path,
            },
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
    """Agentic Retriever Tool: Calculates operational downstream blast radius for a data asset.

    Args:
        tenant_id: Tenant Identifier string.
        dataset_id: Target dataset node ID to assess downstream impact.
        max_depth: Maximum lineage traversal depth. Defaults to 5.
        data_path: Optional local path to tenant Parquet dataset directory.

    Returns:
        Structured graph lineage context formatted for LLM evaluation.
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
    """Agentic Retriever Tool: Searches enterprise datasets, columns, and pipelines.

    Args:
        tenant_id: Tenant Identifier string.
        query: Natural language query for catalog search.
        top_k: Maximum number of matched assets to return. Defaults to 5.
        data_path: Optional local path to tenant Parquet dataset directory.

    Returns:
        Matched asset definitions and schema details formatted for LLM discovery.
    """
    client = LineagIQGraphRAGClient()
    return client.get_discovery_prompt(
        tenant_id=tenant_id,
        query=query,
        top_k=top_k,
        data_path=data_path,
    )


def get_lineage_time_travel_diff(
    tenant_id: str,
    node_id: str,
    timestamp_t1: str,
    timestamp_t2: str,
    data_path: Optional[str] = None,
) -> str:
    """Agentic Retriever Tool: Analyzes historical schema drift & lineage diff between T1 and T2.

    Args:
        tenant_id: Tenant Identifier string.
        node_id: Target dataset or column node ID under evaluation.
        timestamp_t1: Initial ISO 8601 timestamp string (e.g. '2026-09-08T00:00:00Z').
        timestamp_t2: Subsequent ISO 8601 timestamp string (e.g. '2026-09-08T10:00:00Z').
        data_path: Optional local path to tenant dataset directory.

    Returns:
        Formatted GraphRAG prompt detailing schema drift, added/deleted columns, and lineage shifts.
    """
    client = LineagIQGraphRAGClient()
    return client.get_time_travel_diff_prompt(
        tenant_id=tenant_id,
        node_id=node_id,
        timestamp_t1=timestamp_t1,
        timestamp_t2=timestamp_t2,
        data_path=data_path,
    )


