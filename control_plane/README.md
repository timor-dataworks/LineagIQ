# LineagIQ Control Plane & GraphRAG API

The **Control Plane** provides serverless graph traversal and semantic vector search over tenant datasets stored in Parquet and LanceDB format.

It features:
* **DuckDB Graph Engine**: Executes recursive CTE queries directly against Parquet files (`graph/nodes/data.parquet` and `graph/edges/data.parquet`) to calculate downstream blast radius and upstream lineage.
* **Semantic Discovery Engine**: Searches metadata vector indices (`vectors/metadata.lance`) to locate related data assets.
* **GraphRAG Prompt Synthesizer**: Formats contextual graph traversals and search results into structured LLM prompts for downstream AI analysis.
* **FastAPI Web Service**: Exposes REST endpoints for multi-tenant blast radius calculation and semantic discovery.

---

## Directory Structure

```text
control_plane/
├── README.md
├── requirements.txt
├── src/
│   ├── query_engine.py         # DuckDB Parquet scanner & graph traverser
│   ├── prompt_synthesizer.py   # LLM prompt synthesis for blast radius & discovery
│   └── main.py                 # FastAPI application
└── tests/
    ├── test_query_engine.py    # Unit tests for query engine & prompts
    └── test_api.py             # Integration tests for FastAPI endpoints
```
