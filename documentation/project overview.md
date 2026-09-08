# Developer & Architectural Specification: Enterprise Semantic Knowledge Graph (LineagIQ)

## System Overview
The LineagIQ platform models an enterprise data landscape into a contextual knowledge graph. It decouples the core semantic and graph engine from tenant-specific operational data. The architecture operates through a two-tier model: an ephemeral **Stateless Ingestion Agent** that extracts, embeds, and formats metadata inside the customer environment, and a **Serverless S3 Control Plane** that hosts multi-tenant storage and executes GraphRAG queries, time travel historical analysis, and interactive DAG visualization.

---

## 1. Data Model & Ontology Specification

### Node Definitions
* **Dataset / Table:** Physical database objects representing relational structures.
* **Column:** Individual fields within a dataset, including data types and schema constraints.
* **Pipeline:** Data movement and transformation workloads (e.g., dbt models, Airflow tasks).
* **Dashboard / Report:** Analytical consumers displaying aggregated dimensions and metrics.
* **User / Team:** Human creators, maintainers, and operational owners.
* **BusinessTerm:** Normalized conceptual definitions (e.g., "Monthly Recurring Revenue", "Active User").

### Edge Definitions
* `(:Pipeline)-[:PRODUCED_BY]->(:Dataset)`
* `(:Pipeline)-[:CONSUMED_BY]->(:Dataset)`
* `(:Dataset)-[:OWNED_BY]->(:User|Team)`
* `(:Dataset)-[:DERIVED_FROM]->(:Dataset)`
* `(:Column)-[:JOINS_WITH]->(:Column)`
* `(:Dataset|Column)-[:DISPLAYED_IN]->(:Dashboard|Report)`
* `(:Dataset|Column)-[:GOVERNED_BY]->(:BusinessTerm)`

---

## 2. Ingestion Engine & Source Extractors

Ingestion prioritizes static artifacts, operational query logs, and standardized payloads to maximize asset coverage with minimal operational friction:

| Priority | Source Target | Extracted Graph Elements | Implementation Method |
| :--- | :--- | :--- | :--- |
| **P0** | **dbt Artifacts** (`manifest.json`, `catalog.json`) | Table, Column, Pipeline, `DERIVED_FROM`, `OWNED_BY` | Direct local file parsing; traverses compiled DAG nodes, column descriptions, and test coverage. |
| **P0** | **`INFORMATION_SCHEMA`** (Snowflake, BigQuery, Databricks) | Table, Column, physical data types, foreign keys | Read-only SQL queries targeting system catalog views and constraint tables. |
| **P1** | **Query Logs** (`QUERY_HISTORY`, `ACCESS_HISTORY`) | Column `JOINS_WITH` Column, Dataset `CONSUMED_BY` User | Read-only SQL scraping to identify dynamic joins and usage patterns. |
| **P1** | **OpenLineage Events** | Real-time Pipeline run statuses, inputs, outputs | Webhook receiver / batch parser accepting standard OpenLineage JSON events. |
| **P2** | **BI Repositories** (LookML, Tableau APIs) | Dashboard, Report, `DISPLAYED_IN` | API pulls or Git repository parsing mapping model fields to UI dashboards. |

---

## 3. End-to-End Architecture

The agent executes as an ephemeral job within customer VPCs (Kubernetes CronJob, AWS Batch, or CI/CD runner), eliminating the need for persistent volumes or long-running database file locks. Data is persisted in **Delta Lake** dataset directories supporting historical ACID commit logs (`_delta_log/`).

```text
   [Customer VPC / Local Developer Environment]
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Stateless Ingestion Agent (Container / CronJob)                        │
   │                                                                        │
   │  1. Extract Metadata:                                                  │
   │     • Static dbt Artifacts (manifest.json, catalog.json)               │
   │     • Read-Only SQL (INFORMATION_SCHEMA, QUERY_HISTORY)                 │
   │                                                                        │
   │  2. In-Process Transform & Vectorization (/tmp scratch):              │
   │     • Local Quantized Embeddings (bge-small INT8 via ONNX)             │
   │     • Delta Lake dataset generation via deltalake (Nodes & Lineage)    │
   │     • Parquet columnar data.parquet files + Dense Vector Tables        │
   │                                                                        │
   │  3. Direct Lake Sync:                                                  │
   │     • Multipart upload directly to tenant prefix in S3                 │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │ Direct S3 Sync / Presigned Upload
                                       ▼
   [Managed S3 Storage & Query Plane]
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Amazon S3 Multi-Tenant Delta Lake                                      │
   │  s3://control-plane-lake/tenants/{tenant_id}/                           │
   │     ├── graph/nodes/ (_delta_log/, part-*.parquet, data.parquet)       │
   │     ├── graph/edges/ (_delta_log/, part-*.parquet, data.parquet)       │
   │     └── vectors/     (_delta_log/, part-*.parquet, data.parquet)       │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │ Delta Log Version Resolution & PyArrow Scan
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Query Runtime & GraphRAG API (FastAPI / Serverless Container)          │
   │  • DuckDB registers Delta PyArrow snapshots for time travel (as_of)    │
   │  • Vector similarity search over historical embedding snapshots        │
   │  • Historical schema drift & lineage diff computation (T1 -> T2)       │
   │  • Timeline scrubbing slider UI overlay in web visualizer              │
   └────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Architectural Highlights

* **Privacy-First Ingestion:** Raw database content remains inside customer boundaries. Only schema metadata, structure, and embedded representations are synced to the storage plane.
* **Delta Lake ACID & Time Travel:** Graph nodes, lineage edges, and vector indices are committed as Delta Lake tables. Commit history in `_delta_log/` enables point-in-time historical queries across any ISO 8601 timestamp.
* **Serverless Analytics Engine:** Uses DuckDB to register PyArrow tables resolved from Delta Lake historical versions for ultra-fast SQL lineage traversals and graph analytics directly against S3 datasets.
* **Historical Schema Drift Analysis:** Computes detailed diff payloads (`get_schema_time_travel_diff`) identifying added/removed datasets, schema column modifications, and altered lineage edges between two point-in-time snapshots ($T_1 \rightarrow T_2$).
* **Timeline Scrubbing Slider UI:** The web DAG visualizer includes an interactive bottom overlay with a timeline slider, allowing users to scrub back through commit history and visualize lineage evolution over time.
* **Hybrid Vector & Graph Search (GraphRAG):** Combines dense vector similarity search with graph traversal via DuckDB to answer complex queries regarding data blast-radius, governance compliance, and root-cause analysis.
