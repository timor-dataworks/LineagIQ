# LineagIQ Control Plane & GraphRAG API

The **Control Plane** provides serverless graph traversal, historical time-travel analysis, and semantic vector search over tenant datasets stored in **Delta Lake** and **Parquet** formats.

Key Features:
* **Unified NumPy & Delta Lake Graph Engine**: Resolves historical snapshot versions from Delta Lake transaction logs (`_delta_log/`) as of any ISO 8601 timestamp (`as_of`) and executes ultra-fast CSR/CSC array traversals to calculate downstream blast radius and upstream root cause lineage.
* **Time Travel & Schema Drift Engine**: Computes detailed schema additions, removals, modifications, and altered lineage edges between historical timestamps ($T_1 \rightarrow T_2$).
* **Semantic Discovery & Vector Search**: Searches dense metadata vector indices (`vectors/`) against historical snapshot versions via vectorized BLAS cosine similarity with `UnifiedQueryEngine`.
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
├── requirements.txt            # Control plane dependencies (FastAPI, NumPy, deltalake, pyarrow)
├── src/
│   ├── query_engine/           # Modular Query Engine package
│   │   ├── base.py             # Abstract Base Classes (BaseGraphStore, BaseVectorStore, BaseQueryEngine)
│   │   ├── numpy/              # Pure NumPy & Arrow Delta Lake implementation package
│   │   │   ├── engine.py       # NumpyQueryEngine orchestrating graph & vector stores
│   │   │   ├── graph_store.py  # NumpyGraphStore (CSR/CSC multi-hop traversal & reachability)
│   │   │   └── vector_store.py # NumpyVectorStore (BLAS dot-product cosine similarity & top-k)
│   │   └── engine.py           # Engine façade exporting UnifiedQueryEngine & QueryEngine
│   ├── static/                 # Web Visualizer UI (index.html, style.css, script.js)
│   ├── prompt_synthesizer.py   # LLM prompt synthesis (Blast Radius, Root Cause, Diff, Discovery)
│   ├── agent_tools.py          # Agentic Retriever Tools & LineagIQGraphRAGClient
│   └── main.py                 # FastAPI application endpoints
└── tests/
    ├── script.test.js          # Node.js unit tests for extracted client script.js
    ├── test_agent_tools.py     # Unit tests for Agentic Retriever Tools
    ├── test_api.py             # Integration tests for FastAPI endpoints
    ├── test_query_engine.py    # Unit tests for query engine & prompt synthesis
    ├── test_scale_numpy.py     # Scale & load benchmark (50,000 nodes • 150,000 edges)
    └── test_time_travel.py     # Unit tests for Delta Lake commits, historical time travel, and diffing
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

## Storage Engine Architecture: Pure NumPy on Delta Lake (`UnifiedQueryEngine`)

LineagIQ operates on high-performance in-memory graph structures directly backed by Delta Lake storage:

* **Delta Lake Native Ingestion**: Reads Delta Lake transaction logs (`_delta_log/`) and columnar Parquet tables using `deltalake.DeltaTable` and Apache Arrow zero-copy memory buffers.
* **Dual CSR/CSC Topology Layout**:
  * **Compressed Sparse Row (CSR)** for downstream blast radius analysis: Direct contiguous index slices `targets[indptr[u]:indptr[u+1]]`.
  * **Compressed Sparse Column (CSC)** for upstream root cause analysis: Backward reachability index for instantaneous ancestor lineage resolution.
* **Vectorized Cosine Similarity**: Materializes 2D float32 normalized embeddings in contiguous RAM and executes BLAS dot-product matrix multiplications with `np.argpartition` for $O(K)$ candidate retrieval.
* **Unified Query Interface**: Accessible via `UnifiedQueryEngine` and `QueryEngine` aliases implementing `BaseQueryEngine`.

### Scale Benchmark (50,000 Nodes • 150,000 Edges on Delta Lake)

| Performance & Memory Metric | Value | Architectural Benefit |
| :--- | :---: | :--- |
| **In-Memory Cache RAM Footprint** | **~1.5 MB** | 18.6x more compact than tabular database engines |
| **Cold Delta Lake Load & Snapshot Build** | **~145 ms** | Direct Arrow memory transfer from Parquet files |
| **Warm 5-Hop Blast Radius Traversal** | **~0.02 ms** (20 µs) | Instantaneous array indexing bypassing SQL parsing |
| **Warm 10-Hop Deep Graph Traversal** | **~0.04 ms** (40 µs) | Microsecond multi-hop graph reachability |
| **Warm 5-Hop Upstream Root Cause** | **~0.02 ms** (20 µs) | Backward CSC index eliminates reverse scan overhead |
| **Keyword & Subgraph Search (50k nodes)** | **~14 ms** | In-memory token matching over metadata fields |

