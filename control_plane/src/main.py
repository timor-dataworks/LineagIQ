"""LineagIQ Control Plane & GraphRAG API Application Entry Point.

Orchestrates FastAPI routers, static asset mounting, and configuration.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from control_plane.src.config import STATIC_DIR, resolve_data_path
from control_plane.src.services.latex_sanitizer import clean_latex_to_unicode
from control_plane.src.schemas import (
    BlastRadiusRequest,
    RootCauseRequest,
    DiscoveryRequest,
    ChatRequest,
    TimeTravelDiffRequest,
)
from control_plane.src.routers import (
    visualizer_router,
    lineage_router,
    chat_router,
)


def create_app() -> FastAPI:
    """FastAPI application factory for the LineagIQ Control Plane."""
    application = FastAPI(
        title="LineagIQ Control Plane & GraphRAG API",
        description="Multi-tenant GraphRAG query engine over S3 Parquet and DuckDB VSS indices.",
        version="1.0.0",
    )

    # Mount static assets for web visualizer
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    # Register modular API routers
    application.include_router(visualizer_router)
    application.include_router(lineage_router)
    application.include_router(chat_router)

    return application


app = create_app()

__all__ = [
    "app",
    "create_app",
    "resolve_data_path",
    "clean_latex_to_unicode",
    "STATIC_DIR",
    "BlastRadiusRequest",
    "RootCauseRequest",
    "DiscoveryRequest",
    "ChatRequest",
    "TimeTravelDiffRequest",
]
