import os
import json
import argparse
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

from collection_agent.src.extractors.dbt import DbtExtractor
from collection_agent.src.extractors.sql import SqlCatalogExtractor
from collection_agent.src.extractors.query_logs import QueryLogExtractor
from collection_agent.src.extractors.openlineage import OpenLineageExtractor
from collection_agent.src.transform.graph_builder import GraphBuilder
from collection_agent.src.embedder.local_embedder import LocalEmbedder
from collection_agent.src.storage.writer import ArtifactWriter
from collection_agent.src.sync.s3_sync import S3Uploader

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def load_demo_fixtures(builder: GraphBuilder) -> None:
    """Loads default sample fixtures into GraphBuilder for demonstration/testing."""
    dbt_manifest_file = FIXTURES_DIR / "dbt_manifest.json"
    dbt_catalog_file = FIXTURES_DIR / "dbt_catalog.json"
    sql_schema_file = FIXTURES_DIR / "sql_information_schema.json"
    query_logs_file = FIXTURES_DIR / "query_logs.json"
    openlineage_file = FIXTURES_DIR / "openlineage_event.json"

    if dbt_manifest_file.exists():
        with open(dbt_manifest_file) as f:
            manifest_data = json.load(f)
        catalog_data = {}
        if dbt_catalog_file.exists():
            with open(dbt_catalog_file) as f:
                catalog_data = json.load(f)
        
        dbt_ext = DbtExtractor()
        manifest_nodes = dbt_ext.parse_manifest(manifest_data)
        catalog_nodes = dbt_ext.parse_catalog(catalog_data)
        lineage_edges = dbt_ext.extract_lineage(manifest_data)
        builder.ingesting_dbt(manifest_nodes, catalog_nodes, lineage_edges)

    if sql_schema_file.exists():
        with open(sql_schema_file) as f:
            sql_data = json.load(f)
        sql_ext = SqlCatalogExtractor()
        tables = sql_ext.parse_tables(sql_data.get("tables", []))
        columns = sql_ext.parse_columns(sql_data.get("columns", []))
        fks = sql_ext.parse_foreign_keys(sql_data.get("foreign_keys", []))
        builder.ingesting_sql_catalog(tables, columns, fks)

    if query_logs_file.exists():
        with open(query_logs_file) as f:
            ql_data = json.load(f)
        ql_ext = QueryLogExtractor()
        access_edges = ql_ext.parse_user_access(ql_data)
        join_edges = ql_ext.parse_join_predicates(ql_data)
        builder.ingesting_query_logs(access_edges, join_edges)

    if openlineage_file.exists():
        with open(openlineage_file) as f:
            ol_data = json.load(f)
        ol_ext = OpenLineageExtractor()
        parsed_event = ol_ext.parse_event(ol_data)
        builder.ingesting_openlineage(parsed_event)


def run_pipeline(
    output_dir: Optional[str] = None,
    sync_s3: bool = False,
    tenant_id: Optional[str] = None,
    bucket: Optional[str] = None,
    dbt_manifest: Optional[str] = None,
    dbt_catalog: Optional[str] = None,
    sql_schema: Optional[str] = None,
    query_logs: Optional[str] = None,
    load_demo: bool = True,
) -> Dict[str, Any]:
    """
    Executes end-to-end Collection Agent pipeline:
    1. Metadata Extraction & Graph Normalization
    2. Local Vector Embedding
    3. Parquet & LanceDB Artifact Serialization
    4. Optional Multi-part S3 Lake Sync
    """
    target_dir = output_dir or tempfile.mkdtemp(prefix="lineagiq_collection_")

    builder = GraphBuilder()

    has_custom_inputs = any([dbt_manifest, sql_schema, query_logs])

    if has_custom_inputs:
        if dbt_manifest:
            with open(dbt_manifest) as f:
                manifest_data = json.load(f)
            catalog_data = {}
            if dbt_catalog:
                with open(dbt_catalog) as f:
                    catalog_data = json.load(f)
            dbt_ext = DbtExtractor()
            manifest_nodes = dbt_ext.parse_manifest(manifest_data)
            catalog_nodes = dbt_ext.parse_catalog(catalog_data)
            lineage_edges = dbt_ext.extract_lineage(manifest_data)
            builder.ingesting_dbt(manifest_nodes, catalog_nodes, lineage_edges)

        if sql_schema:
            with open(sql_schema) as f:
                sql_data = json.load(f)
            sql_ext = SqlCatalogExtractor()
            tables = sql_ext.parse_tables(sql_data.get("tables", []))
            columns = sql_ext.parse_columns(sql_data.get("columns", []))
            fks = sql_ext.parse_foreign_keys(sql_data.get("foreign_keys", []))
            builder.ingesting_sql_catalog(tables, columns, fks)

        if query_logs:
            with open(query_logs) as f:
                ql_data = json.load(f)
            ql_ext = QueryLogExtractor()
            access_edges = ql_ext.parse_user_access(ql_data)
            join_edges = ql_ext.parse_join_predicates(ql_data)
            builder.ingesting_query_logs(access_edges, join_edges)
    elif load_demo:
        load_demo_fixtures(builder)

    # Vectorize and package graph
    embedder = LocalEmbedder()
    payload = builder.to_payload()
    payload = embedder.embed_payload(payload)

    # Write Parquet and LanceDB artifacts
    writer = ArtifactWriter()
    artifacts = writer.write_all(payload, target_dir)

    # S3 Lake Sync
    synced_keys = []
    if sync_s3:
        uploader = S3Uploader(bucket=bucket, tenant_id=tenant_id)
        synced_keys = uploader.sync_directory(target_dir)

    return {
        "output_dir": target_dir,
        "nodes_count": len(payload.nodes),
        "edges_count": len(payload.edges),
        "artifacts": artifacts,
        "synced_keys": synced_keys,
    }


def main():
    parser = argparse.ArgumentParser(description="LineagIQ Collection Agent CLI")
    parser.add_argument("--output-dir", type=str, help="Output directory for artifacts")
    parser.add_argument("--sync", action="store_true", help="Sync output artifacts to S3")
    parser.add_argument("--tenant-id", type=str, help="LineagIQ Tenant ID")
    parser.add_argument("--bucket", type=str, help="S3 Bucket Name")
    parser.add_argument("--dbt-manifest", type=str, help="Path to dbt manifest.json")
    parser.add_argument("--dbt-catalog", type=str, help="Path to dbt catalog.json")
    parser.add_argument("--sql-schema", type=str, help="Path to SQL INFORMATION_SCHEMA JSON")
    parser.add_argument("--query-logs", type=str, help="Path to query logs JSON")
    parser.add_argument("--no-demo", action="store_true", help="Do not load sample demo data if no inputs provided")

    args = parser.parse_args()
    results = run_pipeline(
        output_dir=args.output_dir,
        sync_s3=args.sync,
        tenant_id=args.tenant_id,
        bucket=args.bucket,
        dbt_manifest=args.dbt_manifest,
        dbt_catalog=args.dbt_catalog,
        sql_schema=args.sql_schema,
        query_logs=args.query_logs,
        load_demo=not args.no_demo,
    )
    print("Collection Agent Pipeline Completed Successfully:")
    print(f"Nodes: {results['nodes_count']}, Edges: {results['edges_count']}")
    print(f"Artifacts Path: {results['output_dir']}")


if __name__ == "__main__":
    main()
