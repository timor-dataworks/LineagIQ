from typing import Dict, Any, List, Optional


class PromptSynthesizer:
    """Prompt Synthesizer builds context-rich, structured prompts for downstream LLM reasoning.

    Generates formatted GraphRAG prompts tailored for Blast Radius Analysis,
    Upstream Root Cause Analysis, and Semantic Data Discovery.
    """

    def synthesize_blast_radius_prompt(
        self,
        start_node: Optional[Dict[str, Any]],
        impacted_nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> str:
        """Synthesizes a structured GraphRAG Prompt for downstream blast-radius analysis.

        Args:
            start_node: Target node dictionary (name, type, id) under assessment.
            impacted_nodes: List of downstream node dictionaries impacted by target.
            edges: List of directed lineage traversal edge dictionaries.

        Returns:
            Formatted text string prompt containing system headers, asset summary,
            traversal details, and AI task instructions.
        """
        target_name = start_node["name"] if start_node else "Target Asset"
        target_type = start_node["type"] if start_node else "Unknown"
        target_id = start_node["id"] if start_node else "Unknown"

        # Categorize impacted nodes by type
        by_type: Dict[str, List[str]] = {}
        for n in impacted_nodes:
            ntype = n.get("type", "Unknown")
            by_type.setdefault(ntype, []).append(f"{n.get('name', 'N/A')} (ID: {n.get('id', 'N/A')})")

        prompt_lines = [
            "================================================================================",
            "LINEAGIQ GRAPHRAG PROMPT: DOWNSTREAM BLAST RADIUS & IMPACT ANALYSIS",
            "================================================================================",
            "",
            "### TARGET ASSET UNDER ASSESSMENT:",
            f"* Name: {target_name}",
            f"* Type: {target_type}",
            f"* Node ID: {target_id}",
            "",
            "### DOWNSTREAM IMPACT SUMMARY:",
            f"Total Impacted Downstream Assets: {len(impacted_nodes)}",
        ]

        for ntype, items in by_type.items():
            prompt_lines.append(f"\n#### Impacted {ntype}s ({len(items)}):")
            for item in items:
                prompt_lines.append(f"  - {item}")

        prompt_lines.extend([
            "",
            "### DOWNSTREAM LINEAGE TRAVERSAL EDGES:",
        ])

        for e in edges:
            prompt_lines.append(f"  - {e['source_id']} --[{e['type']}]--> {e['target_id']} (depth={e.get('depth', 1)})")

        prompt_lines.extend([
            "",
            "================================================================================",
            "AI ASSISTANT TASK INSTRUCTIONS:",
            "1. Analyze the downstream operational blast radius if the target asset schema changes or fails.",
            "2. Identify high-risk downstream consumers (e.g. BI dashboards, pipelines, key business users).",
            "3. Recommend remediation steps and notify owners of impacted downstream components.",
            "4. FORMATTING RULE: Do NOT use LaTeX math formatting, dollar signs ($), or LaTeX commands (e.g. \\rightarrow, \\to). Always output clean plain text or Unicode symbols (e.g. use '→' for lineage transitions, '←', '⇒', bullet points, bold markdown).",
            "================================================================================",
        ])

        return "\n".join(prompt_lines)

    def synthesize_discovery_prompt(
        self,
        query_text: str,
        matched_nodes: List[Dict[str, Any]],
    ) -> str:
        """Synthesizes a structured GraphRAG Prompt for semantic asset discovery.

        Args:
            query_text: Original natural language discovery query from user.
            matched_nodes: List of asset node dictionaries retrieved from hybrid search.

        Returns:
            Formatted text string prompt detailing user query, matched graph assets,
            and task instructions for catalog exploration.
        """
        prompt_lines = [
            "================================================================================",
            "LINEAGIQ GRAPHRAG PROMPT: SEMANTIC DATA DISCOVERY & GOVERNANCE",
            "================================================================================",
            "",
            f'### USER DISCOVERY QUERY: "{query_text}"',
            "",
            f"### MATCHED GRAPH CONTEXT ({len(matched_nodes)} assets found):",
        ]

        for n in matched_nodes:
            prompt_lines.append(f"\n* Asset: {n.get('name', 'N/A')} [{n.get('type', 'Unknown')}]")
            prompt_lines.append(f"  ID: {n.get('id', 'N/A')}")
            if n.get("description"):
                prompt_lines.append(f"  Description: {n['description']}")
            if n.get("properties"):
                prompt_lines.append(f"  Properties: {n['properties']}")

        prompt_lines.extend([
            "",
            "================================================================================",
            "AI ASSISTANT TASK INSTRUCTIONS:",
            "1. Explain how the matched data assets address the user's discovery query.",
            "2. Provide schema guidance, join paths, and dataset ownership details.",
            "3. Note any data governance terms or usage constraints.",
            "4. FORMATTING RULE: Do NOT use LaTeX math formatting, dollar signs ($), or LaTeX commands (e.g. \\rightarrow, \\to). Always output clean plain text or Unicode symbols (e.g. use '→' for lineage transitions, '←', '⇒', bullet points, bold markdown).",
            "================================================================================",
        ])

        return "\n".join(prompt_lines)

    def synthesize_root_cause_prompt(
        self,
        target_node: Optional[Dict[str, Any]],
        upstream_nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> str:
        """Synthesizes a structured GraphRAG Prompt for upstream root cause analysis.

        Args:
            target_node: Target asset node dictionary (name, type, id) under assessment.
            upstream_nodes: List of upstream source/dependency node dictionaries.
            edges: List of directed upstream lineage edge dictionaries.

        Returns:
            Formatted text string prompt containing system headers, asset summary,
            upstream dependencies, traversal edges, and AI troubleshooting instructions.
        """
        target_name = target_node["name"] if target_node else "Target Asset"
        target_type = target_node["type"] if target_node else "Unknown"
        target_id = target_node["id"] if target_node else "Unknown"

        # Categorize upstream nodes by type
        by_type: Dict[str, List[str]] = {}
        for n in upstream_nodes:
            ntype = n.get("type", "Unknown")
            by_type.setdefault(ntype, []).append(f"{n.get('name', 'N/A')} (ID: {n.get('id', 'N/A')})")

        prompt_lines = [
            "================================================================================",
            "LINEAGIQ GRAPHRAG PROMPT: UPSTREAM ROOT CAUSE & ORIGIN ANALYSIS",
            "================================================================================",
            "",
            "### TARGET ASSET UNDER ASSESSMENT:",
            f"* Name: {target_name}",
            f"* Type: {target_type}",
            f"* Node ID: {target_id}",
            "",
            "### UPSTREAM ORIGIN & PIPELINE SUMMARY:",
            f"Total Upstream Assets & Dependencies: {len(upstream_nodes)}",
        ]

        for ntype, items in by_type.items():
            prompt_lines.append(f"\n#### Upstream {ntype}s ({len(items)}):")
            for item in items:
                prompt_lines.append(f"  - {item}")

        prompt_lines.extend([
            "",
            "### UPSTREAM LINEAGE TRAVERSAL EDGES:",
        ])

        for e in edges:
            prompt_lines.append(f"  - {e['source_id']} --[{e['type']}]--> {e['target_id']} (depth={e.get('depth', 1)})")

        prompt_lines.extend([
            "",
            "================================================================================",
            "AI ASSISTANT TASK INSTRUCTIONS:",
            "1. Trace the data lineage back to root ingestion sources and upstream transformation models.",
            "2. Identify potential failure points, schema breaking changes, or upstream pipeline latency causing issues in the target asset.",
            "3. Provide actionable troubleshooting steps to pinpoint the root cause upstream.",
            "4. FORMATTING RULE: Do NOT use LaTeX math formatting, dollar signs ($), or LaTeX commands (e.g. \\rightarrow, \\to). Always output clean plain text or Unicode symbols (e.g. use '→' for lineage transitions, '←', '⇒', bullet points, bold markdown).",
            "================================================================================",
        ])

        return "\n".join(prompt_lines)

    def synthesize_time_travel_diff_prompt(
        self,
        node_id: str,
        timestamp_t1: str,
        timestamp_t2: str,
        diff_result: Dict[str, Any],
    ) -> str:
        """Synthesizes a structured GraphRAG Prompt for historical schema drift & lineage diff analysis.

        Args:
            node_id: Target node ID under historical assessment.
            timestamp_t1: Baseline ISO 8601 timestamp string.
            timestamp_t2: Compare ISO 8601 timestamp string.
            diff_result: Dictionary containing added_nodes, removed_nodes, modified_nodes, edge_changes.

        Returns:
            Formatted text string prompt for LLM historical analysis.
        """
        prompt_lines = [
            "================================================================================",
            "LINEAGIQ GRAPHRAG PROMPT: TIME TRAVEL & HISTORICAL SCHEMA DRIFT ANALYSIS",
            "================================================================================",
            "",
            f"### TARGET ASSET: {node_id}",
            f"### BASELINE TIMESTAMP (T1): {timestamp_t1}",
            f"### COMPARE TIMESTAMP (T2):  {timestamp_t2}",
            "",
            "### HISTORICAL CHANGES SUMMARY:",
            f"* Added Assets / Columns: {diff_result.get('added_nodes_count', 0)}",
            f"* Removed Assets / Columns: {diff_result.get('removed_nodes_count', 0)}",
            f"* Modified Schema Attributes: {diff_result.get('modified_nodes_count', 0)}",
            f"* Added Lineage Edges: {len(diff_result.get('added_edges', []))}",
            f"* Removed Lineage Edges: {len(diff_result.get('removed_edges', []))}",
        ]

        if diff_result.get("added_nodes"):
            prompt_lines.append("\n#### Added Data Assets & Columns:")
            for n in diff_result["added_nodes"]:
                prompt_lines.append(f"  + {n['name']} [{n['type']}] (ID: {n['id']})")

        if diff_result.get("removed_nodes"):
            prompt_lines.append("\n#### Removed Data Assets & Columns:")
            for n in diff_result["removed_nodes"]:
                prompt_lines.append(f"  - {n['name']} [{n['type']}] (ID: {n['id']})")

        if diff_result.get("modified_nodes"):
            prompt_lines.append("\n#### Modified Data Assets / Schema Attributes:")
            for m in diff_result["modified_nodes"]:
                prompt_lines.append(f"  ~ {m['id']}")

        prompt_lines.extend([
            "",
            "================================================================================",
            "AI ASSISTANT TASK INSTRUCTIONS:",
            "1. Evaluate the impact of schema additions, deletions, and lineage shifts between T1 and T2.",
            "2. Identify breaking changes or removed dependencies causing downstream consumer failures.",
            "3. Provide actionable remediation guidance to restore lineage stability.",
            "4. FORMATTING RULE: Do NOT use LaTeX math formatting, dollar signs ($), or LaTeX commands (e.g. \\rightarrow, \\to). Always output clean plain text or Unicode symbols (e.g. use '→' for lineage transitions, '←', '⇒', bullet points, bold markdown).",
            "================================================================================",
        ])

        return "\n".join(prompt_lines)



