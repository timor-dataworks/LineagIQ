# LineagIQ Control Plane & GraphRAG API

The **Control Plane** provides serverless graph traversal and semantic vector search over tenant datasets stored in Parquet and LanceDB format.

It features:
* **DuckDB Graph Engine**: Executes recursive CTE queries directly against Parquet files (`graph/nodes/data.parquet` and `graph/edges/data.parquet`) to calculate downstream blast radius and upstream lineage.
* **Semantic Discovery Engine**: Searches metadata vector indices (`vectors/metadata.lance`) to locate related data assets.
* **GraphRAG Prompt Synthesizer**: Formats contextual graph traversals and search results into structured LLM prompts for downstream AI analysis.
* **Agentic Retriever Tools**: Standalone LangChain / Agentic tools in `control_plane/src/agent_tools.py` for integration into LLM agent workflows.
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
│   ├── agent_tools.py          # Agentic Retriever Tools & LineagIQGraphRAGClient
│   └── main.py                 # FastAPI application
└── tests/
    ├── test_agent_tools.py     # Unit tests for Agentic Retriever Tools
    ├── test_query_engine.py    # Unit tests for query engine & prompts
    └── test_api.py             # Integration tests for FastAPI endpoints
```

---

## Agentic AI & Tool Integration (Approach 2)

LineagIQ Control Plane provides agent tools (`control_plane/src/agent_tools.py`) designed to be registered directly with LLM Agent frameworks like **LangChain**, **LlamaIndex**, **AutoGen**, or custom AI agent loops.

### 1. Registering Tools with LangChain / AI Agents

```python
from langchain.tools import tool
from control_plane.src.agent_tools import get_dataset_blast_radius, search_enterprise_data_catalog

@tool
def blast_radius_tool(tenant_id: str, dataset_id: str) -> str:
    """Calculates downstream operational blast radius for a data asset before schema modifications or code deployments."""
    return get_dataset_blast_radius(tenant_id=tenant_id, dataset_id=dataset_id, data_path="/tmp/tenants/demo_tenant")

@tool
def data_discovery_tool(tenant_id: str, search_query: str) -> str:
    """Searches enterprise datasets, columns, and pipelines for semantic discovery and schema details."""
    return search_enterprise_data_catalog(tenant_id=tenant_id, query=search_query, data_path="/tmp/tenants/demo_tenant")
```

### 2. End-to-End Agent Execution Flow with OpenAI / LLMs

```python
from openai import OpenAI
from control_plane.src.agent_tools import LineagIQGraphRAGClient

# 1. Initialize LineagIQ GraphRAG Client
client = LineagIQGraphRAGClient()

# 2. Retrieve Graph Context & Synthesized Prompt for a target dataset
synthesized_prompt = client.get_blast_radius_prompt(
    tenant_id="demo_tenant",
    node_id="model.jaffle_shop.stg_customers",
    data_path="/tmp/tenants/demo_tenant"
)

# 3. Pass Synthesized Prompt to LLM Provider
openai_client = OpenAI(api_key="your-openai-api-key")
response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You are LineagIQ AI Agent, an expert enterprise data architect."},
        {"role": "user", "content": synthesized_prompt}
    ],
    temperature=0.1
)

print("AI AGENT ANALYSIS & RECOMMENDATIONS:")
print(response.choices[0].message.content)
```
