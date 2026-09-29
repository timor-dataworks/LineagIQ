---
name: graph-db-developer
description: >-
  Graph database engineering standards for property graphs, lineage modeling, dependency networks,
  graph query translation (Cypher/SQL CTE), and GraphRAG context synthesis.
---

# Graph DB Developer Skill

Best practices for designing, querying, and managing semantic knowledge graphs and enterprise lineage networks.

## Core Graph Principles

1. **Property Graph Data Modeling**:
   - Model entities as canonical Nodes (`Dataset`, `Model`, `Source`, `Dashboard`, `Column`, `Metric`, `Job`).
   - Model relationships as directed Edges with explicit semantic types:
     - `DEPENDS_ON` / `DERIVED_FROM` for data lineage flow.
     - `BELONGS_TO` for hierarchical composition (Column -> Dataset).
     - `PRODUCES` / `CONSUMES` for compute-to-data mapping.
   - Maintain JSON-encoded key-value `properties` for extensible, schemaless node/edge metadata.

2. **Querying & Traversal Abstractions**:
   - Decouple storage backends using pluggable interfaces (`BaseGraphStore`).
   - Implement both recursive relational CTE traversals and native graph queries (Cypher / graph algorithms).
   - Ensure edge endpoints are resolved and synthesize placeholder nodes when referencing external or upstream systems.

3. **GraphRAG & Semantic Retrieval**:
   - Convert graph paths and blast radius subgraphs into rich, synthesized prompts for LLM agents.
   - Combine topological structure (upstream/downstream trees) with vector embeddings for hybrid retrieval.
   - Scope lineage queries to relevant subgraphs (e.g. connected components) to control LLM context token windows.
