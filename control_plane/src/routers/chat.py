import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Path as FastPath

from control_plane.src.config import resolve_data_path
from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer
from control_plane.src.schemas import ChatRequest
from control_plane.src.services.llm_service import call_llm

router = APIRouter(prefix="/api/v1/tenants/{tenant_id}", tags=["AI Assistant"])


def _find_target_node(nodes: List[Dict[str, Any]], msg_lower: str) -> Optional[Dict[str, Any]]:
    """Helper to locate target graph node referenced in user query string."""
    for n in nodes:
        if n.get("name", "").lower() in msg_lower or n.get("id", "").lower() in msg_lower:
            return n
    return nodes[0] if nodes else None


def _has_api_key_configured(request: ChatRequest) -> bool:
    """Helper to check whether any LLM API key is present in request or env."""
    return bool(
        request.openai_api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )


@router.post("/chat")
def lineage_ai_chat(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: Optional[ChatRequest] = None,
) -> Dict[str, Any]:
    """GraphRAG LLM Lineage Chat endpoint.

    Integrates DuckDB query engine, PromptSynthesizer, OpenAI, and Gemini LLM
    to answer interactive user queries regarding blast radius, root cause, and lineage graphs.

    Args:
        tenant_id: Unique tenant identifier string.
        request: ChatRequest payload containing user message and optional provider credentials.

    Returns:
        Chat response dictionary containing tenant_id, reply string, synthesized_prompt, and node details.
    """
    if not request or not request.message:
        raise HTTPException(status_code=400, detail="Message prompt is required")

    msg_lower = request.message.lower().strip()
    data_base = resolve_data_path(tenant_id, request.data_path)
    engine = DuckDBQueryEngine(data_base_path=data_base)
    synthesizer = PromptSynthesizer()

    # 1. Check if query asks about blast radius or downstream impact
    if any(k in msg_lower for k in ["blast", "impact", "affected", "break", "change", "downstream"]):
        full_graph = engine.get_full_graph(as_of=request.as_of)
        target_node = _find_target_node(full_graph.get("nodes", []), msg_lower)

        if target_node:
            result = engine.get_downstream_blast_radius(start_node_id=target_node["id"], max_depth=5, as_of=request.as_of)
            prompt = synthesizer.synthesize_blast_radius_prompt(
                start_node=result["root_node"],
                impacted_nodes=result["impacted_nodes"],
                edges=result["edges"],
            )

            llm_reply, llm_err = call_llm(
                prompt,
                openai_key=request.openai_api_key,
                openai_base_url=request.openai_base_url,
                openai_model=request.openai_model,
            )
            if llm_reply:
                reply = llm_reply
            elif llm_err and _has_api_key_configured(request):
                reply = f"<p>⚠️ <strong>LLM Provider Error</strong>:</p><p><code>{llm_err}</code></p><p>Please check your API key and model settings in the ⚙️ settings panel.</p>"
            else:
                impacted_names = [n["name"] for n in result["impacted_nodes"] if n["id"] != target_node["id"]]
                impacted_count = len(result["impacted_nodes"])
                reply = f"<p><strong>⚡ Blast Radius Analysis for <code>{target_node['name']}</code></strong>:</p>"
                reply += f"<p>Downstream impact affects <strong>{impacted_count}</strong> data assets across max traversal depth <strong>{result.get('depth_reached', 0)}</strong>.</p>"
                if impacted_names:
                    reply += "<p>Impacted downstream assets:</p><ul>" + "".join(f"<li><code>{name}</code></li>" for name in impacted_names) + "</ul>"
                else:
                    reply += "<p>No downstream assets are impacted.</p>"
                reply += "<p><em>💡 Tip: Set <code>OPENAI_API_KEY</code> or <code>GEMINI_API_KEY</code> environment variable to enable live LLM responses.</em></p>"

            return {
                "tenant_id": tenant_id,
                "reply": reply,
                "synthesized_prompt": prompt,
                "impacted_nodes": result["impacted_nodes"],
                "target_node_id": target_node["id"],
            }

    # 2. Check if query asks about root cause or upstream origin
    if any(k in msg_lower for k in ["root cause", "upstream", "why", "origin", "source", "parent"]):
        full_graph = engine.get_full_graph(as_of=request.as_of)
        target_node = _find_target_node(full_graph.get("nodes", []), msg_lower)

        if target_node:
            result = engine.get_upstream_root_cause(start_node_id=target_node["id"], max_depth=5, as_of=request.as_of)
            prompt = synthesizer.synthesize_root_cause_prompt(
                target_node=result["target_node"],
                upstream_nodes=result["upstream_nodes"],
                edges=result["edges"],
            )

            llm_reply, llm_err = call_llm(
                prompt,
                openai_key=request.openai_api_key,
                openai_base_url=request.openai_base_url,
                openai_model=request.openai_model,
            )
            if llm_reply:
                reply = llm_reply
            elif llm_err and _has_api_key_configured(request):
                reply = f"<p>⚠️ <strong>LLM Provider Error</strong>:</p><p><code>{llm_err}</code></p><p>Please check your API key and model settings in the ⚙️ settings panel.</p>"
            else:
                upstream_names = [n["name"] for n in result["upstream_nodes"] if n["id"] != target_node["id"]]
                upstream_count = len(result["upstream_nodes"])
                reply = f"<p><strong>🔍 Upstream Root Cause Analysis for <code>{target_node['name']}</code></strong>:</p>"
                reply += f"<p>Upstream lineage traces back to <strong>{upstream_count}</strong> data assets across max traversal depth <strong>{result.get('depth_reached', 0)}</strong>.</p>"
                if upstream_names:
                    reply += "<p>Upstream source assets & dependencies:</p><ul>" + "".join(f"<li><code>{name}</code></li>" for name in upstream_names) + "</ul>"
                else:
                    reply += "<p>No upstream source dependencies found.</p>"
                reply += "<p><em>💡 Tip: Set <code>OPENAI_API_KEY</code> or <code>GEMINI_API_KEY</code> environment variable to enable live LLM responses.</em></p>"

            return {
                "tenant_id": tenant_id,
                "reply": reply,
                "synthesized_prompt": prompt,
                "upstream_nodes": result["upstream_nodes"],
                "target_node_id": target_node["id"],
            }

    # 3. General Semantic Data Discovery / Lineage Asset Search
    matched_nodes = engine.search_semantic_assets(query_text=request.message, top_k=5, as_of=request.as_of)
    prompt = synthesizer.synthesize_discovery_prompt(query_text=request.message, matched_nodes=matched_nodes)

    llm_reply, llm_err = call_llm(
        prompt,
        openai_key=request.openai_api_key,
        openai_base_url=request.openai_base_url,
        openai_model=request.openai_model,
    )
    if llm_reply:
        reply = llm_reply
    elif llm_err and _has_api_key_configured(request):
        reply = f"<p>⚠️ <strong>LLM Provider Error</strong>:</p><p><code>{llm_err}</code></p><p>Please check your API key, base URL, and model settings in the ⚙️ settings panel.</p>"
    elif matched_nodes:
        reply = f"<p>LineagIQ Knowledge Graph matched <strong>{len(matched_nodes)}</strong> relevant data assets for <strong>\"{request.message}\"</strong>:</p><ul>"
        for n in matched_nodes:
            desc = n.get("description") or "No description specified"
            reply += f"<li><strong><code>{n['name']}</code></strong> ({n['type']}): {desc}</li>"
        reply += "</ul><p><em>💡 Tip: Set <code>OPENAI_API_KEY</code> or <code>GEMINI_API_KEY</code> environment variable to enable live LLM responses.</em></p>"
    else:
        full_graph = engine.get_full_graph(as_of=request.as_of)
        nodes_count = len(full_graph.get("nodes", []))
        edges_count = len(full_graph.get("edges", []))
        reply = f"<p>LineagIQ Knowledge Graph active for tenant <code>{tenant_id}</code> containing <strong>{nodes_count} nodes</strong> and <strong>{edges_count} edges</strong>.</p><p>How can I help you trace asset dependencies or compute impact blast radius?</p>"
        reply += "<p><em>💡 Tip: Set <code>OPENAI_API_KEY</code> or <code>GEMINI_API_KEY</code> environment variable to enable live LLM responses.</em></p>"

    return {
        "tenant_id": tenant_id,
        "reply": reply,
        "synthesized_prompt": prompt,
        "matched_nodes": matched_nodes,
    }
