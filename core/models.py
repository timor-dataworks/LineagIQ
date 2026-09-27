"""LineagIQ Core Ontology & Domain Models.

Defines standard entity nodes, relationships, and payload containers
used across ingestion agents, control planes, and GraphRAG pipelines.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NodeType(StrEnum):
    """Supported entity node types in the LineagIQ ontology graph."""
    DATASET = "Dataset"
    COLUMN = "Column"
    PIPELINE = "Pipeline"
    USER = "User"
    TEAM = "Team"
    BUSINESS_TERM = "BusinessTerm"


class EdgeType(StrEnum):
    """Supported relationship edge types in the LineagIQ ontology graph."""
    PRODUCED_BY = "PRODUCED_BY"
    CONSUMED_BY = "CONSUMED_BY"
    OWNED_BY = "OWNED_BY"
    DERIVED_FROM = "DERIVED_FROM"
    JOINS_WITH = "JOINS_WITH"
    DISPLAYED_IN = "DISPLAYED_IN"
    GOVERNED_BY = "GOVERNED_BY"
    BELONGS_TO = "BELONGS_TO"



class Node(BaseModel):
    """Base Graph Node model representing an entity in the LineagIQ graph."""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Unique node canonical identifier")
    type: NodeType = Field(..., description="Entity type classification")
    name: str = Field(..., description="Human-readable entity display name")
    description: str | None = Field(default=None, description="Optional text description or documentation")
    properties: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata attributes map")
    embedding: list[float] | None = Field(default=None, description="Dense vector embedding representation")


class DatasetNode(Node):
    """Data Asset node representing tables, views, topics, or files."""
    type: NodeType = NodeType.DATASET
    database: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")
    table_type: str | None = "BASE TABLE"
    owner: str | None = None


class ColumnNode(Node):
    """Column Attribute node representing a single schema column in a Dataset."""
    type: NodeType = NodeType.COLUMN
    dataset_id: str = Field(..., description="Parent Dataset node ID")
    data_type: str | None = None
    is_nullable: bool = True
    ordinal_position: int | None = None


class PipelineNode(Node):
    """Data Pipeline node representing dbt models, Airflow DAGs, or Spark jobs."""
    type: NodeType = NodeType.PIPELINE
    resource_type: str | None = "model"
    owner: str | None = None


class UserTeamNode(Node):
    """User or Team node representing data consumers and owners."""
    type: NodeType = NodeType.USER
    email: str | None = None


class BusinessTermNode(Node):
    """Business Glossary Term node representing data governance terms."""
    type: NodeType = NodeType.BUSINESS_TERM
    definition: str | None = None
    domain: str | None = None


class Edge(BaseModel):
    """Graph Edge model representing directional relationships between nodes."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    type: EdgeType = Field(..., description="Edge relationship type classification")
    properties: dict[str, Any] = Field(default_factory=dict, description="Edge property metadata map")


class GraphPayload(BaseModel):
    """Container payload holding a collection of graph nodes and lineage edges."""
    nodes: list[DatasetNode | ColumnNode | PipelineNode | UserTeamNode | BusinessTermNode | Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
