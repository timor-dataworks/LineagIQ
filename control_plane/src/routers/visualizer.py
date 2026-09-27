import os
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from control_plane.src.config import STATIC_INDEX_FILE, resolve_data_path

router = APIRouter(tags=["Visualizer & Health"])


@router.get("/healthz")
def health_check() -> dict[str, str]:
    """Service health check endpoint.

    Returns:
        Dictionary indicating status 'ok' and service name.
    """
    return {"status": "ok", "service": "lineagiq-control-plane"}


@router.get("/api/v1/config")
def get_app_config() -> dict[str, Any]:
    """Returns application environment configuration for the web UI.

    Ensures the web GUI operates on server-enforced data path settings.
    """
    data_path = resolve_data_path()
    return {
        "data_path": data_path,
        "env_data_path_set": bool(os.getenv("DATA_PATH")),
    }


@router.get("/", response_class=HTMLResponse)
@router.get("/visualizer", response_class=HTMLResponse)
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
