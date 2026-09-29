# LineagIQ Control Plane & GraphRAG API

The **Control Plane** provides serverless graph traversal, historical time-travel analysis, and semantic vector search over tenant datasets stored in **Delta Lake** and **Parquet** formats.

Key Features:
* **DuckDB Delta Lake Graph Engine**: Resolves historical snapshot versions from Delta Lake transaction logs (`_delta_log/`) as of any ISO 8601 timestamp (`as_of`) and executes recursive CTE queries to calculate downstream blast radius and upstream root cause lineage.
* **Time Travel & Schema Drift Engine**: Computes detailed schema additions, removals, modifications, and altered lineage edges between historical timestamps ($T_1 \rightarrow T_2$).
* **Semantic Discovery & Vector Search**: Searches dense metadata vector indices (`vectors/`) against historical snapshot versions to locate relevant data assets.
* **GraphRAG Prompt Synthesizer**: Formats contextual graph traversals, historical diffs, and search results into structured LLM prompts for downstream AI analysis.
* **Agentic Retriever Tools**: Standalone retriever tools in `control_plane/src/agent_tools.py` for integration into LLM agent workflows (LangChain, AutoGen, LlamaIndex).
* **LineagIQ AI Assistant (Dynamic Docking & Ollama Support)**: Interactive GraphRAG AI assistant drawer dynamically docking to the right edge with automatic sidebar offset adaptation, supporting local models (Ollama on `11434`), OpenAI, and Google Gemini.
* **Decoupled Core Architecture**: Imports domain models, vector embeddings, and storage schemas directly from `core`, with 0 coupling to `collection_agent`.
* **FastAPI Web Service**: Exposes REST endpoints for multi-tenant graph visualization, timeline commit logs, blast radius calculation, root cause analysis, schema diffing, semantic discovery, and GraphRAG chat.

---

## Directory Structure

```text
control_plane/
├── README.md
├── requirements.txt            # Control plane dependencies (FastAPI, DuckDB, deltalake)
├── src/
│   ├── query_engine/           # Modular Query Engine package
│   │   ├── base.py             # Abstract Base Classes (BaseGraphStore, BaseVectorStore, BaseQueryEngine)
│   │   ├── duckdb/             # Dedicated DuckDB implementation package
│   │   │   ├── connection.py   # Connection pooling, extensions, S3/IAM credentials
│   │   │   ├── delta.py        # Delta table attaching & in-memory snapshot materialization
│   │   │   ├── graph_store.py  # DuckDBGraphStore implementing BaseGraphStore
│   │   │   └── vector_store.py # DuckDBVectorStore implementing BaseVectorStore
│   │   ├── numpy/              # Pure NumPy & Arrow Delta Lake implementation package
│   │   │   ├── graph_store.py  # NumpyGraphStore (CSR/CSC multi-hop traversal & reachability)
│   │   │   └── vector_store.py # NumpyVectorStore (BLAS dot-product cosine similarity & top-k)
│   │   └── engine.py           # DuckDBQueryEngine / UnifiedQueryEngine
│   ├── static/                 # Web Visualizer UI (index.html, style.css, script.js)
│   ├── prompt_synthesizer.py   # LLM prompt synthesis (Blast Radius, Root Cause, Diff, Discovery)
│   ├── agent_tools.py          # Agentic Retriever Tools & LineagIQGraphRAGClient
│   └── main.py                 # FastAPI application endpoints
└── tests/
    ├── script.test.js               # Node.js unit tests for extracted client script.js
    ├── test_agent_tools.py          # Unit tests for Agentic Retriever Tools
    ├── test_api.py                  # Integration tests for FastAPI endpoints
    ├── test_query_engine.py         # Unit tests for query engine & prompt synthesis
    ├── test_scale_duckdb.py         # Scale & load benchmark (50,000 nodes • 150,000 edges)
    ├── test_scale_duckdb_vs_numpy.py # Comparative benchmark: DuckDB vs Pure NumPy on Delta Lake
    └── test_time_travel.py          # Unit tests for Delta Lake commits, historical time travel, and diffing
```

---

## REST API Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/healthz` | `GET` | Health check endpoint |
| `/visualizer` | `GET` | Interactive Knowledge Graph Visualizer & Timeline Slider UI |
| `/api/v1/timeline` | `GET` | Fetches available Delta Lake commit timestamps for UI timeline scrubbing |
| `/api/v1/graph` | `GET` | Returns full graph nodes and edges as of optional `as_of` ISO 8601 timestamp |
| `/api/v1/blast-radius` | `POST` | Calculates downstream operational blast radius as of optional `as_of` timestamp |
| `/api/v1/root-cause` | `POST` | Calculates upstream root cause lineage as of optional `as_of` timestamp |
| `/api/v1/discovery` | `POST` | Semantic vector search over data assets as of optional `as_of` timestamp |
| `/api/v1/time-travel/diff` | `POST` | Computes historical schema drift & lineage diff between $T_1$ and $T_2$ |
| `/api/v1/chat` | `POST` | Interactive GraphRAG LLM Lineage Chat assistant |

---

## Agentic AI & Tool Integration

LineagIQ Control Plane provides retriever tools (`control_plane/src/agent_tools.py`) designed to be registered directly with LLM Agent frameworks like **LangChain**, **LlamaIndex**, **AutoGen**, or custom AI agent loops.

### 1. Registering Tools with LangChain / AI Agents

```python
from langchain.tools import tool
from control_plane.src.agent_tools import (
    get_dataset_blast_radius,
    get_lineage_time_travel_diff,
    search_enterprise_data_catalog,
)


@tool
def blast_radius_tool(dataset_id: str) -> str:
    """Calculates downstream operational blast radius for a data asset before schema modifications or deployments."""
    return get_dataset_blast_radius(dataset_id=dataset_id)


@tool
def time_travel_diff_tool(node_id: str, timestamp_t1: str, timestamp_t2: str) -> str:
    """Computes schema additions, deletions, and lineage edge changes between historical timestamps T1 and T2."""
    return get_lineage_time_travel_diff(
        node_id=node_id,
        timestamp_t1=timestamp_t1,
        timestamp_t2=timestamp_t2,
    )


@tool
def data_discovery_tool(search_query: str) -> str:
    """Searches enterprise datasets, columns, and pipelines for semantic discovery and schema details."""
    return search_enterprise_data_catalog(query=search_query)
```

### 2. End-to-End Agent Execution Flow with OpenAI / LLMs

```python
from openai import OpenAI
from control_plane.src.agent_tools import LineagIQGraphRAGClient

# 1. Initialize LineagIQ GraphRAG Client
client = LineagIQGraphRAGClient()

# 2. Retrieve Historical Time Travel Diff Prompt for a target dataset
synthesized_prompt = client.get_time_travel_diff_prompt(
    node_id="model.jaffle_shop.stg_customers",
    timestamp_t1="2026-09-08T08:00:00Z",
    timestamp_t2="2026-09-08T10:00:00Z",
)

# 3. Pass Synthesized Prompt to LLM Provider
openai_client = OpenAI(api_key="your-openai-api-key")
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are LineagIQ AI Agent, an expert enterprise data architect."},
        {"role": "user", "content": synthesized_prompt},
    ],
    temperature=0.1,
)

print("AI AGENT TIME TRAVEL DRIFT ANALYSIS:")
print(response.choices[0].message.content)
```

---

## Storage Engine Architecture: DuckDB vs Pure NumPy on Delta Lake

LineagIQ supports dual storage engine implementations behind the unified `BaseGraphStore` and `BaseVectorStore` interfaces:

1. **`DuckDBGraphStore` & `DuckDBVectorStore`**:
   - Leverages DuckDB's native Delta Lake extension (`delta`) and Parquet readers directly via in-memory duckdb connections.
   - Executes recursive SQL Common Table Expressions (`WITH RECURSIVE`) for lineage traversals.
   - Ideal for SQL-driven data teams requiring zero custom data structures and immediate queryability.

2. **`NumpyGraphStore` & `NumpyVectorStore`**:
   - Directly reads Delta Lake transaction logs (`_delta_log/`) and Parquet data files using `deltalake.DeltaTable` and PyArrow.
   - Compiles graph topology into **Compressed Sparse Row (CSR)** for downstream blast radius and **Compressed Sparse Column (CSC)** for upstream root cause lineage.
   - Computes semantic vector similarity using high-performance vectorized BLAS dot-product operations with `np.argpartition` for $O(K)$ top-k extraction.
   - Yields microsecond traversal latencies with an ultra-compact memory footprint.

### Benchmark Comparison (50,000 Nodes • 150,000 Edges on Delta Lake)

| Performance & Memory Metric | DuckDB Engine | NumPy (CSR / CSC) Engine | Speedup / Efficiency |
| :--- | :---: | :---: | :---: |
| **Cold Delta Lake Table Read** | ~65 ms | ~150 ms | DuckDB C++ reader is ~2.3x faster for initial bulk cold scans |
| **In-Memory Cache RAM Footprint** | ~28.5 MB | **~1.5 MB** | **NumPy is ~18.6x more memory efficient** |
| **Warm 5-Hop Blast Radius Traversal** | ~3.4 ms | **~0.02 ms** | **NumPy is ~170x–190x faster** (direct array slices) |
| **Warm 10-Hop Deep Graph Traversal** | ~8.7 ms | **~0.04 ms** | **NumPy is ~220x–250x faster** |
| **Warm 5-Hop Upstream Root Cause** | ~3.6 ms | **~0.02 ms** | **NumPy is ~180x faster** (CSC backward index) |
| **Full-Text Keyword Search (50k nodes)** | ~13.4 ms | ~14.5 ms | Comparable performance |
