from enum import Enum
from typing import Dict, Any, List, Optional, Union, Literal
from pydantic import BaseModel, Field, ConfigDict


class NodeType(str, Enum):
    DATASET = "Dataset"
    COLUMN = "Column"
    PIPELINE = "Pipeline"
    USER = "User"
    TEAM = "Team"
    BUSINESS_TERM = "BusinessTerm"


class EdgeType(str, Enum):
    PRODUCED_BY = "PRODUCED_BY"
    CONSUMED_BY = "CONSUMED_BY"
    OWNED_BY = "OWNED_BY"
    DERIVED_FROM = "DERIVED_FROM"
    JOINS_WITH = "JOINS_WITH"
    DISPLAYED_IN = "DISPLAYED_IN"
    GOVERNED_BY = "GOVERNED_BY"
    BELONGS_TO = "BELONGS_TO"


class Node(BaseModel):
    """
    Base Graph Node model representing entities in the LineagIQ ontology.
    """
    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: NodeType
    name: str
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None


class DatasetNode(Node):
    type: Literal[NodeType.DATASET] = NodeType.DATASET
    database: Optional[str] = None
    schema_name: Optional[str] = Field(default=None, alias="schema")
    table_type: Optional[str] = "BASE TABLE"
    owner: Optional[str] = None


class ColumnNode(Node):
    type: Literal[NodeType.COLUMN] = NodeType.COLUMN
    dataset_id: str
    data_type: Optional[str] = None
    is_nullable: bool = True
    ordinal_position: Optional[int] = None


class PipelineNode(Node):
    type: Literal[NodeType.PIPELINE] = NodeType.PIPELINE
    resource_type: Optional[str] = "model"
    owner: Optional[str] = None


class UserTeamNode(Node):
    type: Union[Literal[NodeType.USER], Literal[NodeType.TEAM]] = NodeType.USER
    email: Optional[str] = None


class BusinessTermNode(Node):
    type: Literal[NodeType.BUSINESS_TERM] = NodeType.BUSINESS_TERM
    definition: Optional[str] = None
    domain: Optional[str] = None


class Edge(BaseModel):
    """
    Graph Edge model representing relationships between nodes.
    """
    source_id: str
    target_id: str
    type: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphPayload(BaseModel):
    """
    Combined graph payload containing nodes and edges.
    """
    nodes: List[Union[DatasetNode, ColumnNode, PipelineNode, UserTeamNode, BusinessTermNode, Node]] = Field(default_factory=list)
    edges: List[Edge] = Field(default_factory=list)
