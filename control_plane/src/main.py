import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel, Field

from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer

app = FastAPI(
    title="LineagIQ Control Plane & GraphRAG API",
    description="Multi-tenant GraphRAG query engine over S3 Parquet and LanceDB indices.",
    version="1.0.0",
)


class BlastRadiusRequest(BaseModel):
    node_id: str = Field(..., description="Target node ID for blast radius analysis")
    max_depth: int = Field(default=5, ge=1, le=10, description="Max lineage traversal depth")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")


class DiscoveryRequest(BaseModel):
    query: str = Field(..., description="Natural language semantic search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Max matched assets to return")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")


@app.get("/healthz")
def health_check():
    return {"status": "ok", "service": "lineagiq-control-plane"}


@app.post("/api/v1/tenants/{tenant_id}/blast-radius")
def calculate_blast_radius(
    tenant_id: str = Path(..., description="Tenant Identifier"),
    request: BlastRadiusRequest = None,
):
    data_base = request.data_path or os.getenv("TENANT_DATA_DIR", f"/tmp/tenants/{tenant_id}")
    
    engine = DuckDBQueryEngine(data_base_path=data_base)
    result = engine.get_downstream_blast_radius(
        start_node_id=request.node_id,
        max_depth=request.max_depth,
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
        "depth_reached": result["depth_reached"],
        "impacted_nodes": result["impacted_nodes"],
        "edges": result["edges"],
        "synthesized_prompt": prompt,
    }


@app.post("/api/v1/tenants/{tenant_id}/discovery")
def discover_semantic_assets(
    tenant_id: str = Path(..., description="Tenant Identifier"),
    request: DiscoveryRequest = None,
):
    data_base = request.data_path or os.getenv("TENANT_DATA_DIR", f"/tmp/tenants/{tenant_id}")

    engine = DuckDBQueryEngine(data_base_path=data_base)
    matched_nodes = engine.search_semantic_assets(
        query_text=request.query,
        top_k=request.top_k,
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
