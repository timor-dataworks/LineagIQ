from typing import Dict, Any, List, Optional


class PromptSynthesizer:
    """
    Prompt Synthesizer builds context-rich, structured prompts for downstream LLM
    reasoning regarding Blast Radius, Root Cause Analysis, and Data Discovery.
    """

    def synthesize_blast_radius_prompt(
        self,
        start_node: Optional[Dict[str, Any]],
        impacted_nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> str:
        """
        Synthesizes a structured GraphRAG Prompt for downstream blast-radius analysis.
        """
        target_name = start_node["name"] if start_node else "Target Asset"
        target_type = start_node["type"] if start_node else "Unknown"
        target_id = start_node["id"] if start_node else "Unknown"

        # Categorize impacted nodes by type
        by_type: Dict[str, List[str]] = {}
        for n in impacted_nodes:
            ntype = n["type"]
            by_type.setdefault(ntype, []).append(f"{n['name']} (ID: {n['id']})")

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
            "================================================================================",
        ])

        return "\n".join(prompt_lines)

    def synthesize_discovery_prompt(
        self,
        query_text: str,
        matched_nodes: List[Dict[str, Any]],
    ) -> str:
        """
        Synthesizes a structured GraphRAG Prompt for semantic asset discovery.
        """
        prompt_lines = [
            "================================================================================",
            "LINEAGIQ GRAPHRAG PROMPT: SEMANTIC DATA DISCOVERY & GOVERNANCE",
            "================================================================================",
            "",
            f"### USER DISCOVERY QUERY: \"{query_text}\"",
            "",
            f"### MATCHED GRAPH CONTEXT ({len(matched_nodes)} assets found):",
        ]

        for n in matched_nodes:
            prompt_lines.append(f"\n* Asset: {n['name']} [{n['type']}]")
            prompt_lines.append(f"  ID: {n['id']}")
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
            "================================================================================",
        ])

        return "\n".join(prompt_lines)

    def synthesize_root_cause_prompt(
        self,
        target_node: Optional[Dict[str, Any]],
        upstream_nodes: List[Dict[str, Any]],
        edges: List[Dict[str, Any]],
    ) -> str:
        """
        Synthesizes a structured GraphRAG Prompt for upstream root cause analysis.
        """
        target_name = target_node["name"] if target_node else "Target Asset"
        target_type = target_node["type"] if target_node else "Unknown"
        target_id = target_node["id"] if target_node else "Unknown"

        # Categorize upstream nodes by type
        by_type: Dict[str, List[str]] = {}
        for n in upstream_nodes:
            ntype = n["type"]
            by_type.setdefault(ntype, []).append(f"{n['name']} (ID: {n['id']})")

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
            "================================================================================",
        ])

        return "\n".join(prompt_lines)

