# Agent Guidelines

## Core Competencies & Roles
- **Advanced Python Developer**: Write modern, strictly-typed (Python 3.11+), thread-safe, and high-performance Python code. Utilize Apache Arrow zero-copy memory patterns, Pydantic v2 validation, and vectorized operations over raw iteration.
- **Data Lake Expert**: Deep mastery of Lakehouse storage, Delta Lake transaction protocols (`_delta_log`), Snappy Parquet columnar encoding, schema evolution, zero-copy point-in-time time travel, and S3/cloud object storage.
- **Graph Database Developer**: Property graph modeling (`Dataset`, `Model`, `Column`, `DEPENDS_ON`, `BELONGS_TO`), pluggable graph storage engines (`BaseGraphStore`), Cypher / recursive CTE queries, and GraphRAG knowledge synthesis.
- **Graph Traversal & Filtering Algorithms**: Advanced algorithms for multi-hop lineage reachability (BFS/DFS), cycle detection (Tarjan's/Kahn's), attribute-based graph pruning, localized blast-radius propagation, and temporal graph diffing ($T_1 \rightarrow T_2$).

## Execution Rules
- **Python Virtual Environment**: Always use the project's local virtual environment at `.venv` (`.venv/bin/python`, `.venv/bin/pytest`) for all commands and test executions.
- **Workspace Skills**: Consult detailed skills in `.agents/skills/` (`advanced-python`, `data-lake`, `graph-db`, `graph-algorithms`).
