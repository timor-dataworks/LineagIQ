# LineagIQ: Enterprise Semantic Knowledge Graph Platform

LineagIQ models an enterprise data landscape into a contextual knowledge graph. It decouples the core semantic and graph engine from tenant-specific operational data using a three-tier architecture:

1. **LineagIQ Core (`core`)**: Centralized ontology domain models (`Node`, `Edge`, `GraphPayload`), local quantized INT8 vector embedder with singleton caching, Delta Lake PyArrow schemas, storage table/path constants, and `ArtifactWriter`.
2. **Stateless Ingestion Agent (`collection_agent`)**: An ephemeral edge metadata collector that extracts (dbt, SQL catalog, query logs, OpenLineage) and syncs metadata inside the customer environment.
3. **Serverless Control Plane (`control_plane`)**: A high-performance query engine powered by pure NumPy (Compressed Sparse Row/Column indexing) and Delta Lake exposing FastAPI endpoints, interactive web visualization with time travel timeline scrubbing, and the dynamic LineagIQ AI Assistant (supporting OpenAI, Gemini, and local Ollama). Unified by a single `DATA_PATH` environment variable.

---

## 🌐 Live Production Endpoints

| Resource | URL | Description |
| :--- | :--- | :--- |
| **Marketing & Platform Website** | [https://lineagiq.com](https://lineagiq.com) & [https://www.lineagiq.com](https://www.lineagiq.com) | Product architecture, TCO comparison & feature showcase |
| **LineagIQ Control Plane UI** | [https://plane.lineagiq.com/](https://plane.lineagiq.com/) | Live interactive lineage graph, timeline scrubbing & AI Assistant |
| **Interactive OpenAPI Docs** | [https://plane.lineagiq.com/docs](https://plane.lineagiq.com/docs) | Live Swagger UI API explorer |
| **ReDoc API Specifications** | [https://plane.lineagiq.com/redoc](https://plane.lineagiq.com/redoc) | Detailed endpoint schema & payload documentation |

---

## Repository Architecture

```text
LineagIQ/
├── core/                       # Shared Domain Models, Vector Embedder, Schemas & Writer
│   ├── models.py               # Ontology Pydantic Models (Node, Edge, GraphPayload)
│   ├── embedder.py             # Local In-Memory & Quantized Vector Embedder
│   ├── constants.py            # Storage table names, paths, and helpers
│   ├── schemas.py              # Static PyArrow Schemas (NODE_SCHEMA, EDGE_SCHEMA)
│   ├── writer.py               # Delta Lake & Parquet ArtifactWriter
│   ├── graph_builder.py        # Graph normalization and DAG alias resolver
│   ├── utils.py                # ISO 8601 timestamps & search term extractors
│   └── tests/                  # Core package unit tests
│
├── collection_agent/           # Ephemeral Ingestion Agent
│   ├── README.md               # Collection Agent documentation
│   ├── ARCHITECTURE.md         # Architectural specification
│   ├── requirements.txt        # Agent dependencies
│   ├── src/                    # Extractors, S3 Sync, CLI
│   └── tests/                  # Pytest test suite & mock fixtures
│
├── control_plane/              # Serverless Query Plane & GraphRAG API
│   ├── README.md               # Control Plane documentation
│   ├── requirements.txt        # Control plane dependencies
│   ├── src/                    # Pure NumPy Query Engine, Prompt Synthesizer, Agent Tools, FastAPI App, Web Visualizer
│   │   ├── query_engine/       # Base interfaces, NumPy Graph Store (CSR/CSC), NumPy Vector Store (BLAS), Engine façade
│   │   ├── static/             # Web Visualizer UI (index.html, style.css, script.js)
│   │   ├── agent_tools.py      # Retriever tools for LLM frameworks
│   │   ├── prompt_synthesizer.py # GraphRAG prompt generators
│   │   └── main.py             # FastAPI endpoints & route handlers
│   └── tests/                  # Pytest unit & integration test suite (test_time_travel.py, test_api.py, etc.)
│
├── website/                    # Static Product & Architecture Showcase Website
│   ├── index.html              # Landing page, feature demos, quick start
│   ├── style.css               # Design system & responsive styles
│   ├── script.js               # Visualizer demo interactions, mobile nav drawer
│   └── assets/                 # High-resolution UI screenshots & diagrams
│
├── deploy/                     # Server Deployment & Automation (Ubuntu / Docker / Caddy)
│   ├── README.md               # Comprehensive operations & DNS configuration guide
│   ├── deploy.sh               # One-click remote deployment script
│   ├── setup_server.sh         # Server initialization (Docker, Swap, UFW Firewall)
│   ├── docker-compose.yml      # Caddy, Control Plane, and Collection Agent services
│   ├── Caddyfile               # Automatic HTTPS reverse proxy & static asset delivery
│   ├── seed_demo_data.sh       # Multi-version Delta Lake graph seeder
│   └── run_collection.sh       # CLI runner for metadata ingestion
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

## Pure NumPy & Delta Lake High-Performance Query Engine

LineagIQ replaces bulky graph database servers with an ultra-lightweight, in-memory **Compressed Sparse Row (CSR)** and **Compressed Sparse Column (CSC)** engine compiled directly from Delta Lake columnar tables:

* **Microsecond Graph Traversal**: Evaluates multi-hop downstream blast radius and upstream root cause reachability in **microseconds (< 0.05 ms / 20 µs)** through direct contiguous memory slices (`targets[indptr[u]:indptr[u+1]]`).
* **18.6x Memory Reduction**: Requires only **~1.5 MB RAM** to index 50,000 nodes and 150,000 edges in-memory (compared to ~28.5 MB in DuckDB and 16 GB in legacy graph databases like Neo4j).
* **BLAS Vector Dot-Product**: Executes fast normalized dense vector similarity search via contiguous 2D float32 matrices and `np.argpartition` top-$k$ candidate selection.
* **Instant Snapshot Materialization**: Arrow zero-copy memory ingestion directly from Delta Lake commit logs (`_delta_log/`), enabling instant point-in-time time travel cache invalidation.

| Benchmark Metric (50,000 Nodes • 150,000 Edges) | NumPy on Delta Lake | Tabular SQL / DuckDB | Legacy Graph DB (Neo4j) |
| :--- | :---: | :---: | :---: |
| **In-Memory Cache RAM Footprint** | **~1.5 MB** | ~28.5 MB | ~16 GB |
| **5-Hop Blast Radius Traversal** | **~0.02 ms** (20 µs) | ~6.5 ms | ~85 ms |
| **10-Hop Deep Graph Traversal** | **~0.04 ms** (40 µs) | ~14.2 ms | ~190 ms |
| **Upstream Root Cause (5 Hops)** | **~0.02 ms** (20 µs) | ~7.1 ms | ~92 ms |
| **Cold Snapshot Build from Delta Lake** | **~145 ms** | ~480 ms | ~45,000 ms |

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
# (Uses DATA_PATH environment variable for storage location)
blast_radius_prompt = get_dataset_blast_radius(dataset_id="model.jaffle_shop.stg_customers", max_depth=5)

# 2. Retrieve Historical Schema Drift Diff Prompt (Time Travel)
time_travel_prompt = get_lineage_time_travel_diff(
    node_id="model.jaffle_shop.stg_customers", timestamp_t1="2026-09-08T08:00:00Z", timestamp_t2="2026-09-08T10:00:00Z"
)

# 3. Dispatch Context to LLM Provider
client = OpenAI(api_key="your-openai-api-key")
completion = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are LineagIQ AI Agent, an expert enterprise data architect."},
        {"role": "user", "content": time_travel_prompt},
    ],
)

print(completion.choices[0].message.content)
```

### Interactive Web AI Assistant (Dynamic Right Docking & Ollama Support)

The web visualizer UI ([https://plane.lineagiq.com/](https://plane.lineagiq.com/) or local `http://localhost:8000/`) includes an interactive **LineagIQ AI Assistant** drawer:
* **Dynamic Right Docking**: Automatically docks to the right screen edge (`right: 16px`). When a node is selected in the graph, the drawer dynamically shifts left to accommodate the node inspector sidebar without overlapping, and glides back smoothly when the inspector closes.
* **Local LLM Support (Ollama)**: Seamlessly connect to local Ollama instances (`ollama serve` on `http://localhost:11434/v1`) with zero API key required, as well as cloud providers (OpenAI `gpt-4o`, Google Gemini `gemini-3.6-flash`).
* **One-Click Diff Analysis**: In the Time Travel Diff View, click **"🤖 Send to AI Assistant"** to automatically pipe schema drift diffs into the assistant for automated impact explanations.

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

### 2. Run the Collection Agent (Generate Graph Metadata)
Set the unified `DATA_PATH` environment variable and run the Collection Agent CLI to ingest sample metadata fixtures (dbt models, SQL schemas, query logs, OpenLineage events) and output compressed Parquet & Delta Lake table datasets:

```bash
export DATA_PATH=/tmp/lineagiq_data
python3 -m collection_agent.src.cli
```

Or generate a realistic 3-version historical lineage evolution dataset for time travel:
```bash
python3 -m collection_agent.src.cli --multiversion-demo
```

**Output:**
```text
Collection Agent Pipeline Completed Successfully:
Nodes: 37, Edges: 46
Artifacts Path: /tmp/lineagiq_data
```

**Inject custom production data sources directly into the collector:**
```bash
# Ingest dbt manifests & catalogs
python3 -m collection_agent.src.cli --dbt-manifest path/to/manifest.json --dbt-catalog path/to/catalog.json

# Ingest SQL DDL / INFORMATION_SCHEMA
python3 -m collection_agent.src.cli --sql-schema path/to/schema.json

# Ingest warehouse query logs
python3 -m collection_agent.src.cli --query-logs path/to/query_logs.json

# Ingest OpenLineage run events (Airflow, Spark, Flink, Dagster)
python3 -m collection_agent.src.cli --openlineage path/to/openlineage_events.json
```

---

### 3. Launch the Control Plane FastAPI Web Server
Start the serverless query runtime on port `8000` (reads from `DATA_PATH`):

```bash
export DATA_PATH=/tmp/lineagiq_data
python3 -m uvicorn control_plane.src.main:app --reload --port 8000
```

---

### 4. Test GraphRAG Endpoints Manually

#### A. Health & Config Check
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/api/v1/config
```

#### B. Fetch Timeline History (Delta Lake Commit Logs)
```bash
curl http://localhost:8000/api/v1/timeline
```

#### C. Historical Time Travel Graph Query
Fetch knowledge graph as of a historical timestamp:
```bash
curl "http://localhost:8000/api/v1/graph?as_of=2026-09-08T08:00:00Z"
```

#### D. Downstream Blast Radius Query
Compute downstream operational blast radius for target dataset `model.jaffle_shop.stg_customers`:

```bash
curl -X POST http://localhost:8000/api/v1/blast-radius \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "model.jaffle_shop.stg_customers",
    "max_depth": 5
  }'
```

#### E. Historical Schema Drift & Time Travel Diff Query
Compute schema additions, removals, and lineage edge changes between $T_1$ and $T_2$:

```bash
curl -X POST http://localhost:8000/api/v1/time-travel/diff \
  -H "Content-Type: application/json" \
  -d '{
    "node_id": "model.jaffle_shop.stg_customers",
    "timestamp_t1": "2026-09-08T08:00:00Z",
    "timestamp_t2": "2026-09-08T10:00:00Z"
  }'
```

#### F. Semantic Asset Discovery Query
Find data assets related to `"customer"`:

```bash
curl -X POST http://localhost:8000/api/v1/discovery \
  -H "Content-Type: application/json" \
  -d '{
    "query": "customer",
    "top_k": 5
  }'
```

---

### 5. Interactive Web Visualizer & API Documentation
Open your web browser to test interactive endpoints:

* **Production Visualizer & Timeline Scrubbing**: [https://plane.lineagiq.com/](https://plane.lineagiq.com/)
* **Production OpenAPI Swagger UI**: [https://plane.lineagiq.com/docs](https://plane.lineagiq.com/docs)
* **Production ReDoc Documentation**: [https://plane.lineagiq.com/redoc](https://plane.lineagiq.com/redoc)
* **Local Development UI**: [http://localhost:8000/](http://localhost:8000/) (Swagger: [http://localhost:8000/docs](http://localhost:8000/docs))

---

### 6. Run Full Test Suite
Run all Python unit/integration tests and JavaScript client unit tests:

```bash
# Run Python backend test suite (48 tests)
python3 -m pytest collection_agent/tests/ control_plane/tests/

# Run JavaScript visualizer client test suite (4 tests)
node --test control_plane/tests/script.test.js
```

---

### 7. Docker Packaging & Deployment

LineagIQ provides production-ready Docker images for both the **Collection Agent** and the **Control Plane**.

#### A. Build with Docker Compose
```bash
# Start Control Plane web service on port 8000
docker compose up -d control_plane

# Ingest metadata via ephemeral Collection Agent
docker compose run --rm collection_agent
```

#### B. Build & Run Standalone Containers

##### 1. Collection Agent (Ephemeral Edge Ingestion)
```bash
# Build standalone image
docker build -f Dockerfile.collection_agent -t lineagiq-collection-agent:latest .

# Run metadata extraction using default DATA_PATH (/data)
docker run --rm \
  -v $(pwd)/data:/data \
  lineagiq-collection-agent:latest

# Or override DATA_PATH via environment variable
docker run --rm \
  -e DATA_PATH=/data/custom \
  -v $(pwd)/data:/data \
  lineagiq-collection-agent:latest
```

##### 2. Control Plane (Serverless Query Engine & Visualizer Web UI)
```bash
# Build standalone image
docker build -f Dockerfile.control_plane -t lineagiq-control-plane:latest .

# Run web service on port 8000 with mounted data lake storage (uses DATA_PATH=/data)
docker run -d --name lineagiq-control-plane \
  -p 8000:8000 \
  -v $(pwd)/data:/data \
  lineagiq-control-plane:latest

# Or override DATA_PATH to point to another path
docker run -d --name lineagiq-control-plane \
  -p 8000:8000 \
  -e DATA_PATH=/data/custom \
  -v $(pwd)/data:/data \
  lineagiq-control-plane:latest
```

##### 3. Unified Multi-Stage Target Builds
You can also build using the root multi-stage `Dockerfile`:
```bash
# Build collection agent target
docker build --target collection-agent -t lineagiq-collection-agent .

# Build control plane target (default)
docker build --target control-plane -t lineagiq-control-plane .
```

#### C. Generate 3-Version Time-Travel Demo Dataset in Docker
You can run the multi-version generator inside Docker to create realistic historical schema evolution (V0: E-commerce, V1: GDPR/Multi-currency, V2: Real-time Streaming & AI Churn):

##### Option 1: Via Collection Agent Container (uses DATA_PATH)
```bash
docker run --rm \
  -v $(pwd)/data:/data \
  lineagiq-collection-agent:latest \
  --multiversion-demo
```

##### Option 2: Via Docker Compose
```bash
docker compose run --rm demo_generator
```

##### Option 3: Direct Python Module Invocation
```bash
docker run --rm \
  -v $(pwd)/data:/data \
  --entrypoint python \
  lineagiq-collection-agent:latest \
  -m scripts.generate_multiversion_demo
```
