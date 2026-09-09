from typing import Dict
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from control_plane.src.config import STATIC_INDEX_FILE

router = APIRouter(tags=["Visualizer & Health"])


@router.get("/healthz")
def health_check() -> Dict[str, str]:
    """Service health check endpoint.

    Returns:
        Dictionary indicating status 'ok' and service name.
    """
    return {"status": "ok", "service": "lineagiq-control-plane"}


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
