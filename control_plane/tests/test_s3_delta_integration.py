"""Integration tests for Delta Lake storage over S3 with moto.

Tests end-to-end writing of Delta Lake tables (nodes, edges, vectors with dense embeddings)
directly to mock AWS S3 buckets using ArtifactWriter and querying them with DuckDBGraphStore
and DuckDBVectorStore, as well as multi-tenant S3 synchronization.
"""

import os
import socket
import tempfile
import shutil
import pytest
pytest.importorskip("moto")
import boto3
from moto.server import ThreadedMotoServer  # type: ignore

from core.models import Node, Edge, GraphPayload, NodeType, EdgeType
from core.writer import ArtifactWriter
from collection_agent.src.sync.s3_sync import S3Uploader, S3Downloader
from control_plane.src.query_engine.duckdb_store import (
    DuckDBGraphStore,
    get_available_timestamps,
    resolve_delta_or_parquet_table,
)
from control_plane.src.query_engine.duckdb_vector_store import DuckDBVectorStore


def get_free_port() -> int:
    """Finds an unused ephemeral port for ThreadedMotoServer."""
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def moto_s3_server():
    """Spins up a local threaded Moto S3 server on an ephemeral port for S3 Delta Lake tests."""
    port = get_free_port()
    server = ThreadedMotoServer("127.0.0.1", port)
    server.start()
    endpoint_url = f"http://127.0.0.1:{port}"

    storage_options = {
        "AWS_ENDPOINT_URL": endpoint_url,
        "AWS_ACCESS_KEY_ID": "mock-access-key",
        "AWS_SECRET_ACCESS_KEY": "mock-secret-key",
        "AWS_REGION": "us-east-1",
        "AWS_ALLOW_HTTP": "true",
        "AWS_S3_ALLOW_UNSAFE_RENAME": "true",
    }

    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id="mock-access-key",
        aws_secret_access_key="mock-secret-key",
    )

    yield {
        "server": server,
        "endpoint_url": endpoint_url,
        "storage_options": storage_options,
        "s3_client": s3_client,
    }

    server.stop()


def test_s3_direct_write_and_read_delta_with_vectors_and_embeddings(moto_s3_server):
    """Verifies that ArtifactWriter writes Delta Lake tables with dense vector embeddings
    directly to an S3 bucket and that DuckDBGraphStore and DuckDBVectorStore query them directly.
    """
    s3_client = moto_s3_server["s3_client"]
    storage_options = moto_s3_server["storage_options"]
    bucket_name = "lineagiq-direct-delta-lake"

    s3_client.create_bucket(Bucket=bucket_name)

    # 1. Create realistic lineage graph with dense embeddings
    nodes = [
        Node(
            id="db.raw.customers",
            name="raw_customers",
            type=NodeType.DATASET,
            description="Raw customer ingestion table",
            embedding=[0.90, 0.10, 0.00, 0.00],
            properties={"database": "analytics", "schema": "raw"},
        ),
        Node(
            id="db.stg.customers",
            name="stg_customers",
            type=NodeType.DATASET,
            description="Staged and deduplicated customer accounts",
            embedding=[0.85, 0.15, 0.00, 0.00],
            properties={"database": "analytics", "schema": "staging"},
        ),
        Node(
            id="db.marts.fct_mrr",
            name="fct_mrr",
            type=NodeType.DATASET,
            description="Monthly recurring revenue finance mart",
            embedding=[0.00, 0.00, 0.95, 0.05],
            properties={"database": "analytics", "schema": "marts"},
        ),
        Node(
            id="bi.dashboard.exec_mrr",
            name="exec_mrr_dashboard",
            type=NodeType.BUSINESS_TERM,
            description="Executive MRR and revenue dashboard",
            embedding=[0.00, 0.00, 0.90, 0.10],
            properties={"tool": "Tableau", "refresh_cadence": "hourly"},
        ),
    ]

    edges = [
        Edge(
            source_id="db.raw.customers",
            target_id="db.stg.customers",
            type=EdgeType.DERIVED_FROM,
            properties={"transformation": "dbt run --select stg_customers"},
        ),
        Edge(
            source_id="db.stg.customers",
            target_id="db.marts.fct_mrr",
            type=EdgeType.DERIVED_FROM,
            properties={"transformation": "dbt run --select fct_mrr"},
        ),
        Edge(
            source_id="db.marts.fct_mrr",
            target_id="bi.dashboard.exec_mrr",
            type=EdgeType.CONSUMED_BY,
            properties={"view_count": 42},
        ),
    ]

    payload = GraphPayload(nodes=nodes, edges=edges)

    s3_base_uri = f"s3://{bucket_name}/tenants/tenant_alpha"

    # 2. Write Delta Lake tables with vector embeddings directly to S3
    writer = ArtifactWriter()
    artifact_uris = writer.write_all(payload, base_dir=s3_base_uri, storage_options=storage_options)

    assert artifact_uris["nodes"] == f"{s3_base_uri}/graph/nodes"
    assert artifact_uris["edges"] == f"{s3_base_uri}/graph/edges"
    assert artifact_uris["vectors"] == f"{s3_base_uri}/vectors"

    # 3. Verify Delta Lake transaction logs and parquet part files exist in S3
    s3_objs = s3_client.list_objects_v2(Bucket=bucket_name, Prefix="tenants/tenant_alpha/")
    keys = [item["Key"] for item in s3_objs.get("Contents", [])]

    assert any("graph/nodes/_delta_log/00000000000000000000.json" in k for k in keys)
    assert any("graph/edges/_delta_log/00000000000000000000.json" in k for k in keys)
    assert any("vectors/_delta_log/00000000000000000000.json" in k for k in keys)
    assert any("vectors/part-" in k and k.endswith(".parquet") for k in keys)

    # 4. Query graph directly from S3 using DuckDBGraphStore
    graph_store = DuckDBGraphStore(s3_base_uri, storage_options=storage_options)

    # Test full graph
    graph = graph_store.get_full_graph()
    assert len(graph["nodes"]) == 4
    assert len(graph["edges"]) == 3
    node_ids = {n["id"] for n in graph["nodes"]}
    assert "db.raw.customers" in node_ids
    assert "db.marts.fct_mrr" in node_ids

    # Test downstream blast radius
    blast = graph_store.get_downstream_blast_radius("db.raw.customers", max_depth=5)
    assert blast["root_node"]["id"] == "db.raw.customers"
    assert len(blast["impacted_nodes"]) == 4
    assert blast["depth_reached"] == 3

    # Test upstream root cause
    root_cause = graph_store.get_upstream_root_cause("bi.dashboard.exec_mrr", max_depth=5)
    assert root_cause["target_node"]["id"] == "bi.dashboard.exec_mrr"
    upstream_ids = {n["id"] for n in root_cause["upstream_nodes"]}
    assert "db.raw.customers" in upstream_ids
    assert "db.stg.customers" in upstream_ids
    assert "db.marts.fct_mrr" in upstream_ids

    # Test get_nodes_by_ids
    retrieved = graph_store.get_nodes_by_ids(["db.marts.fct_mrr"])
    assert len(retrieved) == 1
    assert retrieved[0]["name"] == "fct_mrr"

    # Test search_nodes_by_terms
    matches = graph_store.search_nodes_by_terms("customers")
    match_ids = {m["id"] for m in matches}
    assert "db.raw.customers" in match_ids
    assert "db.stg.customers" in match_ids

    # 5. Query vector similarity directly from S3 using DuckDBVectorStore
    vector_store = DuckDBVectorStore(s3_base_uri, storage_options=storage_options)

    # Customer similarity search
    customer_query = [0.92, 0.08, 0.00, 0.00]
    top_customer_matches = vector_store.search_vectors(customer_query, top_k=2)
    assert len(top_customer_matches) == 2
    assert top_customer_matches[0] == "db.raw.customers"
    assert top_customer_matches[1] == "db.stg.customers"

    # Finance MRR similarity search
    mrr_query = [0.00, 0.00, 0.92, 0.08]
    top_mrr_matches = vector_store.search_vectors(mrr_query, top_k=2)
    assert len(top_mrr_matches) == 2
    assert set(top_mrr_matches) == {"db.marts.fct_mrr", "bi.dashboard.exec_mrr"}





def test_s3_delta_time_travel_versioning(moto_s3_server):
    """Verifies historical time travel queries over Delta Lake commit logs on S3."""
    s3_client = moto_s3_server["s3_client"]
    storage_options = moto_s3_server["storage_options"]
    bucket_name = "lineagiq-timetravel-lake"

    s3_client.create_bucket(Bucket=bucket_name)
    s3_base_uri = f"s3://{bucket_name}/tenants/tenant_history"

    writer = ArtifactWriter()

    # Commit Version 0: 2 initial nodes
    v0_nodes = [
        Node(id="orders_v1", name="orders_v1", type=NodeType.DATASET, description="V0 dataset", embedding=[0.5, 0.5]),
        Node(id="users_v1", name="users_v1", type=NodeType.DATASET, description="V0 dataset", embedding=[0.1, 0.9]),
    ]
    payload_v0 = GraphPayload(nodes=v0_nodes, edges=[])
    writer.write_all(payload_v0, base_dir=s3_base_uri, mode="overwrite", storage_options=storage_options)

    # Commit Version 1: 2 additional nodes appended
    v1_nodes = [
        Node(id="payments_v2", name="payments_v2", type=NodeType.DATASET, description="V1 dataset", embedding=[0.2, 0.8]),
        Node(id="analytics_v2", name="analytics_v2", type=NodeType.DATASET, description="V1 dataset", embedding=[0.3, 0.7]),
    ]
    payload_v1 = GraphPayload(nodes=v1_nodes, edges=[])
    writer.write_all(payload_v1, base_dir=s3_base_uri, mode="append", storage_options=storage_options)

    # Check commit history timestamps from S3
    timestamps = get_available_timestamps(s3_base_uri, storage_options=storage_options)
    assert len(timestamps) == 2
    assert timestamps[0]["version"] == 0
    assert timestamps[1]["version"] == 1

    # Query current state (version 1)
    store = DuckDBGraphStore(s3_base_uri, storage_options=storage_options)
    current_graph = store.get_full_graph()
    assert len(current_graph["nodes"]) == 4

    # Query historical state as of version 0 timestamp
    v0_iso = timestamps[0]["timestamp"]
    v0_graph = store.get_full_graph(as_of=v0_iso)
    assert len(v0_graph["nodes"]) == 2
    v0_ids = {n["id"] for n in v0_graph["nodes"]}
    assert "orders_v1" in v0_ids
    assert "users_v1" in v0_ids
    assert "payments_v2" not in v0_ids


def test_s3_sync_roundtrip_with_uploader_and_downloader(moto_s3_server):
    """Verifies that local Delta tables with embeddings can be synced to S3 with S3Uploader,
    retrieved with S3Downloader, and queried with DuckDBGraphStore and DuckDBVectorStore.
    """
    s3_client = moto_s3_server["s3_client"]
    bucket_name = "lineagiq-sync-roundtrip"
    s3_client.create_bucket(Bucket=bucket_name)

    temp_write_dir = tempfile.mkdtemp(prefix="lineagiq_write_")
    temp_read_dir = tempfile.mkdtemp(prefix="lineagiq_read_")

    try:
        # 1. Create graph with embeddings
        nodes = [
            Node(id="source_a", name="source_a", type=NodeType.DATASET, description="Source A", embedding=[0.99, 0.01]),
            Node(id="model_b", name="model_b", type=NodeType.DATASET, description="Model B", embedding=[0.95, 0.05]),
        ]
        edges = [
            Edge(source_id="source_a", target_id="model_b", type=EdgeType.DERIVED_FROM)
        ]
        payload = GraphPayload(nodes=nodes, edges=edges)

        # 2. Write locally
        writer = ArtifactWriter()
        writer.write_all(payload, base_dir=temp_write_dir)

        # 3. Upload to S3 with S3Uploader
        uploader = S3Uploader(bucket=bucket_name, prefix="lake", s3_client=s3_client)
        uploaded = uploader.sync_directory(temp_write_dir)
        assert len(uploaded) > 0

        # 4. Download from S3 with S3Downloader into clean temp_read_dir
        downloader = S3Downloader(bucket=bucket_name, prefix="lake", s3_client=s3_client)
        downloaded = downloader.download_directory(temp_read_dir)
        assert len(downloaded) == len(uploaded)

        # 5. Query downloaded tenant dataset with DuckDBGraphStore & DuckDBVectorStore
        store = DuckDBGraphStore(temp_read_dir)
        graph = store.get_full_graph()
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1

        vstore = DuckDBVectorStore(temp_read_dir)
        matches = vstore.search_vectors([0.98, 0.02], top_k=1)
        assert len(matches) == 1
        assert matches[0] == "source_a"

    finally:
        shutil.rmtree(temp_write_dir, ignore_errors=True)
        shutil.rmtree(temp_read_dir, ignore_errors=True)
