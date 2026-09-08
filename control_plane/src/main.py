import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException, Path as FastPath, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer

STATIC_DIR = Path(__file__).parent / "static"
STATIC_INDEX_FILE = STATIC_DIR / "index.html"

app = FastAPI(
    title="LineagIQ Control Plane & GraphRAG API",
    description="Multi-tenant GraphRAG query engine over S3 Parquet and DuckDB VSS indices.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def resolve_data_path(tenant_id: str, custom_path: Optional[str] = None) -> str:
    """Resolves local or S3 tenant data path with environment fallback."""
    return custom_path or os.getenv("TENANT_DATA_DIR", f"/tmp/tenants/{tenant_id}")


def post_json(url: str, payload: Dict[str, Any], headers: Optional[Dict[str, str]] = None, timeout: int = 45) -> Tuple[Optional[Any], Optional[str]]:
    """Generic JSON POST request helper using standard urllib."""
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
        
    try:
        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        err_text = ""
        try:
            err_text = e.read().decode("utf-8")
        except Exception:
            pass
        msg = f"HTTP {e.code}"
        if err_text:
            try:
                parsed = json.loads(err_text)
                if isinstance(parsed, dict) and "error" in parsed:
                    err_obj = parsed["error"]
                    if isinstance(err_obj, dict) and "message" in err_obj:
                        msg += f": {err_obj['message']}"
                    else:
                        msg += f": {err_obj}"
                elif isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict) and "error" in parsed[0]:
                    msg += f": {parsed[0]['error'].get('message', parsed[0]['error'])}"
                else:
                    msg += f": {err_text[:200]}"
            except Exception:
                msg += f": {err_text[:200]}"
        print(f"HTTP Error for POST {url}: {msg}")
        return None, msg
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower():
            err_msg = f"Request timed out ({timeout}s limit exceeded)"
        print(f"HTTP POST request warning to {url}: {err_msg}")
        return None, err_msg


class BlastRadiusRequest(BaseModel):
    node_id: str = Field(..., description="Target node ID for blast radius analysis")
    max_depth: int = Field(default=5, ge=1, le=10, description="Max lineage traversal depth")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")


class RootCauseRequest(BaseModel):
    node_id: str = Field(..., description="Target node ID for upstream root cause analysis")
    max_depth: int = Field(default=5, ge=1, le=10, description="Max lineage traversal depth")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")



class DiscoveryRequest(BaseModel):
    query: str = Field(..., description="Natural language semantic search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Max matched assets to return")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")


class ChatRequest(BaseModel):
    message: str = Field(..., description="User query for GraphRAG lineage AI assistant")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")
    openai_api_key: Optional[str] = Field(default=None, description="Optional OpenAI API Key")
    openai_base_url: Optional[str] = Field(default=None, description="Optional OpenAI Base URL endpoint")
    openai_model: Optional[str] = Field(default=None, description="Optional OpenAI Model name")


@app.get("/healthz")
def health_check():
    return {"status": "ok", "service": "lineagiq-control-plane"}


@app.get("/", response_class=HTMLResponse)
@app.get("/visualizer", response_class=HTMLResponse)
def get_graph_visualizer():
    """Serves the Knowledge Graph Visualizer web page."""
    if not STATIC_INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Visualizer index.html not found")
    return STATIC_INDEX_FILE.read_text(encoding="utf-8")


@app.get("/api/v1/tenants/{tenant_id}/graph")
def get_tenant_graph(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    data_path: Optional[str] = Query(default=None, description="Local or S3 data path"),
):
    """Returns all nodes and edges for tenant graph visualization."""
    engine = DuckDBQueryEngine(data_base_path=resolve_data_path(tenant_id, data_path))
    return engine.get_full_graph()


@app.post("/api/v1/tenants/{tenant_id}/blast-radius")
def calculate_blast_radius(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: BlastRadiusRequest = None,
):
    data_base = resolve_data_path(tenant_id, request.data_path if request else None)
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
        "depth_reached": result.get("depth_reached", 0),
        "impacted_nodes": result["impacted_nodes"],
        "edges": result["edges"],
        "synthesized_prompt": prompt,
    }


@app.post("/api/v1/tenants/{tenant_id}/root-cause")
def calculate_root_cause(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: RootCauseRequest = None,
):
    data_base = resolve_data_path(tenant_id, request.data_path if request else None)
    engine = DuckDBQueryEngine(data_base_path=data_base)
    result = engine.get_upstream_root_cause(
        start_node_id=request.node_id,
        max_depth=request.max_depth,
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



@app.post("/api/v1/tenants/{tenant_id}/discovery")
def discover_semantic_assets(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: DiscoveryRequest = None,
):
    data_base = resolve_data_path(tenant_id, request.data_path if request else None)
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


def call_openai_llm(
    prompt: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Calls OpenAI API or any OpenAI-compatible provider (Azure OpenAI, Ollama, vLLM, Groq, OpenRouter).
    Automatically routes Gemini API keys (AIza..., AQ...) to Google's OpenAI endpoint if no custom base_url is set.
    """
    key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return None, None

    is_gemini_key = key.startswith("AIza") or key.startswith("AQ") or not key.startswith("sk-")
    default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai" if is_gemini_key else "https://api.openai.com/v1"
    default_model = "gemini-3.6-flash" if is_gemini_key else "gpt-4o-mini"

    endpoint = (base_url or os.getenv("OPENAI_BASE_URL") or default_base_url).rstrip("/")
    url = f"{endpoint}/chat/completions"
    model_name = model or os.getenv("OPENAI_MODEL") or default_model

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": "You are LineagIQ AI Assistant, an expert data lineage, governance, and blast radius reasoning agent.",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
    }

    body, err = post_json(url, payload, headers={"Authorization": f"Bearer {key}"})
    if body and isinstance(body, dict):
        choices = body.get("choices", [])
        if choices and isinstance(choices, list) and len(choices) > 0:
            content = choices[0].get("message", {}).get("content")
            if content:
                return content, None

    return None, err


def call_gemini_llm(prompt: str, api_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Calls Google Gemini API (gemini-3.6-flash) using standard HTTP endpoint.
    """
    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None, None

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    last_err = None

    for model_name in ["gemini-3.6-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        body, err = post_json(url, payload)
        if body and isinstance(body, dict):
            candidates = body.get("candidates", [])
            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and parts[0].get("text"):
                    return parts[0]["text"], None
        if err:
            last_err = err

    return None, last_err


def call_llm(
    prompt: str,
    openai_key: Optional[str] = None,
    openai_base_url: Optional[str] = None,
    openai_model: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempts to generate LLM response using configured providers in order:
    1. OpenAI / OpenAI-compatible API (including Gemini AIza keys via Google OpenAI endpoint)
    2. Google Gemini Native API
    """
    openai_res, openai_err = call_openai_llm(prompt, api_key=openai_key, base_url=openai_base_url, model=openai_model)
    if openai_res:
        return openai_res, None

    gemini_res, gemini_err = call_gemini_llm(prompt, api_key=openai_key)
    if gemini_res:
        return gemini_res, None

    return None, openai_err or gemini_err


@app.post("/api/v1/tenants/{tenant_id}/chat")
def lineage_ai_chat(
    tenant_id: str = FastPath(..., description="Tenant Identifier"),
    request: ChatRequest = None,
):
    """
    GraphRAG LLM Lineage Chat endpoint. Integrates DuckDB query engine, PromptSynthesizer,
    OpenAI, and Gemini LLM to answer interactive queries regarding blast radius and lineage graphs.
    """
    if not request or not request.message:
        raise HTTPException(status_code=400, detail="Message prompt is required")

    msg_lower = request.message.lower().strip()
    data_base = resolve_data_path(tenant_id, request.data_path)
    engine = DuckDBQueryEngine(data_base_path=data_base)
    synthesizer = PromptSynthesizer()

    # 1. Check if query asks about blast radius or downstream impact
    if any(k in msg_lower for k in ["blast", "impact", "affected", "break", "change", "downstream"]):
        full_graph = engine.get_full_graph()
        target_node = None
        for n in full_graph.get("nodes", []):
            if n["name"].lower() in msg_lower or n["id"].lower() in msg_lower:
                target_node = n
                break
        
        if not target_node and full_graph.get("nodes"):
            target_node = full_graph["nodes"][0]

        if target_node:
            result = engine.get_downstream_blast_radius(start_node_id=target_node["id"], max_depth=5)
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
            elif llm_err and (request.openai_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
                reply = f"⚠️ **LLM Provider Error**:\n\n`{llm_err}`\n\nPlease check your API key and model settings in the ⚙️ settings panel."
            else:
                impacted_names = [n["name"] for n in result["impacted_nodes"] if n["id"] != target_node["id"]]
                impacted_count = len(result["impacted_nodes"])
                reply = f"**⚡ Blast Radius Analysis for `{target_node['name']}`**:\n\n"
                reply += f"Downstream impact affects **{impacted_count}** data assets across max traversal depth **{result.get('depth_reached', 0)}**.\n\n"
                if impacted_names:
                    reply += "Impacted downstream assets:\n" + "\n".join(f"- `{name}`" for name in impacted_names)
                else:
                    reply += "No downstream assets are impacted."
                reply += "\n\n*💡 Tip: Set `OPENAI_API_KEY` or `GEMINI_API_KEY` environment variable to enable live LLM responses.*"

            return {
                "tenant_id": tenant_id,
                "reply": reply,
                "synthesized_prompt": prompt,
                "impacted_nodes": result["impacted_nodes"],
                "target_node_id": target_node["id"],
            }

    # 2. Check if query asks about root cause or upstream origin
    if any(k in msg_lower for k in ["root cause", "upstream", "why", "origin", "source", "parent"]):
        full_graph = engine.get_full_graph()
        target_node = None
        for n in full_graph.get("nodes", []):
            if n["name"].lower() in msg_lower or n["id"].lower() in msg_lower:
                target_node = n
                break
        
        if not target_node and full_graph.get("nodes"):
            target_node = full_graph["nodes"][0]

        if target_node:
            result = engine.get_upstream_root_cause(start_node_id=target_node["id"], max_depth=5)
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
            elif llm_err and (request.openai_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
                reply = f"⚠️ **LLM Provider Error**:\n\n`{llm_err}`\n\nPlease check your API key and model settings in the ⚙️ settings panel."
            else:
                upstream_names = [n["name"] for n in result["upstream_nodes"] if n["id"] != target_node["id"]]
                upstream_count = len(result["upstream_nodes"])
                reply = f"**🔍 Upstream Root Cause Analysis for `{target_node['name']}`**:\n\n"
                reply += f"Upstream lineage traces back to **{upstream_count}** data assets across max traversal depth **{result.get('depth_reached', 0)}**.\n\n"
                if upstream_names:
                    reply += "Upstream source assets & dependencies:\n" + "\n".join(f"- `{name}`" for name in upstream_names)
                else:
                    reply += "No upstream source dependencies found."
                reply += "\n\n*💡 Tip: Set `OPENAI_API_KEY` or `GEMINI_API_KEY` environment variable to enable live LLM responses.*"

            return {
                "tenant_id": tenant_id,
                "reply": reply,
                "synthesized_prompt": prompt,
                "upstream_nodes": result["upstream_nodes"],
                "target_node_id": target_node["id"],
            }

    # 3. General Semantic Data Discovery / Lineage Asset Search

    matched_nodes = engine.search_semantic_assets(query_text=request.message, top_k=5)
    prompt = synthesizer.synthesize_discovery_prompt(query_text=request.message, matched_nodes=matched_nodes)

    llm_reply, llm_err = call_llm(
        prompt,
        openai_key=request.openai_api_key,
        openai_base_url=request.openai_base_url,
        openai_model=request.openai_model,
    )
    if llm_reply:
        reply = llm_reply
    elif llm_err and (request.openai_api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        reply = f"⚠️ **LLM Provider Error**:\n\n`{llm_err}`\n\nPlease check your API key, base URL, and model settings in the ⚙️ settings panel."
    elif matched_nodes:
        reply = f"LineagIQ Knowledge Graph matched **{len(matched_nodes)}** relevant data assets for **\"{request.message}\"**:\n\n"
        for n in matched_nodes:
            desc = n.get("description") or "No description specified"
            reply += f"• **`{n['name']}`** ({n['type']}): {desc}\n"
        reply += "\n*💡 Tip: Set `OPENAI_API_KEY` or `GEMINI_API_KEY` environment variable to enable live LLM responses.*"
    else:
        full_graph = engine.get_full_graph()
        nodes_count = len(full_graph.get("nodes", []))
        edges_count = len(full_graph.get("edges", []))
        reply = f"LineagIQ Knowledge Graph active for tenant `{tenant_id}` containing **{nodes_count} nodes** and **{edges_count} edges**.\n\nHow can I help you trace asset dependencies or compute impact blast radius?"
        reply += "\n\n*💡 Tip: Set `OPENAI_API_KEY` or `GEMINI_API_KEY` environment variable to enable live LLM responses.*"

    return {
        "tenant_id": tenant_id,
        "reply": reply,
        "synthesized_prompt": prompt,
        "matched_nodes": matched_nodes,
    }

