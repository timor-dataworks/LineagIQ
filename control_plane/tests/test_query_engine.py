import os
from collection_agent.src.transform import (
    DatasetNode,
    PipelineNode,
    ColumnNode,
    Edge,
    EdgeType,
    GraphPayload,
)
from collection_agent.src.storage.writer import ArtifactWriter
from control_plane.src.query_engine import DuckDBQueryEngine
from control_plane.src.prompt_synthesizer import PromptSynthesizer


def test_duckdb_blast_radius_traversal(tmp_path):
    # Construct a sample graph: Raw Customers -> Stg Customers Model -> Orders Model
    raw_ds = DatasetNode(id="raw.customers", name="raw_customers", description="Raw landing table")
    stg_pipe = PipelineNode(id="dbt.stg_customers", name="stg_customers", resource_type="model")
    stg_ds = DatasetNode(id="analytics.stg_customers", name="stg_customers", description="Staged customers")
    orders_pipe = PipelineNode(id="dbt.orders", name="orders", resource_type="model")

    edge1 = Edge(source_id="raw.customers", target_id="dbt.stg_customers", type=EdgeType.CONSUMED_BY)
    edge2 = Edge(source_id="dbt.stg_customers", target_id="analytics.stg_customers", type=EdgeType.PRODUCED_BY)
    edge3 = Edge(source_id="analytics.stg_customers", target_id="dbt.orders", type=EdgeType.CONSUMED_BY)

    payload = GraphPayload(
        nodes=[raw_ds, stg_pipe, stg_ds, orders_pipe],
        edges=[edge1, edge2, edge3],
    )

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    engine = DuckDBQueryEngine(data_base_path=str(tmp_path))
    result = engine.get_downstream_blast_radius("raw.customers", max_depth=5)

    assert result["root_node"]["id"] == "raw.customers"
    assert len(result["impacted_nodes"]) == 4
    assert len(result["edges"]) == 3
    assert result["depth_reached"] == 3

    # Test Prompt Synthesis
    synthesizer = PromptSynthesizer()
    prompt = synthesizer.synthesize_blast_radius_prompt(
        start_node=result["root_node"],
        impacted_nodes=result["impacted_nodes"],
        edges=result["edges"],
    )

    assert "LINEAGIQ GRAPHRAG PROMPT" in prompt
    assert "raw_customers" in prompt
    assert "dbt.orders" in prompt


def test_duckdb_vector_semantic_search(tmp_path):
    from collection_agent.src.embedder.local_embedder import LocalEmbedder

    ds = DatasetNode(id="db.users", name="users", description="User dimension dataset")
    col = ColumnNode(id="db.users.email", name="email", dataset_id="db.users", data_type="VARCHAR")
    payload = GraphPayload(nodes=[ds, col], edges=[])

    embedder = LocalEmbedder()
    payload = embedder.embed_payload(payload)

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    engine = DuckDBQueryEngine(data_base_path=str(tmp_path))
    results = engine.search_semantic_assets("email address", top_k=5)

    node_ids = [r["id"] for r in results]
    assert "db.users.email" in node_ids
    assert "db.users" in node_ids  # Parent dataset resolved


def test_hybrid_semantic_search_with_parent_resolution(tmp_path):
    from collection_agent.src.embedder.local_embedder import LocalEmbedder

    ds = DatasetNode(id="db.orders", name="orders", description="Fact orders")
    col = ColumnNode(id="db.orders.order_id", name="order_id", dataset_id="db.orders")
    payload = GraphPayload(nodes=[ds, col], edges=[])

    embedder = LocalEmbedder()
    payload = embedder.embed_payload(payload)

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    engine = DuckDBQueryEngine(data_base_path=str(tmp_path))
    results = engine.search_semantic_assets("find order_id", top_k=5)

    matched_ids = {r["id"] for r in results}
    assert "db.orders.order_id" in matched_ids
    assert "db.orders" in matched_ids


def test_duckdb_upstream_root_cause_traversal(tmp_path):
    # Construct graph: Raw Customers -> Stg Customers Model -> Orders Model
    raw_ds = DatasetNode(id="raw.customers", name="raw_customers", description="Raw landing table")
    stg_pipe = PipelineNode(id="dbt.stg_customers", name="stg_customers", resource_type="model")
    stg_ds = DatasetNode(id="analytics.stg_customers", name="stg_customers", description="Staged customers")
    orders_pipe = PipelineNode(id="dbt.orders", name="orders", resource_type="model")

    edge1 = Edge(source_id="raw.customers", target_id="dbt.stg_customers", type=EdgeType.CONSUMED_BY)
    edge2 = Edge(source_id="dbt.stg_customers", target_id="analytics.stg_customers", type=EdgeType.PRODUCED_BY)
    edge3 = Edge(source_id="analytics.stg_customers", target_id="dbt.orders", type=EdgeType.CONSUMED_BY)

    payload = GraphPayload(
        nodes=[raw_ds, stg_pipe, stg_ds, orders_pipe],
        edges=[edge1, edge2, edge3],
    )

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    engine = DuckDBQueryEngine(data_base_path=str(tmp_path))
    result = engine.get_upstream_root_cause("dbt.orders", max_depth=5)

    assert result["target_node"]["id"] == "dbt.orders"
    assert len(result["upstream_nodes"]) == 4
    assert len(result["edges"]) == 3
    assert result["depth_reached"] == 3

    # Test Prompt Synthesis
    synthesizer = PromptSynthesizer()
    prompt = synthesizer.synthesize_root_cause_prompt(
        target_node=result["target_node"],
        upstream_nodes=result["upstream_nodes"],
        edges=result["edges"],
    )

    assert "UPSTREAM ROOT CAUSE" in prompt
    assert "dbt.orders" in prompt
    assert "raw_customers" in prompt


def test_upstream_root_cause_filters_belongs_to_and_synthesizes_missing_nodes(tmp_path):
    # Construct graph simulating the issue:
    # stg_customers dataset has 2 columns pointing to it via BELONGS_TO,
    # and 1 raw source dataset (source.raw_customers) pointing to it via DERIVED_FROM (missing from nodes.parquet).
    stg_ds = DatasetNode(id="model.stg_customers", name="stg_customers", description="Staged customers")
    col1 = ColumnNode(id="model.stg_customers.customer_id", name="customer_id", dataset_id="model.stg_customers")
    col2 = ColumnNode(id="model.stg_customers.first_name", name="first_name", dataset_id="model.stg_customers")

    edge_col1 = Edge(source_id="model.stg_customers.customer_id", target_id="model.stg_customers", type=EdgeType.BELONGS_TO)
    edge_col2 = Edge(source_id="model.stg_customers.first_name", target_id="model.stg_customers", type=EdgeType.BELONGS_TO)
    edge_derived = Edge(source_id="source.raw_customers", target_id="model.stg_customers", type=EdgeType.DERIVED_FROM)

    # Note: source.raw_customers is intentionally left out of nodes list to test synthesis
    payload = GraphPayload(
        nodes=[stg_ds, col1, col2],
        edges=[edge_col1, edge_col2, edge_derived],
    )

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    engine = DuckDBQueryEngine(data_base_path=str(tmp_path))

    # Test get_upstream_root_cause
    result = engine.get_upstream_root_cause("model.stg_customers", max_depth=5)

    node_ids = {n["id"] for n in result["upstream_nodes"]}

    # Must NOT include child columns
    assert "model.stg_customers.customer_id" not in node_ids
    assert "model.stg_customers.first_name" not in node_ids

    # MUST include target dataset and synthesized raw source node
    assert "model.stg_customers" in node_ids
    assert "source.raw_customers" in node_ids
    assert len(result["upstream_nodes"]) == 2
    assert len(result["edges"]) == 1
    assert result["edges"][0]["type"] == "DERIVED_FROM"

    # Test get_full_graph missing node synthesis
    full_graph = engine.get_full_graph()
    full_node_ids = {n["id"] for n in full_graph["nodes"]}
    assert "source.raw_customers" in full_node_ids

    # Test get_downstream_blast_radius starting from Column node customer_id
    blast_res = engine.get_downstream_blast_radius("model.stg_customers.customer_id", max_depth=5)
    blast_ids = {n["id"] for n in blast_res["impacted_nodes"]}
    assert "model.stg_customers.customer_id" in blast_ids
    assert "model.stg_customers" in blast_ids
    assert len(blast_res["impacted_nodes"]) == 2


def test_pluggable_stores_architecture(tmp_path):
    from control_plane.src.query_engine import BaseGraphStore, BaseVectorStore

    class CustomMockGraphStore(BaseGraphStore):
        def get_full_graph(self):
            return {"nodes": [{"id": "mock.node", "name": "mock_node", "type": "Dataset"}], "edges": []}

        def get_downstream_blast_radius(self, start_node_id: str, max_depth: int = 5):
            return {"impacted_nodes": [{"id": start_node_id}], "edges": [], "root_node": {"id": start_node_id}, "depth_reached": 1}

        def get_upstream_root_cause(self, start_node_id: str, max_depth: int = 5):
            return {"upstream_nodes": [{"id": start_node_id}], "edges": [], "target_node": {"id": start_node_id}, "depth_reached": 1}

        def get_nodes_by_ids(self, node_ids):
            return [{"id": nid, "name": nid, "type": "Dataset"} for nid in node_ids]

        def search_nodes_by_terms(self, query_text: str, top_k: int = 5):
            return [{"id": "mock.searched_node", "name": query_text, "type": "Dataset"}]

    class CustomMockVectorStore(BaseVectorStore):
        def search_vectors(self, query_vector, top_k: int = 5):
            return ["mock.vector_node"]

    mock_graph = CustomMockGraphStore()
    mock_vector = CustomMockVectorStore()

    engine = DuckDBQueryEngine(
        data_base_path=str(tmp_path),
        graph_store=mock_graph,
        vector_store=mock_vector,
    )

    full = engine.get_full_graph()
    assert full["nodes"][0]["id"] == "mock.node"

    blast = engine.get_downstream_blast_radius("custom.node")
    assert blast["root_node"]["id"] == "custom.node"

    semantic = engine.search_semantic_assets("test query")
    assert semantic[0]["id"] == "mock.vector_node"


def test_duckdb_vss_vector_store(tmp_path):
    from collection_agent.src.embedder.local_embedder import LocalEmbedder
    from control_plane.src.query_engine import DuckDBVectorStore

    ds = DatasetNode(id="db.customers", name="customers", description="Customer dataset")
    col = ColumnNode(id="db.customers.email", name="email", dataset_id="db.customers")
    payload = GraphPayload(nodes=[ds, col], edges=[])

    embedder = LocalEmbedder()
    payload = embedder.embed_payload(payload)

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    vstore = DuckDBVectorStore(data_base_path=str(tmp_path))

    query_vec = embedder.embed_text("email address")
    results = vstore.search_vectors(query_vec, top_k=5)

    assert len(results) > 0


def test_semantic_search_raw_customers_edge_node_ranking(tmp_path):
    from collection_agent.src.embedder.local_embedder import LocalEmbedder
    from collection_agent.src.transform.graph_builder import GraphBuilder

    builder = GraphBuilder()
    stg_ds = DatasetNode(id="model.jaffle_shop.stg_customers", name="stg_customers", description="Staged customer records")
    builder.add_node(stg_ds)

    # Add lineage edge referencing implicit external source node source.jaffle_shop.raw_customers
    builder.add_edge(Edge(
        source_id="source.jaffle_shop.raw_customers",
        target_id="model.jaffle_shop.stg_customers",
        type=EdgeType.DERIVED_FROM
    ))

    payload = builder.to_payload()
    embedder = LocalEmbedder()
    payload = embedder.embed_payload(payload)

    writer = ArtifactWriter()
    writer.write_all(payload, str(tmp_path))

    engine = DuckDBQueryEngine(data_base_path=str(tmp_path))
    results = engine.search_semantic_assets("raw_customers", top_k=5)

    assert len(results) > 0
    # Must rank source.jaffle_shop.raw_customers first
    assert results[0]["id"] == "source.jaffle_shop.raw_customers"
    assert results[0]["name"] == "raw_customers"







