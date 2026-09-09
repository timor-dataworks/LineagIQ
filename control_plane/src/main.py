import os
import re
import json
import logging
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

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_INDEX_FILE = STATIC_DIR / "index.html"

app = FastAPI(
    title="LineagIQ Control Plane & GraphRAG API",
    description="Multi-tenant GraphRAG query engine over S3 Parquet and DuckDB VSS indices.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def resolve_data_path(tenant_id: str, custom_path: Optional[str] = None) -> str:
    """Resolves local or S3 tenant data path with environment fallback.

    Args:
        tenant_id: Unique tenant identifier.
        custom_path: Optional explicit data path passed in API request.

    Returns:
        Resolved file or directory path string for tenant Parquet datasets.
    """
    return custom_path or os.getenv("TENANT_DATA_DIR", f"/tmp/tenants/{tenant_id}")


def post_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 45,
) -> Tuple[Optional[Any], Optional[str]]:
    """Generic JSON POST request helper using standard urllib.

    Args:
        url: Target HTTP endpoint URL.
        payload: Data dictionary to serialize as JSON payload.
        headers: Optional HTTP headers dictionary.
        timeout: HTTP request timeout in seconds. Defaults to 45.

    Returns:
        Tuple of (parsed_json_response_dict, error_message_string).
        On success, second element is None. On failure, first element is None.
    """
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
        logger.warning(f"HTTP Error for POST {url}: {msg}")
        return None, msg
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower():
            err_msg = f"Request timed out ({timeout}s limit exceeded)"
        logger.warning(f"HTTP POST request warning to {url}: {err_msg}")
        return None, err_msg


class BlastRadiusRequest(BaseModel):
    """Payload schema for downstream blast radius analysis request."""
    node_id: str = Field(..., description="Target node ID for blast radius analysis")
    max_depth: int = Field(default=5, ge=1, le=10, description="Max lineage traversal depth")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")
    as_of: Optional[str] = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")


class RootCauseRequest(BaseModel):
    """Payload schema for upstream root cause analysis request."""
    node_id: str = Field(..., description="Target node ID for upstream root cause analysis")
    max_depth: int = Field(default=5, ge=1, le=10, description="Max lineage traversal depth")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")
    as_of: Optional[str] = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")


class DiscoveryRequest(BaseModel):
    """Payload schema for semantic asset discovery request."""
    query: str = Field(..., description="Natural language semantic search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Max matched assets to return")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")
    as_of: Optional[str] = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")


class ChatRequest(BaseModel):
    """Payload schema for interactive GraphRAG LLM chat request."""
    message: str = Field(..., description="User query for GraphRAG lineage AI assistant")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")
    as_of: Optional[str] = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")
    openai_api_key: Optional[str] = Field(default=None, description="Optional OpenAI API Key")
    openai_base_url: Optional[str] = Field(default=None, description="Optional OpenAI Base URL endpoint")
    openai_model: Optional[str] = Field(default=None, description="Optional OpenAI Model name")


class TimeTravelDiffRequest(BaseModel):
    """Payload schema for historical schema drift and lineage diff request."""
    node_id: str = Field(..., description="Target node ID for time travel diff analysis")
    timestamp_t1: str = Field(..., description="Initial ISO 8601 timestamp string (T1)")
    timestamp_t2: str = Field(..., description="Subsequent ISO 8601 timestamp string (T2)")
    data_path: Optional[str] = Field(default=None, description="Local or S3 path to tenant data")


@app.get("/healthz")
def health_check() -> Dict[str, str]:
    """Service health check endpoint.

    Returns:
        Dictionary indicating status 'ok' and service name.
    """
    return {"status": "ok", "service": "lineagiq-control-plane"}


@app.get("/", response_class=HTMLResponse)
@app.get("/visualizer", response_class=HTMLResponse)
def get_graph_visualizer() -> str:
    """Serves the Knowledge Graph Visualizer web page.

    Returns:
        HTML document content string.

    Raises:
        HTTPException 404 if index.html is missing.
    """
    if not STATIC_INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="Visualizer index.html not found")
    return STATIC_INDEX_FILE.read_text(encoding="utf-8")


@app.get("/api/v1/tenants/{tenant_id}/graph")
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


@app.get("/api/v1/tenants/{tenant_id}/timeline")
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


@app.post("/api/v1/tenants/{tenant_id}/blast-radius")
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


@app.post("/api/v1/tenants/{tenant_id}/root-cause")
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


@app.post("/api/v1/tenants/{tenant_id}/discovery")
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


@app.post("/api/v1/tenants/{tenant_id}/time-travel/diff")
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


def clean_latex_to_unicode(text: str) -> str:
    """Sanitizes LaTeX math formatting from LLM responses into clean Unicode and plain text."""
    if not text:
        return text

    # Strip \text{...}, \mathrm{...}, \mathbf{...}, \mathit{...} wrappers
    text = re.sub(r"\\text\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\mathrm\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\mathbf\{([^}]+)\}", r"\1", text)
    text = re.sub(r"\\mathit\{([^}]+)\}", r"\1", text)

    # Convert escaped underscores often generated in LaTeX
    text = re.sub(r"\\_", "_", text)

    # Clean LaTeX arrows into clean Unicode
    text = re.sub(r"\$\s*\\+(?:rightarrow|to)\s*\$", "→", text)
    text = re.sub(r"\\+(?:rightarrow|to)\b", "→", text)
    text = re.sub(r"\$\s*\\+leftarrow\s*\$", "←", text)
    text = re.sub(r"\\+leftarrow\b", "←", text)
    text = re.sub(r"\$\s*\\+Rightarrow\s*\$", "⇒", text)
    text = re.sub(r"\\+Rightarrow\b", "⇒", text)
    text = re.sub(r"\$\s*\\+Leftarrow\s*\$", "⇐", text)
    text = re.sub(r"\\+Leftarrow\b", "⇐", text)
    text = re.sub(r"\$\s*\\+leftrightarrow\s*\$", "↔", text)
    text = re.sub(r"\\+leftrightarrow\b", "↔", text)
    text = re.sub(r"\$\s*\\+Leftrightarrow\s*\$", "⇔", text)
    text = re.sub(r"\\+Leftrightarrow\b", "⇔", text)
    text = re.sub(r"\$\s*\\+(?:longrightarrow|mapsto|implies)\s*\$", "⟶", text)
    text = re.sub(r"\\+(?:longrightarrow|mapsto|implies)\b", "⟶", text)

    # Common math symbols
    text = re.sub(r"\$\s*\\+approx\s*\$", "≈", text)
    text = re.sub(r"\\+approx\b", "≈", text)
    text = re.sub(r"\$\s*\\+neq\s*\$", "≠", text)
    text = re.sub(r"\\+neq\b", "≠", text)
    text = re.sub(r"\$\s*\\+(?:le|leq)\s*\$", "≤", text)
    text = re.sub(r"\\+(?:le|leq)\b", "≤", text)
    text = re.sub(r"\$\s*\\+(?:ge|geq)\s*\$", "≥", text)
    text = re.sub(r"\\+(?:ge|geq)\b", "≥", text)
    text = re.sub(r"\$\s*\\+times\s*\$", "×", text)
    text = re.sub(r"\\+times\b", "×", text)
    text = re.sub(r"\$\s*\\+cdot\s*\$", "·", text)
    text = re.sub(r"\\+cdot\b", "·", text)
    text = re.sub(r"\$\s*\\+(?:dots|cdots)\s*\$", "...", text)
    text = re.sub(r"\\+(?:dots|cdots)\b", "...", text)

    # Unwrap $...$ wrapping around arrow or simple math expressions
    text = re.sub(r"\$([^$\n]*?[→←⇒⇐↔⇔⟶⟵⟹↦][^$\n]*?)\$", r"\1", text)
    text = re.sub(r"\{([→←⇒⇐↔⇔⟶⟵⟹↦])\}", r"\1", text)

    return text


def call_openai_llm(
    prompt: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Calls OpenAI API or OpenAI-compatible provider (Azure, Ollama, vLLM, Groq, OpenRouter).

    Automatically routes Gemini API keys (AIza..., AQ...) to Google's OpenAI endpoint
    if no custom base_url is set.

    Args:
        prompt: Full prompt string to submit to LLM.
        api_key: Optional API key override.
        base_url: Optional API base URL endpoint override.
        model: Optional LLM model identifier override.

    Returns:
        Tuple of (generated_response_text, error_message_string).
    """
    key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    endpoint = (base_url or os.getenv("OPENAI_BASE_URL") or "").rstrip("/")

    # Allow local Ollama or local LLM servers without requiring API key
    if not key:
        if endpoint and any(h in endpoint.lower() for h in ["11434", "localhost", "127.0.0.1", "ollama"]):
            key = "ollama"
        else:
            return None, None

    is_gemini_key = (key.startswith("AIza") or key.startswith("AQ") or (not key.startswith("sk-") and key != "ollama")) and not (endpoint and "11434" in endpoint)
    default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai" if is_gemini_key else "https://api.openai.com/v1"
    default_model = "gemini-3.6-flash" if is_gemini_key else ("llama3" if key == "ollama" else "gpt-4o-mini")

    if not endpoint:
        endpoint = default_base_url

    url = f"{endpoint}/chat/completions"
    model_name = model or os.getenv("OPENAI_MODEL") or default_model

    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are LineagIQ AI Assistant, an expert data lineage, governance, and blast radius reasoning agent.\n"
                    "CRITICAL FORMATTING INSTRUCTION: Do NOT use LaTeX math formatting, dollar signs ($), or LaTeX commands "
                    "(e.g. \\rightarrow, \\to, \\leftarrow). Always use clean plain text or standard Unicode symbols "
                    "(such as '→' for lineage transitions, '←', '⇒', bullet points, bold markdown)."
                ),
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
                return clean_latex_to_unicode(content), None

    return None, err


def call_gemini_llm(prompt: str, api_key: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Calls Google Gemini API (gemini-3.6-flash) using standard REST HTTP endpoint.

    Args:
        prompt: Full prompt string to submit to Gemini.
        api_key: Optional Gemini/Google API key override.

    Returns:
        Tuple of (generated_response_text, error_message_string).
    """
    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None, None

    formatting_rule = (
        "\n\nCRITICAL FORMATTING INSTRUCTION: Do NOT use LaTeX math formatting, dollar signs ($), or LaTeX commands "
        "(e.g. \\rightarrow, \\to). Always output clean plain text or Unicode symbols (e.g. '→' for lineage flow).\n"
    )
    payload = {"contents": [{"parts": [{"text": prompt + formatting_rule}]}]}
    last_err = None

    for model_name in ["gemini-3.6-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        body, err = post_json(url, payload)
        if body and isinstance(body, dict):
            candidates = body.get("candidates", [])
            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                parts = candidates[0].get("content", {}).get("parts", [])
                if parts and parts[0].get("text"):
                    return clean_latex_to_unicode(parts[0]["text"]), None
        if err:
            last_err = err

    return None, last_err


def call_llm(
    prompt: str,
    openai_key: Optional[str] = None,
    openai_base_url: Optional[str] = None,
    openai_model: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Attempts to generate LLM response using configured providers in order:
    1. OpenAI / OpenAI-compatible API (including Gemini AIza keys via Google OpenAI endpoint)
    2. Google Gemini Native API

    Args:
        prompt: Full prompt string for LLM completion.
        openai_key: Optional OpenAI API key override.
        openai_base_url: Optional base URL endpoint override.
        openai_model: Optional model name override.

    Returns:
        Tuple of (generated_response_text, error_message_string).
    """
    openai_res, openai_err = call_openai_llm(prompt, api_key=openai_key, base_url=openai_base_url, model=openai_model)
    if openai_res:
        return clean_latex_to_unicode(openai_res), None

    gemini_res, gemini_err = call_gemini_llm(prompt, api_key=openai_key)
    if gemini_res:
        return clean_latex_to_unicode(gemini_res), None

    return None, openai_err or gemini_err


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


@app.post("/api/v1/tenants/{tenant_id}/chat")
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
        reply = f"⚠️ **LLM Provider Error**:\n\n`{llm_err}`\n\nPlease check your API key, base URL, and model settings in the ⚙️ settings panel."
    elif matched_nodes:
        reply = f"LineagIQ Knowledge Graph matched **{len(matched_nodes)}** relevant data assets for **\"{request.message}\"**:\n\n"
        for n in matched_nodes:
            desc = n.get("description") or "No description specified"
            reply += f"• **`{n['name']}`** ({n['type']}): {desc}\n"
        reply += "\n*💡 Tip: Set `OPENAI_API_KEY` or `GEMINI_API_KEY` environment variable to enable live LLM responses.*"
    else:
        full_graph = engine.get_full_graph(as_of=request.as_of)
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



