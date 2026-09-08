# LineagIQ Collection Agent (Stateless Ingestion Agent)

The **Collection Agent** is an ephemeral, privacy-first metadata collection service designed to execute directly within customer environments (VPCs, Kubernetes clusters, CI/CD runners, or AWS Batch).

It extracts structural metadata, query logs, and static pipeline manifests, embeds semantic descriptions using a local ONNX model, formats graph nodes, lineage edges, and vector indices into **Delta Lake** dataset tables and Snappy-compressed Parquet artifacts, and streams the processed outputs directly to the multi-tenant LineagIQ Control Plane S3 bucket.

---

## Key Design Principles

* **Ephemeral Execution**: Runs as a stateless container or cron job with zero persistent database lock requirements or persistent volume storage.
* **Privacy-First & Secure**: Only extracts structural schema metadata, query logs, and pipeline definitions. Raw enterprise table cell data never leaves the customer environment.
* **In-Process Embeddings**: Uses quantized local embedding models (`bge-small-en-v1.5` INT8 via ONNX runtime) to generate vector embeddings in memory without third-party API dependencies.
* **Delta Lake & Columnar Output**: Produces standardized Delta Lake datasets (`write_deltalake`) with `_delta_log/` transaction histories alongside `.parquet` files for graph nodes, edges, and dense vector embeddings.
* **Direct Lake Sync**: Directly uploads prepared Delta Lake and Parquet datasets to tenant prefixes in S3 via presigned URLs or IAM roles.

---

## Directory Structure

```text
collection_agent/
├── README.md                 # Component overview and operational guide
├── ARCHITECTURE.md           # Technical architectural specification
├── requirements.txt          # Python dependencies
├── src/                      # Source code
│   ├── cli.py                # Command-line entrypoint & pipeline runner
│   ├── extractors/           # dbt, SQL INFORMATION_SCHEMA, Query Logs, OpenLineage
│   └── sync/                 # Multi-part S3 uploader
└── tests/                    # Pytest test suite and sample fixtures
    ├── fixtures/             # Mock dbt manifests, SQL schemas, query logs, OpenLineage events
    ├── test_cli.py           # Pipeline runner tests
    ├── test_dbt_extractor.py # dbt extractor tests
    ├── test_openlineage_extractor.py
    ├── test_query_logs_extractor.py
    ├── test_sql_extractor.py
    └── test_sync.py          # S3 sync tests
```

---

## Quick Start: Running the Collection Agent Demo

### 1. Install Dependencies
```bash
pip install -r collection_agent/requirements.txt
```

### 2. Run the Ingestion Pipeline
To run the agent and generate tenant graph artifacts (`graph/nodes/`, `graph/edges/`, `vectors/`) for a demo tenant:

```bash
python3 -m collection_agent.src.cli --output-dir /tmp/tenants/demo_tenant
```

**Output:**
```text
Collection Agent Pipeline Completed Successfully:
Nodes: 16, Edges: 9
Artifacts Path: /tmp/tenants/demo_tenant
```

### 3. Custom Metadata Extraction Options
```bash
# Ingest dbt compilation artifacts
python3 -m collection_agent.src.cli --dbt-manifest path/to/manifest.json --dbt-catalog path/to/catalog.json --output-dir /tmp/tenants/my_tenant

# Ingest SQL INFORMATION_SCHEMA export
python3 -m collection_agent.src.cli --sql-schema path/to/schema.json --output-dir /tmp/tenants/my_tenant

# Sync directly to S3 bucket
python3 -m collection_agent.src.cli --output-dir /tmp/tenants/my_tenant --sync --tenant-id tenant_123 --bucket control-plane-lake
```

### 4. Run Unit Tests
```bash
python3 -m pytest collection_agent/tests/
```

---

## Architectural Deep Dive

For full details on data flows, module breakdown, security boundaries, and storage formats, see [ARCHITECTURE.md](file:///Users/timor/projects/dataworks/LineagIQ/collection_agent/ARCHITECTURE.md).
