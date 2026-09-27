
from pydantic import BaseModel, Field


class BlastRadiusRequest(BaseModel):
    """Payload schema for downstream blast radius analysis request."""
    node_id: str = Field(..., description="Target node ID for blast radius analysis")
    max_depth: int = Field(default=5, ge=1, le=10, description="Max lineage traversal depth")
    as_of: str | None = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")


class RootCauseRequest(BaseModel):
    """Payload schema for upstream root cause analysis request."""
    node_id: str = Field(..., description="Target node ID for upstream root cause analysis")
    max_depth: int = Field(default=5, ge=1, le=10, description="Max lineage traversal depth")
    as_of: str | None = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")


class DiscoveryRequest(BaseModel):
    """Payload schema for semantic asset discovery request."""
    query: str = Field(..., description="Natural language semantic search query")
    top_k: int = Field(default=5, ge=1, le=50, description="Max matched assets to return")
    as_of: str | None = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")


class ChatRequest(BaseModel):
    """Payload schema for interactive GraphRAG LLM chat request."""
    message: str = Field(..., description="User query for GraphRAG lineage AI assistant")
    as_of: str | None = Field(default=None, description="Optional ISO 8601 timestamp string for historical time travel")
    openai_api_key: str | None = Field(default=None, description="Optional OpenAI API Key")
    openai_base_url: str | None = Field(default=None, description="Optional OpenAI Base URL endpoint")
    openai_model: str | None = Field(default=None, description="Optional OpenAI Model name")


class TimeTravelDiffRequest(BaseModel):
    """Payload schema for historical schema drift and lineage diff request."""
    node_id: str = Field(..., description="Target node ID for time travel diff analysis")
    timestamp_t1: str = Field(..., description="Initial ISO 8601 timestamp string (T1)")
    timestamp_t2: str = Field(..., description="Subsequent ISO 8601 timestamp string (T2)")
