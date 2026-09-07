from typing import Dict, Any, List, Optional
from collection_agent.src.transform.models import (
    Node,
    NodeType,
    EdgeType,
    DatasetNode,
    ColumnNode,
    PipelineNode,
    UserTeamNode,
    BusinessTermNode,
    Edge,
    GraphPayload,
)


class GraphBuilder:
    """
    Graph Builder normalizes raw extractor payloads into validated Pydantic
    Node and Edge models, maintaining deduplicated collections.
    """

    def __init__(self):
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, Edge] = {}

    def add_node(self, node: Node) -> None:
        """Add or update a node in the graph registry."""
        if node.id in self._nodes:
            # Merge properties if node already exists
            existing = self._nodes[node.id]
            existing.properties.update(node.properties)
            if node.description and not existing.description:
                existing.description = node.description
        else:
            self._nodes[node.id] = node

    def add_nodes(self, nodes: List[Node]) -> None:
        for n in nodes:
            self.add_node(n)

    def add_edge(self, edge: Edge) -> None:
        """Add an edge avoiding exact source-target-type duplicates."""
        edge_key = f"{edge.source_id}->{edge.type.value}->{edge.target_id}"
        if edge_key not in self._edges:
            self._edges[edge_key] = edge
        else:
            self._edges[edge_key].properties.update(edge.properties)

    def add_edges(self, edges: List[Edge]) -> None:
        for e in edges:
            self.add_edge(e)

    def ingesting_dbt(
        self,
        manifest_nodes: List[Dict[str, Any]],
        catalog_nodes: Optional[List[Dict[str, Any]]] = None,
        lineage_edges: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Build graph nodes and edges from raw dbt extractor outputs."""
        catalog_map = {c["id"]: c for c in (catalog_nodes or [])}

        for node_raw in manifest_nodes:
            node_id = node_raw["id"]
            node_type = node_raw.get("type")

            if node_type == "Dataset":
                cat_info = catalog_map.get(node_id, {})
                ds_node = DatasetNode(
                    id=node_id,
                    name=node_raw["name"],
                    database=node_raw.get("database"),
                    schema=node_raw.get("schema"),
                    description=node_raw.get("description"),
                    owner=node_raw.get("meta", {}).get("owner") or cat_info.get("owner"),
                )
                self.add_node(ds_node)

                # Extract Column nodes
                for col_name in node_raw.get("columns", []):
                    col_id = f"{node_id}.{col_name}"
                    col_node = ColumnNode(
                        id=col_id,
                        name=col_name,
                        dataset_id=node_id,
                    )
                    self.add_node(col_node)

            elif node_type == "Pipeline":
                pipe_node = PipelineNode(
                    id=node_id,
                    name=node_raw["name"],
                    description=node_raw.get("description"),
                    owner=node_raw.get("meta", {}).get("owner"),
                )
                self.add_node(pipe_node)

        # Process lineage edges
        if lineage_edges:
            for raw_edge in lineage_edges:
                edge_type = EdgeType(raw_edge.get("type", "DERIVED_FROM"))
                edge = Edge(
                    source_id=raw_edge["source"],
                    target_id=raw_edge["target"],
                    type=edge_type,
                )
                self.add_edge(edge)

    def ingesting_sql_catalog(
        self,
        tables: List[Dict[str, Any]],
        columns: List[Dict[str, Any]],
        foreign_keys: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Build graph nodes and edges from SQL INFORMATION_SCHEMA extractor outputs."""
        for tbl in tables:
            ds_node = DatasetNode(
                id=tbl["id"],
                name=tbl["table_name"],
                database=tbl.get("table_catalog"),
                schema=tbl.get("table_schema"),
                table_type=tbl.get("table_type", "BASE TABLE"),
            )
            self.add_node(ds_node)

        for col in columns:
            col_node = ColumnNode(
                id=col["id"],
                name=col["column_name"],
                dataset_id=col["dataset_id"],
                data_type=col.get("data_type"),
                is_nullable=col.get("is_nullable", True),
                ordinal_position=col.get("ordinal_position"),
            )
            self.add_node(col_node)

        if foreign_keys:
            for fk in foreign_keys:
                edge = Edge(
                    source_id=fk["source"],
                    target_id=fk["target"],
                    type=EdgeType.JOINS_WITH,
                    properties={"constraint_name": fk.get("constraint_name")},
                )
                self.add_edge(edge)

    def ingesting_query_logs(
        self,
        access_edges: List[Dict[str, Any]],
        join_edges: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Build graph edges and User nodes from query log extractor outputs."""
        for acc in access_edges:
            user_id = acc["target"]
            user_node = UserTeamNode(
                id=user_id,
                name=user_id.replace("user:", ""),
            )
            self.add_node(user_node)

            edge = Edge(
                source_id=acc["source"],
                target_id=user_id,
                type=EdgeType.CONSUMED_BY,
                properties={
                    "query_id": acc.get("query_id"),
                    "execution_time": acc.get("execution_time"),
                },
            )
            self.add_edge(edge)

        if join_edges:
            for j in join_edges:
                edge = Edge(
                    source_id=j["source"],
                    target_id=j["target"],
                    type=EdgeType.JOINS_WITH,
                    properties={"query_id": j.get("query_id")},
                )
                self.add_edge(edge)

    def ingesting_openlineage(self, event_data: Dict[str, Any]) -> None:
        """Build graph nodes and edges from parsed OpenLineage event outputs."""
        pipeline_id = event_data["pipeline_id"]
        pipeline_node = PipelineNode(
            id=pipeline_id,
            name=pipeline_id.split(".")[-1],
            resource_type="openlineage_job",
        )
        self.add_node(pipeline_node)

        for inp_ds in event_data.get("inputs", []):
            ds_node = DatasetNode(
                id=inp_ds,
                name=inp_ds.split(".")[-1],
            )
            self.add_node(ds_node)

        for out_ds in event_data.get("outputs", []):
            ds_node = DatasetNode(
                id=out_ds,
                name=out_ds.split(".")[-1],
            )
            self.add_node(ds_node)

        for raw_edge in event_data.get("edges", []):
            edge = Edge(
                source_id=raw_edge["source"],
                target_id=raw_edge["target"],
                type=EdgeType(raw_edge["type"]),
            )
            self.add_edge(edge)

    def to_payload(self) -> GraphPayload:
        """Return assembled GraphPayload containing all nodes and edges."""
        return GraphPayload(
            nodes=list(self._nodes.values()),
            edges=list(self._edges.values()),
        )
