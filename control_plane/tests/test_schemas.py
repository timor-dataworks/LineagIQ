import pytest
from pydantic import ValidationError
from control_plane.src.schemas import (
    BlastRadiusRequest,
    RootCauseRequest,
    DiscoveryRequest,
    ChatRequest,
    TimeTravelDiffRequest,
)


def test_blast_radius_request_defaults():
    req = BlastRadiusRequest(node_id="analytics.orders")
    assert req.node_id == "analytics.orders"
    assert req.max_depth == 5
    assert req.data_path is None
    assert req.as_of is None


def test_blast_radius_request_validation():
    with pytest.raises(ValidationError):
        # Missing required node_id
        BlastRadiusRequest()  # type: ignore

    with pytest.raises(ValidationError):
        # max_depth out of bounds (> 10)
        BlastRadiusRequest(node_id="test", max_depth=15)  # type: ignore

    with pytest.raises(ValidationError):
        # max_depth < 1
        BlastRadiusRequest(node_id="test", max_depth=0)  # type: ignore


def test_root_cause_request_validation():
    req = RootCauseRequest(node_id="analytics.orders", max_depth=3)
    assert req.node_id == "analytics.orders"
    assert req.max_depth == 3

    with pytest.raises(ValidationError):
        RootCauseRequest()  # type: ignore


def test_discovery_request_validation():
    req = DiscoveryRequest(query="find customers", top_k=10)
    assert req.query == "find customers"
    assert req.top_k == 10

    with pytest.raises(ValidationError):
        DiscoveryRequest(query="test", top_k=100)  # type: ignore


def test_chat_request_fields():
    req = ChatRequest(
        message="What is the blast radius?",
        openai_api_key="sk-123",
        openai_base_url="http://localhost:11434/v1",
        openai_model="llama3",
    )
    assert req.message == "What is the blast radius?"
    assert req.openai_api_key == "sk-123"
    assert req.openai_base_url == "http://localhost:11434/v1"
    assert req.openai_model == "llama3"


def test_time_travel_diff_request_validation():
    req = TimeTravelDiffRequest(
        node_id="dataset.orders",
        timestamp_t1="2026-09-08T10:00:00Z",
        timestamp_t2="2026-09-08T11:00:00Z",
    )
    assert req.node_id == "dataset.orders"
    assert req.timestamp_t1 == "2026-09-08T10:00:00Z"
    assert req.timestamp_t2 == "2026-09-08T11:00:00Z"

    with pytest.raises(ValidationError):
        # Missing timestamp_t2
        TimeTravelDiffRequest(node_id="dataset.orders", timestamp_t1="2026-09-08T10:00:00Z")  # type: ignore
