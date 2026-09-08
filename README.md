# LineagIQ: Enterprise Semantic Knowledge Graph Platform

LineagIQ models an enterprise data landscape into a contextual knowledge graph. It decouples the core semantic and graph engine from tenant-specific operational data using a two-tier architecture:

1. **Stateless Ingestion Agent (`collection_agent`)**: An ephemeral edge metadata collector that extracts, embeds (via local ONNX INT8), formats (Delta Lake / Parquet), and syncs metadata inside the customer environment.
2. **Serverless S3 Control Plane (`control_plane`)**: A multi-tenant query engine powered by DuckDB and Delta Lake exposing FastAPI endpoints, interactive web visualization with time travel timeline scrubbing, and Agentic AI tools for GraphRAG prompt synthesis (downstream blast-radius, upstream root cause, historical schema drift diffing, and semantic discovery).

---

## Repository Architecture

```text
LineagIQ/
├── collection_agent/           # Ephemeral Ingestion Agent
│   ├── README.md               # Collection Agent documentation
│   ├── ARCHITECTURE.md          # Architectural specification
│   ├── requirements.txt        # Agent dependencies
│   ├── src/                    # Extractors, Transform, Embedder, Storage, Sync, CLI
│   └── tests/                  # Pytest test suite & mock fixtures
│
├── control_plane/              # Serverless Query Plane & GraphRAG API
│   ├── README.md               # Control Plane documentation
│   ├── requirements.txt        # Control plane dependencies
│   ├── src/                    # DuckDB Query Engine, Prompt Synthesizer, Agent Tools, FastAPI App, Web Visualizer
│   │   ├── query_engine/       # Base interfaces, DuckDB Graph Store, DuckDB Vector Store, Engine façade
│   │   ├── static/             # Web Visualizer UI (index.html, style.css, script.js)
│   │   ├── agent_tools.py      # Retriever tools for LLM frameworks
│   │   ├── prompt_synthesizer.py # GraphRAG prompt generators
│   │   └── main.py             # FastAPI endpoints & route handlers
│   └── tests/                  # Pytest unit & integration test suite (test_time_travel.py, test_api.py, etc.)
│
├── documentation/              # High-level developer & architectural specs
│   └── project overview.md
└── requirements.txt            # Root dependencies
```

---

## Time Travel & Historical Schema Drift Analysis

LineagIQ supports **Time Travel** over schema changes and lineage graph versions using **Delta Lake** storage format commit logs:

* **ISO 8601 Timestamp Queries**: Query lineage graphs, blast radius, root cause, and semantic vector embeddings as of any point in time (`as_of="2026-09-08T10:00:00Z"`).
* **Schema & Lineage Diffing**: Analyze added, removed, and modified data assets, columns, and lineage edges between any two historical timestamps ($T_1 \rightarrow T_2$).
* **Timeline Scrubbing Slider UI**: Interactive web visualizer UI allows dragging through commit logs to scrub back in time and view historical graph states visually.

---

## AI Agent & LLM Integration (Retriever Tools)

LineagIQ Control Plane includes pre-built **Agentic Retriever Tools** ([`control_plane/src/agent_tools.py`](file:///Users/timor/projects/dataworks/LineagIQ/control_plane/src/agent_tools.py)) that enable LLM agents (LangChain, AutoGen, LlamaIndex) to perform automated blast-radius impact analysis, historical time-travel diffing, and semantic data discovery.

### Python Code Example:

```python
from openai import OpenAI
from control_plane.src.agent_tools import (
    get_dataset_blast_radius,
    get_lineage_time_travel_diff,
    search_enterprise_data_catalog,
)

# 1. Retrieve Graph Context & Synthesized Prompt from LineagIQ Control Plane
blast_radius_prompt = get_dataset_blast_radius(
    tenant_id="demo_tenant",
    dataset_id="model.jaffle_shop.stg_customers",
    data_path="/tmp/tenants/demo_tenant"
)

# 2. Retrieve Historical Schema Drift Diff Prompt (Time Travel)
time_travel_prompt = get_lineage_time_travel_diff(
    tenant_id="demo_tenant",
    node_id="model.jaffle_shop.stg_customers",
    timestamp_t1="2026-09-08T08:00:00Z",
    timestamp_t2="2026-09-08T10:00:00Z",
    data_path="/tmp/tenants/demo_tenant"
)

# 3. Dispatch Context to LLM Provider
client = OpenAI(api_key="your-openai-api-key")
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are LineagIQ AI Agent, an expert enterprise data architect."},
        {"role": "user", "content": time_travel_prompt}
    ]
)

print(completion.choices[0].message.content)
```

---

## End-to-End Demo Setup & Execution

### 1. Installation & Environment Setup
Clone the repository and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

### 2. Run the Collection Agent (Generate Tenant Graph Metadata)
Execute the Collection Agent CLI to ingest sample metadata fixtures (dbt models, SQL schemas, query logs, OpenLineage events) and output compressed Parquet & Delta Lake table datasets to `/tmp/tenants/demo_tenant`:

```bash
python3 -m collection_agent.src.cli --output-dir /tmp/tenants/demo_tenant
```

**Output:**
```text
Collection Agent Pipeline Completed Successfully:
Nodes: 16, Edges: 9
Artifacts Path: /tmp/tenants/demo_tenant
```

---

### 3. Launch the Control Plane FastAPI Web Server
Start the serverless query runtime on port `8000`:

```bash
python3 -m uvicorn control_plane.src.main:app --reload --port 8000
```

---

### 4. Test GraphRAG Endpoints Manually

#### A. Health Check
```bash
curl http://localhost:8000/healthz
```

#### B. Fetch Tenant Timeline History (Delta Lake Commit Logs)
```bash
curl http://localhost:8000/api/v1/tenants/demo_tenant/timeline
```

#### C. Historical Time Travel Graph Query
Fetch knowledge graph as of a historical timestamp:
```bash
curl "http://localhost:8000/api/v1/tenants/demo_tenant/graph?as_of=2026-09-08T08:00:00Z"
```

#### D. Downstream Blast Radius Query
Compute downstream operational blast radius for target dataset `model.jaffle_shop.stg_customers`:

```bash
curl -X POST http://localhost:8000/api/v1/tenants/demo_tenant/blast-radius \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "model.jaffle_shop.stg_customers",
    "max_depth": 5,
    "data_path": "/tmp/tenants/demo_tenant"
  }'
```

#### E. Historical Schema Drift & Time Travel Diff Query
Compute schema additions, removals, and lineage edge changes between $T_1$ and $T_2$:

```bash
curl -X POST http://localhost:8000/api/v1/tenants/demo_tenant/time-travel/diff \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "model.jaffle_shop.stg_customers",
    "timestamp_t1": "2026-09-08T08:00:00Z",
    "timestamp_t2": "2026-09-08T10:00:00Z",
    "data_path": "/tmp/tenants/demo_tenant"
  }'
```

#### F. Semantic Asset Discovery Query
Find data assets related to `"customer"`:

```bash
curl -X POST http://localhost:8000/api/v1/tenants/demo_tenant/discovery \
  -H "Content-Type: application/json" \
  -d '{
    "query": "customer",
    "top_k": 5,
    "data_path": "/tmp/tenants/demo_tenant"
  }'
```

---

### 5. Interactive Web Visualizer & API Documentation
Open your web browser to test interactive endpoints:
* **Interactive Visualizer & Timeline Scrubbing UI**: [http://localhost:8000/visualizer](http://localhost:8000/visualizer)
* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 6. Run Full Test Suite
Run all Python unit/integration tests and JavaScript client unit tests:

```bash
# Run Python backend test suite (48 tests)
python3 -m pytest collection_agent/tests/ control_plane/tests/

# Run JavaScript visualizer client test suite (4 tests)
node --test control_plane/tests/script.test.js
```
