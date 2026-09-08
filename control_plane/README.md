# LineagIQ Control Plane & GraphRAG API

The **Control Plane** provides serverless graph traversal, historical time-travel analysis, and semantic vector search over tenant datasets stored in **Delta Lake** and **Parquet** formats.

Key Features:
* **DuckDB Delta Lake Graph Engine**: Resolves historical snapshot versions from Delta Lake transaction logs (`_delta_log/`) as of any ISO 8601 timestamp (`as_of`) and executes recursive CTE queries to calculate downstream blast radius and upstream root cause lineage.
* **Time Travel & Schema Drift Engine**: Computes detailed schema additions, removals, modifications, and altered lineage edges between historical timestamps ($T_1 \rightarrow T_2$).
* **Semantic Discovery & Vector Search**: Searches dense metadata vector indices (`vectors/`) against historical snapshot versions to locate relevant data assets.
* **GraphRAG Prompt Synthesizer**: Formats contextual graph traversals, historical diffs, and search results into structured LLM prompts for downstream AI analysis.
* **Agentic Retriever Tools**: Standalone retriever tools in `control_plane/src/agent_tools.py` for integration into LLM agent workflows (LangChain, AutoGen, LlamaIndex).
* **Interactive Visualizer with Timeline Scrubbing**: Web UI visualizer (`/visualizer`) featuring an interactive bottom overlay with a timeline slider for scrubbing back through graph commit history.
* **FastAPI Web Service**: Exposes REST endpoints for multi-tenant graph visualization, timeline commit logs, blast radius calculation, root cause analysis, schema diffing, semantic discovery, and GraphRAG chat.

---

## Directory Structure

```text
control_plane/
├── README.md
├── requirements.txt            # Control plane dependencies (FastAPI, DuckDB, deltalake)
├── src/
│   ├── query_engine/           # Modular Query Engine package
│   │   ├── base.py             # Abstract Base Classes (BaseGraphStore, BaseVectorStore)
│   │   ├── duckdb_store.py     # DuckDB Delta Lake Graph Store & Time Travel
│   │   ├── duckdb_vector_store.py # DuckDB Vector Store with historical time travel
│   │   └── engine.py           # DuckDBQueryEngine façade
│   ├── static/                 # Web Visualizer UI (index.html, style.css, script.js)
│   ├── prompt_synthesizer.py   # LLM prompt synthesis (Blast Radius, Root Cause, Diff, Discovery)
│   ├── agent_tools.py          # Agentic Retriever Tools & LineagIQGraphRAGClient
│   └── main.py                 # FastAPI application endpoints
└── tests/
    ├── test_agent_tools.py     # Unit tests for Agentic Retriever Tools
    ├── test_api.py             # Integration tests for FastAPI endpoints
    ├── test_query_engine.py    # Unit tests for query engine & prompt synthesis
    └── test_time_travel.py     # Unit tests for Delta Lake commits, historical time travel, and diffing
```

---

## REST API Endpoints

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/healthz` | `GET` | Health check endpoint |
| `/visualizer` | `GET` | Interactive Knowledge Graph Visualizer & Timeline Slider UI |
| `/api/v1/tenants/{tenant_id}/timeline` | `GET` | Fetches available Delta Lake commit timestamps for UI timeline scrubbing |
| `/api/v1/tenants/{tenant_id}/graph` | `GET` | Returns full graph nodes and edges as of optional `as_of` ISO 8601 timestamp |
| `/api/v1/tenants/{tenant_id}/blast-radius` | `POST` | Calculates downstream operational blast radius as of optional `as_of` timestamp |
| `/api/v1/tenants/{tenant_id}/root-cause` | `POST` | Calculates upstream root cause lineage as of optional `as_of` timestamp |
| `/api/v1/tenants/{tenant_id}/discovery` | `POST` | Semantic vector search over data assets as of optional `as_of` timestamp |
| `/api/v1/tenants/{tenant_id}/time-travel/diff` | `POST` | Computes historical schema drift & lineage diff between $T_1$ and $T_2$ |
| `/api/v1/tenants/{tenant_id}/chat` | `POST` | Interactive GraphRAG LLM Lineage Chat assistant |

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
def blast_radius_tool(tenant_id: str, dataset_id: str) -> str:
    """Calculates downstream operational blast radius for a data asset before schema modifications or deployments."""
    return get_dataset_blast_radius(tenant_id=tenant_id, dataset_id=dataset_id, data_path="/tmp/tenants/demo_tenant")

@tool
def time_travel_diff_tool(tenant_id: str, node_id: str, timestamp_t1: str, timestamp_t2: str) -> str:
    """Computes schema additions, deletions, and lineage edge changes between historical timestamps T1 and T2."""
    return get_lineage_time_travel_diff(
        tenant_id=tenant_id,
        node_id=node_id,
        timestamp_t1=timestamp_t1,
        timestamp_t2=timestamp_t2,
        data_path="/tmp/tenants/demo_tenant",
    )

@tool
def data_discovery_tool(tenant_id: str, search_query: str) -> str:
    """Searches enterprise datasets, columns, and pipelines for semantic discovery and schema details."""
    return search_enterprise_data_catalog(tenant_id=tenant_id, query=search_query, data_path="/tmp/tenants/demo_tenant")
```

### 2. End-to-End Agent Execution Flow with OpenAI / LLMs

```python
from openai import OpenAI
from control_plane.src.agent_tools import LineagIQGraphRAGClient

# 1. Initialize LineagIQ GraphRAG Client
client = LineagIQGraphRAGClient()

# 2. Retrieve Historical Time Travel Diff Prompt for a target dataset
synthesized_prompt = client.get_time_travel_diff_prompt(
    tenant_id="demo_tenant",
    node_id="model.jaffle_shop.stg_customers",
    timestamp_t1="2026-09-08T08:00:00Z",
    timestamp_t2="2026-09-08T10:00:00Z",
    data_path="/tmp/tenants/demo_tenant"
)

# 3. Pass Synthesized Prompt to LLM Provider
openai_client = OpenAI(api_key="your-openai-api-key")
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are LineagIQ AI Agent, an expert enterprise data architect."},
        {"role": "user", "content": synthesized_prompt}
    ],
    temperature=0.1
)

print("AI AGENT TIME TRAVEL DRIFT ANALYSIS:")
print(response.choices[0].message.content)
```
