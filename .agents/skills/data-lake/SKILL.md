---
name: data-lake-expert
description: >-
  Specialized expertise in Lakehouse storage architecture, Delta Lake transaction protocols,
  Parquet columnar optimization, schema evolution, time-travel snapshots, and cloud object storage.
---

# Data Lake Expert Skill

Comprehensive guidance for managing, querying, and optimizing lakehouse tables and columnar storage formats in LineagIQ.

## Core Storage Paradigms

1. **Delta Lake Protocol & ACID Logs**:
   - Understand the `_delta_log/` transaction journal (`.json` commit logs and `.checkpoint.parquet` state files).
   - Leverage `DeltaTable` API (`deltalake-python`) for reading commits, log history, and point-in-time versions.
   - Support zero-copy time travel: query table states as of historical versions or ISO 8601 timestamps without data duplication.

2. **Parquet Columnar Optimization**:
   - Enforce Snappy or ZSTD compression with optimized row group sizes (~64MB–128MB for analytical scans).
   - Leverage dictionary encoding and statistics (min/max bounds) for predicate pushdown.
   - Maintain uniform schemas across partition layouts to enable fast file pruning.

3. **Cloud Object Store Integration (S3 / GCS / Azure)**:
   - Configure S3 credentials securely (IAM roles, STS temporary credentials, AWS environment variables).
   - Cache credentials with safe TTL margins (e.g. 45-minute refresh on 1-hour IAM tokens).
   - Implement exponential backoff retry policies for cloud object store rate limits (HTTP 503 / 429).

4. **Schema Evolution & Idempotency**:
   - Handle schema drift gracefully: added columns, nullable changes, and metadata attribute evolution.
   - Ensure atomic, idempotent table writes (upsert / append / overwrite) preventing orphan data files.
