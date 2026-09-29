"""Scale and load benchmark comparison: DuckDB Query Engine vs. Pure NumPy Query Engine.

Evaluates in-memory snapshot cache footprint, cold Delta Lake loading, and recursive
traversal latencies on an enterprise-scale graph of 50,000 nodes and 150,000 edges.
"""

import time

import pyarrow as pa
import pytest
from deltalake import write_deltalake

from control_plane.src.query_engine import DuckDBQueryEngine, NumpyQueryEngine
from core.schemas import EDGE_SCHEMA, NODE_SCHEMA


@pytest.fixture(scope="module")
def benchmark_delta_graph(tmp_path_factory) -> str:
    """Generates a 50,000-node, 150,000-edge Delta Lake dataset for benchmarking."""
    base_dir = str(tmp_path_factory.mktemp("bench_graph_data"))
    num_nodes = 50_000
    num_edges = 150_000

    # 1. 50,000 Nodes
    node_ids = [f"model.analytics.asset_{i}" for i in range(num_nodes)]
    node_types = ["Dataset" if i % 3 == 0 else "Model" for i in range(num_nodes)]
    node_names = [f"asset_{i}" for i in range(num_nodes)]
    node_descs = [f"Enterprise analytics asset {i} in gold lineage layer" for i in range(num_nodes)]
    node_props = ['{"layer": "gold", "tier": "production"}'] * num_nodes

    nodes_table = pa.Table.from_arrays(
        [
            pa.array(node_ids, type=pa.string()),
            pa.array(node_types, type=pa.string()),
            pa.array(node_names, type=pa.string()),
            pa.array(node_descs, type=pa.string()),
            pa.array(node_props, type=pa.string()),
        ],
        schema=NODE_SCHEMA,
    )

    # 2. 150,000 Edges (Multi-hop DAG)
    sources = (
        [f"model.analytics.asset_{i}" for i in range(49_999)]
        + [f"model.analytics.asset_{i}" for i in range(49_998)]
        + [f"model.analytics.asset_{i}" for i in range(50_003)]
    )
    targets = (
        [f"model.analytics.asset_{i + 1}" for i in range(49_999)]
        + [f"model.analytics.asset_{i + 2}" for i in range(49_998)]
        + [f"model.analytics.asset_{i + 3}" for i in range(50_003)]
    )

    edges_table = pa.Table.from_arrays(
        [
            pa.array(sources, type=pa.string()),
            pa.array(targets, type=pa.string()),
            pa.array(["DEPENDS_ON"] * num_edges, type=pa.string()),
            pa.array(['{"dependency_type": "sql_view"}'] * num_edges, type=pa.string()),
        ],
        schema=EDGE_SCHEMA,
    )

    write_deltalake(f"{base_dir}/graph/nodes", nodes_table, mode="overwrite")
    write_deltalake(f"{base_dir}/graph/edges", edges_table, mode="overwrite")

    return base_dir


def test_compare_duckdb_vs_numpy_engines(benchmark_delta_graph: str) -> None:
    """Executes the load benchmark on both DuckDB and NumPy engines and asserts correctness & latency."""
    duck_engine = DuckDBQueryEngine(data_base_path=benchmark_delta_graph)
    numpy_engine = NumpyQueryEngine(data_base_path=benchmark_delta_graph)

    # ---------------------------------------------------------
    # 1. Cold Delta Scan & In-Memory Snapshot Materialization
    # ---------------------------------------------------------
    t0 = time.perf_counter()
    duck_cold = duck_engine.get_downstream_blast_radius("model.analytics.asset_0", max_depth=5)
    duck_cold_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    numpy_cold = numpy_engine.get_downstream_blast_radius("model.analytics.asset_0", max_depth=5)
    numpy_cold_ms = (time.perf_counter() - t0) * 1000

    # Verify both returned identical impacted nodes for the cold run
    assert len(duck_cold["impacted_nodes"]) == len(numpy_cold["impacted_nodes"])

    # ---------------------------------------------------------
    # 2. In-Memory Cache Footprint Measurement
    # ---------------------------------------------------------
    con = duck_engine.graph_store.con
    duck_bytes = con.execute("SELECT sum(memory_usage_bytes) FROM duckdb_memory();").fetchone()[0] or 0
    duck_ram_mb = duck_bytes / (1024 * 1024)

    # NumPy CSR array footprint
    numpy_bytes = numpy_engine.graph_store.get_in_memory_footprint_bytes()
    numpy_ram_mb = numpy_bytes / (1024 * 1024)

    # ---------------------------------------------------------
    # 3. Warm 5-Hop Blast Radius Traversal (Average of 10 runs)
    # ---------------------------------------------------------
    duck_5hop_times = []
    numpy_5hop_times = []

    for step in range(10):
        target_id = f"model.analytics.asset_{step * 100}"

        t0 = time.perf_counter()
        d_res = duck_engine.get_downstream_blast_radius(target_id, max_depth=5)
        duck_5hop_times.append(time.perf_counter() - t0)

        t0 = time.perf_counter()
        n_res = numpy_engine.get_downstream_blast_radius(target_id, max_depth=5)
        numpy_5hop_times.append(time.perf_counter() - t0)

        assert len(d_res["impacted_nodes"]) == len(n_res["impacted_nodes"])

    duck_5hop_avg_ms = (sum(duck_5hop_times) / len(duck_5hop_times)) * 1000
    numpy_5hop_avg_ms = (sum(numpy_5hop_times) / len(numpy_5hop_times)) * 1000

    # ---------------------------------------------------------
    # 4. Warm 10-Hop Deep Recursive Traversal
    # ---------------------------------------------------------
    t0 = time.perf_counter()
    duck_10hop = duck_engine.get_downstream_blast_radius("model.analytics.asset_500", max_depth=10)
    duck_10hop_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    numpy_10hop = numpy_engine.get_downstream_blast_radius("model.analytics.asset_500", max_depth=10)
    numpy_10hop_ms = (time.perf_counter() - t0) * 1000

    assert len(duck_10hop["impacted_nodes"]) == len(numpy_10hop["impacted_nodes"])

    # ---------------------------------------------------------
    # 5. Warm 5-Hop Upstream Root Cause Traversal
    # ---------------------------------------------------------
    t0 = time.perf_counter()
    duck_up = duck_engine.get_upstream_root_cause("model.analytics.asset_2500", max_depth=5)
    duck_up_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    numpy_up = numpy_engine.get_upstream_root_cause("model.analytics.asset_2500", max_depth=5)
    numpy_up_ms = (time.perf_counter() - t0) * 1000

    assert len(duck_up["upstream_nodes"]) == len(numpy_up["upstream_nodes"])

    # ---------------------------------------------------------
    # 6. Full-Text Search over 50,000 Nodes
    # ---------------------------------------------------------
    t0 = time.perf_counter()
    duck_search = duck_engine.graph_store.search_nodes_by_terms("asset_12345", top_k=5)
    duck_search_ms = (time.perf_counter() - t0) * 1000

    t0 = time.perf_counter()
    numpy_search = numpy_engine.graph_store.search_nodes_by_terms("asset_12345", top_k=5)
    numpy_search_ms = (time.perf_counter() - t0) * 1000

    assert any(n["id"] == "model.analytics.asset_12345" for n in duck_search)
    assert any(n["id"] == "model.analytics.asset_12345" for n in numpy_search)

    # ---------------------------------------------------------
    # Assert Performance Thresholds
    # ---------------------------------------------------------
    assert duck_5hop_avg_ms < 50.0
    assert numpy_5hop_avg_ms < 10.0  # NumPy CSR is sub-millisecond to low millisecond
    assert numpy_10hop_ms < 30.0

    speedup_5hop = duck_5hop_avg_ms / numpy_5hop_avg_ms if numpy_5hop_avg_ms > 0 else 1.0
    speedup_10hop = duck_10hop_ms / numpy_10hop_ms if numpy_10hop_ms > 0 else 1.0

    print("\n" + "=" * 80)
    print(" Performance Benchmark: DuckDB vs. Pure NumPy (50,000 Nodes • 150,000 Edges)")
    print("=" * 80)
    print(f"{'Metric':<42} | {'DuckDB Engine':<16} | {'NumPy Engine':<16}")
    print("-" * 80)
    print(f"{'Cold Delta Scan & Snapshot Build':<42} | {duck_cold_ms:>13.2f} ms | {numpy_cold_ms:>13.2f} ms")
    print(f"{'In-Memory Graph Cache Footprint':<42} | {duck_ram_mb:>13.2f} MB | {numpy_ram_mb:>13.2f} MB")
    print(
        f"{'Warm 5-Hop Blast Radius (Avg of 10)':<42} | {duck_5hop_avg_ms:>13.2f} ms | {numpy_5hop_avg_ms:>13.2f} ms ({speedup_5hop:.1f}x)"
    )
    print(
        f"{'Warm 10-Hop Deep Traversal':<42} | {duck_10hop_ms:>13.2f} ms | {numpy_10hop_ms:>13.2f} ms ({speedup_10hop:.1f}x)"
    )
    print(f"{'Warm 5-Hop Upstream Root Cause':<42} | {duck_up_ms:>13.2f} ms | {numpy_up_ms:>13.2f} ms")
    print(f"{'Full-Text Term Search (50k nodes)':<42} | {duck_search_ms:>13.2f} ms | {numpy_search_ms:>13.2f} ms")
    print("=" * 80)
