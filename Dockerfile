# ==============================================================================
# LineagIQ Unified Multi-Stage Dockerfile
#
# Build Targets:
#   1. Collection Agent:
#      docker build --target collection-agent -t lineagiq-collection-agent .
#
#   2. Control Plane (Default):
#      docker build --target control-plane -t lineagiq-control-plane .
# ==============================================================================

# Base image with shared dependencies and environment
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    DATA_PATH=/data

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY core/requirements.txt /app/core/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/core/requirements.txt

COPY core/ /app/core/
COPY scripts/ /app/scripts/


# ------------------------------------------------------------------------------
# Target: Collection Agent
# ------------------------------------------------------------------------------
FROM base AS collection-agent

COPY collection_agent/requirements.txt /app/collection_agent/requirements.txt
RUN pip install --no-cache-dir -r /app/collection_agent/requirements.txt

COPY collection_agent/ /app/collection_agent/

VOLUME ["/data"]

ENTRYPOINT ["python", "-m", "collection_agent.src.cli"]
CMD []


# ------------------------------------------------------------------------------
# Target: Control Plane (Default)
# ------------------------------------------------------------------------------
FROM base AS control-plane

ENV PORT=8000 \
    HOST=0.0.0.0

COPY control_plane/requirements.txt /app/control_plane/requirements.txt
RUN pip install --no-cache-dir -r /app/control_plane/requirements.txt

COPY control_plane/ /app/control_plane/

EXPOSE 8000
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["sh", "-c", "exec uvicorn control_plane.src.main:app --host ${HOST} --port ${PORT}"]
