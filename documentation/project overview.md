# Developer & Architectural Specification: Enterprise Semantic Knowledge Graph (LineagIQ)

## System Overview
The LineagIQ platform models an enterprise data landscape into a contextual knowledge graph. It decouples the core semantic and graph engine from tenant-specific operational data. The architecture operates through a two-tier model: an ephemeral **Stateless Ingestion Agent** that extracts, embeds, and formats metadata inside the customer environment, and a **Serverless S3 Control Plane** that hosts multi-tenant storage and executes GraphRAG queries.

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

The agent executes as an ephemeral job within customer VPCs (Kubernetes CronJob, AWS Batch, or CI/CD runner), eliminating the need for persistent volumes or long-running database file locks.

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
   │     • Columnar Parquet generation (Nodes & Lineage Edges)              │
   │     • Local LanceDB Table Indexing                                     │
   │                                                                        │
   │  3. Direct Lake Sync:                                                  │
   │     • Multipart upload directly to tenant prefix in S3                 │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │ Direct S3 Sync / Presigned Upload
                                       ▼
   [Managed S3 Storage & Query Plane]
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Amazon S3 Multi-Tenant Lake                                            │
   │  s3://control-plane-lake/tenants/{tenant_id}/                           │
   │     ├── graph/nodes/data.parquet                                       │
   │     ├── graph/edges/data.parquet                                       │
   │     └── vectors/metadata.lance/                                        │
   └───────────────────────────────────┬────────────────────────────────────┘
                                       │ HTTPFS / Direct S3 Range Reads
                                       ▼
   ┌────────────────────────────────────────────────────────────────────────┐
   │ Query Runtime & GraphRAG API (FastAPI / Serverless Container)          │
   │  • DuckDB scans Parquet via HTTPFS for lineage traversals              │
   │  • S3-backed LanceDB handles vector similarity lookups                 │
   │  • Prompt synthesis for downstream blast-radius & discovery            │
   └────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Architectural Highlights

* **Privacy-First Ingestion:** Raw database content remains inside customer boundaries. Only schema metadata, structure, and embedded representations are synced to the storage plane.
* **Serverless Analytics Engine:** Uses DuckDB over HTTPFS for ultra-fast SQL lineage traversals and graph analytics directly against Parquet files stored in S3.
* **Hybrid Vector & Graph Search (GraphRAG):** Combines direct similarity search via LanceDB with graph traversal via DuckDB to answer complex queries regarding data blast-radius, governance compliance, and root-cause analysis.
