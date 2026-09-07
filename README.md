# LineagIQ: Enterprise Semantic Knowledge Graph Platform

LineagIQ models an enterprise data landscape into a contextual knowledge graph. It decouples the core semantic and graph engine from tenant-specific operational data using a two-tier architecture:

1. **Stateless Ingestion Agent (`collection_agent`)**: An ephemeral edge metadata collector that extracts, embeds (via local ONNX INT8), formats (Parquet/LanceDB), and syncs metadata inside the customer environment.
2. **Serverless S3 Control Plane (`control_plane`)**: A multi-tenant query engine powered by DuckDB and LanceDB exposing FastAPI endpoints for GraphRAG prompt synthesis (downstream blast-radius & semantic discovery).

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
│   ├── src/                    # DuckDB Query Engine, Prompt Synthesizer, FastAPI App
│   └── tests/                  # Pytest integration tests
│
├── documentation/              # High-level developer & architectural specs
│   └── project overview.md
└── requirements.txt            # Root dependencies
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
Execute the Collection Agent CLI to ingest sample metadata fixtures (dbt models, SQL schemas, query logs, OpenLineage events) and output compressed Parquet files and LanceDB vector indices to `/tmp/tenants/demo_tenant`:

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

#### B. Downstream Blast Radius & Prompt Synthesis Query
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

#### C. Semantic Asset Discovery Query
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

### 5. Interactive API Documentation
Open your web browser to test interactive endpoints:
* **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
* **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

### 6. Run Full Test Suite
Run all 28 unit and integration tests across `collection_agent` and `control_plane`:

```bash
python3 -m pytest collection_agent/tests/ control_plane/tests/
```
