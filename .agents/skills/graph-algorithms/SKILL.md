---
name: graph-traversal-algorithms
description: >-
  Advanced algorithmic techniques for graph traversal, multi-hop blast radius propagation,
  cycle detection, topological sorting, pathfinding, and attribute-based subgraph filtering.
---

# Graph Traversal & Filtering Algorithms Skill

Algorithmic reference for high-performance lineage graph evaluation, reachability analysis, and graph analytics.

## Core Algorithmic Workflows

1. **Multi-Hop Traversal (Upstream & Downstream Blast Radius)**:
   - **Breadth-First Search (BFS)**: Preferred for level-by-level blast radius exploration and shortest-hop distance calculation.
   - **Depth-First Search (DFS)**: Preferred for path discovery, dependency chain tracking, and deep tree verification.
   - **Depth Bounding**: Always enforce a safe `max_depth` parameter (default 5, bounded 1–10) to prevent unbounded graph expansion on large-scale enterprise topologies.

2. **Cycle Detection & Topological Sorting**:
   - Detect circular dependencies in lineage flows using **Tarjan's strongly connected components (SCC)** or **Kahn's topological sort algorithm** (in-degree tracking).
   - Flag cycles immediately in transformation pipelines to alert data engineers before materialization.

3. **Graph Filtering & Pruning**:
   - **Semantic Filtering**: Filter nodes and edges by attributes (e.g. environment `prod`/`dev`, source system, layer `bronze`/`silver`/`gold`).
   - **Edge Type Exclusion**: Exclude structural edges (e.g. `BELONGS_TO`) during lineage traversals unless specifically expanding column-level lineage.
   - **Subgraph Scoping**: Given a target node, isolate the weakly connected component or reachable cone (upstream + downstream) before executing expensive diffing or aggregation.

4. **Temporal Graph Diffing**:
   - Compare snapshot $G_{T1} = (V_1, E_1)$ and $G_{T2} = (V_2, E_2)$ to compute:
     - Added nodes: $V_2 \setminus V_1$
     - Removed nodes: $V_1 \setminus V_2$
     - Modified nodes: $\{v \in V_1 \cap V_2 \mid \text{properties}_1(v) \neq \text{properties}_2(v)\}$
     - Added edges: $E_2 \setminus E_1$
     - Removed edges: $E_1 \setminus E_2$
   - Ensure diffs can be evaluated either globally or localized to a specific scoped node's neighborhood.
