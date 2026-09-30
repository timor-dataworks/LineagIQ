from typing import Any

from fastapi import APIRouter, HTTPException, Query

from control_plane.src.config import resolve_data_path
from control_plane.src.prompt_synthesizer import PromptSynthesizer
from control_plane.src.query_engine import QueryEngine
from control_plane.src.schemas import (
    BlastRadiusRequest,
    DiscoveryRequest,
    RootCauseRequest,
    TimeTravelDiffRequest,
)

router = APIRouter(prefix="/api/v1", tags=["Lineage & Graph"])


@router.get("/graph")
def get_graph(
    as_of: str | None = Query(default=None, description="Optional ISO 8601 timestamp for historical time travel"),
) -> dict[str, Any]:
    """Returns all nodes and edges for graph visualization.

    Args:
        as_of: Optional ISO 8601 timestamp string for historical time travel.

    Returns:
        Full knowledge graph structure containing 'nodes' and 'edges'.
    """
    engine = QueryEngine(data_base_path=resolve_data_path())
    return engine.get_full_graph(as_of=as_of)


@router.get("/timeline")
def get_timeline() -> dict[str, Any]:
    """Returns available commit timestamps from Delta Lake logs for UI timeline scrubbing.

    Returns:
        Dictionary containing list of available commit timestamp objects.
    """
    engine = QueryEngine(data_base_path=resolve_data_path())
    timestamps = engine.get_available_timestamps()
    return {"timestamps_count": len(timestamps), "timestamps": timestamps}


@router.post("/blast-radius")
def calculate_blast_radius(
    request: BlastRadiusRequest | None = None,
) -> dict[str, Any]:
    """Calculates downstream operational blast radius for a target asset node.

    Args:
        request: BlastRadiusRequest containing node_id and optional max_depth/as_of.

    Returns:
        Impact analysis dictionary including target_node, impacted_nodes, edges, and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="BlastRadiusRequest body is required")
    data_base = resolve_data_path()
    engine = QueryEngine(data_base_path=data_base)
    result = engine.get_downstream_blast_radius(
        start_node_id=request.node_id,
        max_depth=request.max_depth,
        as_of=request.as_of,
    )

    synthesizer = PromptSynthesizer()
    prompt = synthesizer.synthesize_blast_radius_prompt(
        start_node=result["root_node"],
        impacted_nodes=result["impacted_nodes"],
        edges=result["edges"],
    )

    return {
        "target_node": result["root_node"],
        "impacted_nodes_count": len(result["impacted_nodes"]),
        "depth_reached": result.get("depth_reached", 0),
        "impacted_nodes": result["impacted_nodes"],
        "edges": result["edges"],
        "synthesized_prompt": prompt,
    }


@router.post("/root-cause")
def calculate_root_cause(
    request: RootCauseRequest | None = None,
) -> dict[str, Any]:
    """Calculates upstream root cause lineage starting from a target asset node.

    Args:
        request: RootCauseRequest containing node_id and optional max_depth/as_of.

    Returns:
        Root cause analysis dictionary including target_node, upstream_nodes, edges, and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="RootCauseRequest body is required")
    data_base = resolve_data_path()
    engine = QueryEngine(data_base_path=data_base)
    result = engine.get_upstream_root_cause(
        start_node_id=request.node_id,
        max_depth=request.max_depth,
        as_of=request.as_of,
    )

    synthesizer = PromptSynthesizer()
    prompt = synthesizer.synthesize_root_cause_prompt(
        target_node=result["target_node"],
        upstream_nodes=result["upstream_nodes"],
        edges=result["edges"],
    )

    return {
        "target_node": result["target_node"],
        "upstream_nodes_count": len(result["upstream_nodes"]),
        "depth_reached": result.get("depth_reached", 0),
        "upstream_nodes": result["upstream_nodes"],
        "edges": result["edges"],
        "synthesized_prompt": prompt,
    }


@router.post("/discovery")
def discover_semantic_assets(
    request: DiscoveryRequest | None = None,
) -> dict[str, Any]:
    """Executes semantic search over lineage assets and synthesizes a discovery prompt.

    Args:
        request: DiscoveryRequest containing natural language query, top_k, and optional as_of.

    Returns:
        Discovery result dictionary containing query, matched_nodes, and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="DiscoveryRequest body is required")
    data_base = resolve_data_path()
    engine = QueryEngine(data_base_path=data_base)
    matched_nodes = engine.search(
        query_text=request.query,
        top_k=request.top_k,
        as_of=request.as_of,
    )

    synthesizer = PromptSynthesizer()
    prompt = synthesizer.synthesize_discovery_prompt(
        query_text=request.query,
        matched_nodes=matched_nodes,
    )

    return {
        "query": request.query,
        "matched_nodes_count": len(matched_nodes),
        "matched_nodes": matched_nodes,
        "synthesized_prompt": prompt,
    }


@router.post("/time-travel/diff")
def calculate_time_travel_diff(
    request: TimeTravelDiffRequest | None = None,
) -> dict[str, Any]:
    """Calculates schema drift and lineage diff between two historical ISO 8601 timestamps.

    Args:
        request: TimeTravelDiffRequest containing node_id, timestamp_t1, timestamp_t2.

    Returns:
        Diff dictionary containing added/removed nodes/edges and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="TimeTravelDiffRequest body is required")
    data_base = resolve_data_path()
    engine = QueryEngine(data_base_path=data_base)
    diff_result = engine.get_schema_time_travel_diff(
        start_node_id=request.node_id,
        timestamp_t1=request.timestamp_t1,
        timestamp_t2=request.timestamp_t2,
    )

    synthesizer = PromptSynthesizer()
    prompt = synthesizer.synthesize_time_travel_diff_prompt(
        node_id=request.node_id,
        timestamp_t1=request.timestamp_t1,
        timestamp_t2=request.timestamp_t2,
        diff_result=diff_result,
    )

    return {
        "diff": diff_result,
        "synthesized_prompt": prompt,
    }
