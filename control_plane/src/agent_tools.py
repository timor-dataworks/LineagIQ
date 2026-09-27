import os

from control_plane.src.config import resolve_data_path
from control_plane.src.prompt_synthesizer import PromptSynthesizer
from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.services.http_client import post_json


class LineagIQGraphRAGClient:
    """Client for interacting with LineagIQ Control Plane directly in-process or via REST API.

    Provides methods to query blast radius and semantic asset discovery prompts for
    Agentic AI integration workflows.

    Args:
        base_url: Base URL endpoint for LineagIQ Control Plane REST API.
            Defaults to environment variable `LINEAGIQ_CONTROL_PLANE_URL` or `http://localhost:8000`.
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or os.getenv("LINEAGIQ_CONTROL_PLANE_URL", "http://localhost:8000")

    def get_blast_radius_prompt(
        self,
        node_id: str,
        max_depth: int = 5,
    ) -> str:
        """Queries downstream blast radius and returns a high-context GraphRAG prompt.

        Attempts in-process DuckDB query if DATA_PATH exists locally, or falls back to REST API.

        Args:
            node_id: Unique asset identifier for target node.
            max_depth: Maximum lineage traversal depth. Defaults to 5.

        Returns:
            Synthesized GraphRAG prompt string ready for LLM prompt context injection.
        """
        try:
            data_path = resolve_data_path()
            if os.path.exists(data_path):
                engine = DuckDBQueryEngine(data_base_path=data_path)
                res = engine.get_downstream_blast_radius(start_node_id=node_id, max_depth=max_depth)
                synthesizer = PromptSynthesizer()
                return synthesizer.synthesize_blast_radius_prompt(
                    start_node=res["root_node"],
                    impacted_nodes=res["impacted_nodes"],
                    edges=res["edges"],
                )
        except Exception:
            pass

        url = f"{self.base_url}/api/v1/blast-radius"
        res, err = post_json(
            url,
            payload={"node_id": node_id, "max_depth": max_depth},
            timeout=10,
        )
        if err or not res:
            raise RuntimeError(f"Blast radius request failed: {err}")
        return res["synthesized_prompt"]

    def get_discovery_prompt(
        self,
        query: str,
        top_k: int = 5,
    ) -> str:
        """Queries semantic data discovery and returns a high-context GraphRAG prompt.

        Attempts in-process DuckDB query if DATA_PATH exists locally, or falls back to REST API.

        Args:
            query: Natural language asset search query string.
            top_k: Maximum number of top matching assets to retrieve. Defaults to 5.

        Returns:
            Synthesized GraphRAG discovery prompt string ready for LLM prompt context injection.
        """
        try:
            data_path = resolve_data_path()
            if os.path.exists(data_path):
                engine = DuckDBQueryEngine(data_base_path=data_path)
                matched_nodes = engine.search_semantic_assets(query_text=query, top_k=top_k)
                synthesizer = PromptSynthesizer()
                return synthesizer.synthesize_discovery_prompt(query_text=query, matched_nodes=matched_nodes)
        except Exception:
            pass

        url = f"{self.base_url}/api/v1/discovery"
        res, err = post_json(
            url,
            payload={"query": query, "top_k": top_k},
            timeout=10,
        )
        if err or not res:
            raise RuntimeError(f"Discovery request failed: {err}")
        return res["synthesized_prompt"]

    def get_time_travel_diff_prompt(
        self,
        node_id: str,
        timestamp_t1: str,
        timestamp_t2: str,
    ) -> str:
        """Queries historical schema and lineage diff between T1 and T2 and returns GraphRAG prompt.

        Args:
            node_id: Target asset identifier.
            timestamp_t1: Initial ISO 8601 timestamp string.
            timestamp_t2: Subsequent ISO 8601 timestamp string.

        Returns:
            Synthesized GraphRAG prompt string ready for LLM prompt context injection.
        """
        try:
            data_path = resolve_data_path()
            if os.path.exists(data_path):
                engine = DuckDBQueryEngine(data_base_path=data_path)
                diff_res = engine.get_schema_time_travel_diff(
                    start_node_id=node_id, timestamp_t1=timestamp_t1, timestamp_t2=timestamp_t2
                )
                synthesizer = PromptSynthesizer()
                return synthesizer.synthesize_time_travel_diff_prompt(
                    node_id=node_id, timestamp_t1=timestamp_t1, timestamp_t2=timestamp_t2, diff_result=diff_res
                )
        except Exception:
            pass

        url = f"{self.base_url}/api/v1/time-travel/diff"
        res, err = post_json(
            url,
            payload={
                "node_id": node_id,
                "timestamp_t1": timestamp_t1,
                "timestamp_t2": timestamp_t2,
            },
            timeout=10,
        )
        if err or not res:
            raise RuntimeError(f"Time travel diff request failed: {err}")
        return res["synthesized_prompt"]


# Standalone Helper Functions / Agent Tools
def get_dataset_blast_radius(
    dataset_id: str,
    max_depth: int = 5,
) -> str:
    """Agentic Retriever Tool: Calculates operational downstream blast radius for a data asset.

    Args:
        dataset_id: Target dataset node ID to assess downstream impact.
        max_depth: Maximum lineage traversal depth. Defaults to 5.

    Returns:
        Structured graph lineage context formatted for LLM evaluation.
    """
    client = LineagIQGraphRAGClient()
    return client.get_blast_radius_prompt(
        node_id=dataset_id,
        max_depth=max_depth,
    )


def search_enterprise_data_catalog(
    query: str,
    top_k: int = 5,
) -> str:
    """Agentic Retriever Tool: Searches enterprise datasets, columns, and pipelines.

    Args:
        query: Natural language query for catalog search.
        top_k: Maximum number of matched assets to return. Defaults to 5.

    Returns:
        Matched asset definitions and schema details formatted for LLM discovery.
    """
    client = LineagIQGraphRAGClient()
    return client.get_discovery_prompt(
        query=query,
        top_k=top_k,
    )


def get_lineage_time_travel_diff(
    node_id: str,
    timestamp_t1: str,
    timestamp_t2: str,
) -> str:
    """Agentic Retriever Tool: Analyzes historical schema drift & lineage diff between T1 and T2.

    Args:
        node_id: Target dataset or column node ID under evaluation.
        timestamp_t1: Initial ISO 8601 timestamp string (e.g. '2026-09-08T00:00:00Z').
        timestamp_t2: Subsequent ISO 8601 timestamp string (e.g. '2026-09-08T10:00:00Z').

    Returns:
        Formatted GraphRAG prompt detailing schema drift, added/deleted columns, and lineage shifts.
    """
    client = LineagIQGraphRAGClient()
    return client.get_time_travel_diff_prompt(
        node_id=node_id,
        timestamp_t1=timestamp_t1,
        timestamp_t2=timestamp_t2,
    )
