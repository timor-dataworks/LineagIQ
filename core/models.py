"""LineagIQ Core Ontology & Domain Models.

Defines standard entity nodes, relationships, and payload containers
used across ingestion agents, control planes, and GraphRAG pipelines.
"""

from enum import Enum
from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict


class NodeType(str, Enum):
    """Supported entity node types in the LineagIQ ontology graph."""
    DATASET = "Dataset"
    COLUMN = "Column"
    PIPELINE = "Pipeline"
    USER = "User"
    TEAM = "Team"
    BUSINESS_TERM = "BusinessTerm"


class EdgeType(str, Enum):
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
    description: Optional[str] = Field(default=None, description="Optional text description or documentation")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata attributes map")
    embedding: Optional[List[float]] = Field(default=None, description="Dense vector embedding representation")


class DatasetNode(Node):
    """Data Asset node representing tables, views, topics, or files."""
    type: Literal[NodeType.DATASET] = NodeType.DATASET
    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")
    table_type: Optional[str] = "BASE TABLE"
    owner: Optional[str] = None


class ColumnNode(Node):
    """Column Attribute node representing a single schema column in a Dataset."""
    type: Literal[NodeType.COLUMN] = NodeType.COLUMN
    dataset_id: str = Field(..., description="Parent Dataset node ID")
    data_type: Optional[str] = None
    is_nullable: bool = True
    ordinal_position: Optional[int] = None


class PipelineNode(Node):
    """Data Pipeline node representing dbt models, Airflow DAGs, or Spark jobs."""
    type: Literal[NodeType.PIPELINE] = NodeType.PIPELINE
    resource_type: Optional[str] = "model"
    owner: Optional[str] = None


class UserTeamNode(Node):
    """User or Team node representing data consumers and owners."""
    type: Union[Literal[NodeType.USER], Literal[NodeType.TEAM]] = NodeType.USER
    email: Optional[str] = None


class BusinessTermNode(Node):
    """Business Glossary Term node representing data governance terms."""
    type: Literal[NodeType.BUSINESS_TERM] = NodeType.BUSINESS_TERM
    definition: Optional[str] = None
    domain: Optional[str] = None


class Edge(BaseModel):
    """Graph Edge model representing directional relationships between nodes."""
    source_id: str = Field(..., description="Source node ID")
    target_id: str = Field(..., description="Target node ID")
    type: EdgeType = Field(..., description="Edge relationship type classification")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge property metadata map")


class GraphPayload(BaseModel):
    """Container payload holding a collection of graph nodes and lineage edges."""
    nodes: List[Union[DatasetNode, ColumnNode, PipelineNode, UserTeamNode, BusinessTermNode, Node]] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
