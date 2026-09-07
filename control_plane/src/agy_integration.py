import sys
import argparse
from typing import Optional
from control_plane.src.agent_tools import LineagIQGraphRAGClient


def run_agy_blast_radius(
    tenant_id: str,
    node_id: str,
    data_path: Optional[str] = None,
    max_depth: int = 5,
) -> str:
    """
    Executes GraphRAG Blast Radius traversal and returns the AGY Agent contextual prompt.
    """
    client = LineagIQGraphRAGClient()
    return client.get_blast_radius_prompt(
        tenant_id=tenant_id,
        node_id=node_id,
        max_depth=max_depth,
        data_path=data_path,
    )


def run_agy_discovery(
    tenant_id: str,
    query: str,
    data_path: Optional[str] = None,
    top_k: int = 5,
) -> str:
    """
    Executes GraphRAG Semantic Discovery and returns the AGY Agent contextual prompt.
    """
    client = LineagIQGraphRAGClient()
    return client.get_discovery_prompt(
        tenant_id=tenant_id,
        query=query,
        top_k=top_k,
        data_path=data_path,
    )


def main():
    parser = argparse.ArgumentParser(description="AGY Agent LineagIQ Control Plane Integrator")
    parser.add_argument("--tenant", type=str, default="demo_tenant", help="Tenant ID")
    parser.add_argument("--data-path", type=str, default="/tmp/tenants/demo_tenant", help="Path to tenant artifacts")
    parser.add_argument("--blast-radius", type=str, help="Target Node ID for Blast Radius analysis")
    parser.add_argument("--discovery", type=str, help="Semantic search query for Asset Discovery")
    parser.add_argument("--max-depth", type=int, default=5, help="Max traversal depth")

    args = parser.parse_args()

    if args.blast_radius:
        prompt = run_agy_blast_radius(
            tenant_id=args.tenant,
            node_id=args.blast_radius,
            data_path=args.data_path,
            max_depth=args.max_depth,
        )
        print(prompt)
    elif args.discovery:
        prompt = run_agy_discovery(
            tenant_id=args.tenant,
            query=args.discovery,
            data_path=args.data_path,
        )
        print(prompt)
    else:
        print("Usage: python3 -m control_plane.src.agy_integration --blast-radius NODE_ID or --discovery QUERY")


if __name__ == "__main__":
    main()
