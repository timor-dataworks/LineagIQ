from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Path as FastPath, Query

from control_plane.src.config import resolve_data_path
from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer
from control_plane.src.schemas import (
    BlastRadiusRequest,
    RootCauseRequest,
    DiscoveryRequest,
    TimeTravelDiffRequest,
)

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}", tags=["Lineage & Graph"])


@router.get("/graph")
def get_tenant_graph(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    data_path: Optional[str] = Query(default=None, description="Local or S3 data path"),
    as_of: Optional[str] = Query(default=None, description="Optional ISO 8601 timestamp for historical time travel"),
) -> Dict[str, Any]:
    """Returns all nodes and edges for tenant graph visualization.

    Args:
        tenant_id: Unique tenant identifier string.
        data_path: Optional custom path to tenant Parquet dataset.
        as_of: Optional ISO 8601 timestamp string for historical time travel.

    Returns:
        Full knowledge graph structure containing 'nodes' and 'edges'.
    """
    engine = DuckDBQueryEngine(data_base_path=resolve_data_path(tenant_id, data_path))
    return engine.get_full_graph(as_of=as_of)


@router.get("/timeline")
def get_tenant_timeline(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    data_path: Optional[str] = Query(default=None, description="Local or S3 data path"),
) -> Dict[str, Any]:
    """Returns available commit timestamps from Delta Lake logs for UI timeline scrubbing.

    Args:
        tenant_id: Unique tenant identifier string.
        data_path: Optional custom path to tenant data.

    Returns:
        Dictionary containing list of available commit timestamp objects.
    """
    engine = DuckDBQueryEngine(data_base_path=resolve_data_path(tenant_id, data_path))
    timestamps = engine.get_available_timestamps()
    return {"tenant_id": tenant_id, "timestamps_count": len(timestamps), "timestamps": timestamps}


@router.post("/blast-radius")
def calculate_blast_radius(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: Optional[BlastRadiusRequest] = None,
) -> Dict[str, Any]:
    """Calculates downstream operational blast radius for a target asset node.

    Args:
        tenant_id: Unique tenant identifier string.
        request: BlastRadiusRequest containing node_id and optional max_depth/data_path/as_of.

    Returns:
        Impact analysis dictionary including target_node, impacted_nodes, edges, and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="BlastRadiusRequest body is required")
    data_base = resolve_data_path(tenant_id, request.data_path)
    engine = DuckDBQueryEngine(data_base_path=data_base)
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
        "tenant_id": tenant_id,
        "target_node": result["root_node"],
        "impacted_nodes_count": len(result["impacted_nodes"]),
        "depth_reached": result.get("depth_reached", 0),
        "impacted_nodes": result["impacted_nodes"],
        "edges": result["edges"],
        "synthesized_prompt": prompt,
    }


@router.post("/root-cause")
def calculate_root_cause(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: Optional[RootCauseRequest] = None,
) -> Dict[str, Any]:
    """Calculates upstream root cause lineage starting from a target asset node.

    Args:
        tenant_id: Unique tenant identifier string.
        request: RootCauseRequest containing node_id and optional max_depth/data_path/as_of.

    Returns:
        Root cause analysis dictionary including target_node, upstream_nodes, edges, and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="RootCauseRequest body is required")
    data_base = resolve_data_path(tenant_id, request.data_path)
    engine = DuckDBQueryEngine(data_base_path=data_base)
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
        "tenant_id": tenant_id,
        "target_node": result["target_node"],
        "upstream_nodes_count": len(result["upstream_nodes"]),
        "depth_reached": result.get("depth_reached", 0),
        "upstream_nodes": result["upstream_nodes"],
        "edges": result["edges"],
        "synthesized_prompt": prompt,
    }


@router.post("/discovery")
def discover_semantic_assets(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: Optional[DiscoveryRequest] = None,
) -> Dict[str, Any]:
    """Executes semantic search over lineage assets and synthesizes a discovery prompt.

    Args:
        tenant_id: Unique tenant identifier string.
        request: DiscoveryRequest containing natural language query, top_k, optional data_path, and as_of.

    Returns:
        Discovery result dictionary containing query, matched_nodes, and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="DiscoveryRequest body is required")
    data_base = resolve_data_path(tenant_id, request.data_path)
    engine = DuckDBQueryEngine(data_base_path=data_base)
    matched_nodes = engine.search_semantic_assets(
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
        "tenant_id": tenant_id,
        "query": request.query,
        "matched_nodes_count": len(matched_nodes),
        "matched_nodes": matched_nodes,
        "synthesized_prompt": prompt,
    }


@router.post("/time-travel/diff")
def calculate_time_travel_diff(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: Optional[TimeTravelDiffRequest] = None,
) -> Dict[str, Any]:
    """Calculates schema drift and lineage diff between two historical ISO 8601 timestamps.

    Args:
        tenant_id: Unique tenant identifier string.
        request: TimeTravelDiffRequest containing node_id, timestamp_t1, timestamp_t2.

    Returns:
        Diff dictionary containing added/removed nodes/edges and synthesized prompt.
    """
    if not request:
        raise HTTPException(status_code=400, detail="TimeTravelDiffRequest body is required")
    data_base = resolve_data_path(tenant_id, request.data_path)
    engine = DuckDBQueryEngine(data_base_path=data_base)
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
        "tenant_id": tenant_id,
        "diff": diff_result,
        "synthesized_prompt": prompt,
    }
