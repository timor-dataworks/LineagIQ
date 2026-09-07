# Stateless Ingestion Agent (Collection Agent): Architectural Overview

## 1. Executive Summary

The **Collection Agent** is the edge metadata collection engine for LineagIQ. Designed to operate strictly within the customer's security boundary (VPC, local runner, or private subnet), the agent extracts metadata, converts it into canonical ontology structures, generates quantized vector embeddings locally, packages data into Parquet and LanceDB indices, and syncs the resulting artifacts to the LineagIQ Control Plane.

```text
 Customer VPC Boundary
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ Collection Agent (Container Job / K8s CronJob)                                         │
 │                                                                                        │
 │ ┌───────────────────┐    ┌───────────────────┐    ┌──────────────────────────────────┐ │
 │ │  1. Extractors    │───>│  2. Graph Builder │───>│ 3. In-Memory Embedder & Writer   │ │
 │ │  • dbt Artifacts  │    │  • Node Schema    │    │  • bge-small INT8 ONNX            │ │
 │ │  • SQL Catalogs   │    │  • Lineage Edges  │    │  • Parquet (Nodes/Edges)          │ │
 │ │  • Query Logs     │    │  • Business Terms │    │  • LanceDB Index                 │ │
 │ └───────────────────┘    └───────────────────┘    └──────────────────────────────────┘ │
 └───────────────────────────────────────────┬────────────────────────────────────────────┘
                                             │ Multipart Presigned S3 Sync
                                             ▼
 Multi-Tenant S3 Storage Plane
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │ s3://control-plane-lake/tenants/{tenant_id}/                                           │
 │    ├── graph/nodes/data.parquet                                                        │
 │    ├── graph/edges/data.parquet                                                        │
 │    └── vectors/metadata.lance/                                                         │
 └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Architectural Components

### 2.1 Extraction Subsystem (`extractors/`)
The extraction layer uses source-specific plugins targeting operational data assets:

1. **dbt Extractor (`extractors/dbt.py`)**:
   - Parses compiled `manifest.json` and `catalog.json` artifacts.
   - Extracts `Table`, `Column`, and `Pipeline` nodes along with DAG relationships (`DERIVED_FROM`, `PRODUCED_BY`).
   - Captures column descriptions, tests, and data owner metadata.

2. **SQL Catalog Extractor (`extractors/sql.py`)**:
   - Executes read-only queries against `INFORMATION_SCHEMA` across Snowflake, BigQuery, Databricks, PostgreSQL, etc.
   - Extracts tables, views, columns, physical data types, nullability, primary keys, and foreign keys.

3. **Query Log Extractor (`extractors/query_logs.py`)**:
   - Scrapes `QUERY_HISTORY` / `ACCESS_HISTORY` audit logs.
   - Infers column-level join relationships (`JOINS_WITH`) and dataset usage patterns (`CONSUMED_BY`).

4. **OpenLineage Event Receiver (`extractors/openlineage.py`)**:
   - Ingests standard OpenLineage JSON events from Airflow, Spark, or dbt runtime adapters.

---

### 2.2 Graph Normalization Engine (`transform/`)
Translates extracted payloads into the normalized LineagIQ Ontology:

* **Node Types**:
  - `Dataset`: Tables, views, and raw file stores.
  - `Column`: Individual schema fields.
  - `Pipeline`: Transformation jobs and dbt models.
  - `User` / `Team`: Owners and query consumers.
  - `BusinessTerm`: Conceptual domain definitions.

* **Edge Types**:
  - `(:Pipeline)-[:PRODUCED_BY]->(:Dataset)`
  - `(:Pipeline)-[:CONSUMED_BY]->(:Dataset)`
  - `(:Dataset)-[:DERIVED_FROM]->(:Dataset)`
  - `(:Column)-[:JOINS_WITH]->(:Column)`
  - `(:Dataset|Column)-[:GOVERNED_BY]->(:BusinessTerm)`

---

### 2.3 In-Process Vectorization (`embedder/`)
To eliminate external API costs and keep metadata private:
- Uses a local quantized embedding model (`bge-small-en-v1.5` in INT8 ONNX format).
- Embedded fields: Dataset descriptions, column names, business terms, and query context strings.
- Runs entirely in-process using ONNX Runtime with zero external HTTP calls.

---

### 2.4 Storage & Index Serialization (`storage/`)
Outputs are stored in ephemeral `/tmp` scratch space before sync:
- **Graph Nodes & Edges**: Written to optimized, compressed Apache Parquet files (`data.parquet`).
- **Vector Indexing**: Written directly to LanceDB table formats (`metadata.lance/`).

---

### 2.5 Multi-Part Direct Sync (`sync/`)
- Obtains presigned S3 upload URLs from the LineagIQ Control Plane API using tenant authentication tokens.
- Streams Parquet and LanceDB chunks directly to `s3://control-plane-lake/tenants/{tenant_id}/`.
- Cleanly purges all temporary files from local storage upon completion.

---

## 3. Data Processing Pipeline Execution Flow

```text
 ┌───────────────┐
 │ 1. Init       │ Load CLI arguments, tenant tokens, and extractor options.
 └───────┬───────┘
         ▼
 ┌───────────────┐
 │ 2. Extract    │ Run active extractors concurrently against configured sources.
 └───────┬───────┘
         ▼
 ┌───────────────┐
 │ 3. Transform  │ Map raw metadata to canonical Node & Edge graph records.
 └───────┬───────┘
         ▼
 ┌───────────────┐
 │ 4. Vectorize  │ Generate 384-dim embeddings via local ONNX runtime.
 └───────┬───────┘
         ▼
 ┌───────────────┐
 │ 5. Package    │ Write node & edge Parquet tables + LanceDB vector tables.
 └───────┬───────┘
         ▼
 ┌───────────────┐
 │ 6. Sync       │ Multipart upload to tenant S3 prefix & cleanup scratch files.
 └───────────────┘
```

---

## 4. Security & Privacy Guarantees

* **Zero Content Leakage**: Only schema definitions, structural metadata, query metrics, and lineage relationships are collected. Raw data records are never accessed or stored.
* **Local Processing**: Model inference occurs locally within the container without streaming metadata to external LLMs during ingestion.
* **Minimal Privileges**: Requires strictly read-only access to system metadata views (`INFORMATION_SCHEMA`, `QUERY_HISTORY`).
* **Ephemeral Lifecycle**: Self-terminates after execution, leaving no persistent footprint or background listeners.
