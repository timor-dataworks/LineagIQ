#!/usr/bin/env bash
# ==============================================================================
# LineagIQ Metadata Collection Agent Runner
# Ingests lineage metadata (dbt, SQL catalog, query logs, OpenLineage) into Delta Lake
# ==============================================================================
set -euo pipefail

cd /opt/lineagiq

if [ "$#" -eq 0 ]; then
  echo "🚀 Running default ingestion demo..."
  docker compose run --rm \
    -e DATA_PATH=/data/tenants/default/ \
    collection-agent
  echo "✅ Ingestion complete. Control Plane will automatically query new Delta Lake state."
  exit 0
fi

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
  echo "============================================================"
  echo "LineagIQ Collection Agent"
  echo "============================================================"
  echo "Usage: $0 [options]"
  echo ""
  echo "Options:"
  echo "  (no args)                                 Ingest built-in sample demo fixtures"
  echo "  --multiversion-demo                       Generate multi-version demo history"
  echo "  --dbt-manifest FILE --dbt-catalog FILE    Ingest dbt artifacts (place under /opt/lineagiq/sources/)"
  echo "  --sql-schema FILE                         Ingest SQL schema JSON"
  echo "  --query-logs FILE                         Ingest SQL query access logs"
  echo "  --openlineage FILE                        Ingest OpenLineage run events"
  echo "============================================================"
  exit 0
fi

echo "🚀 Executing Collection Agent container..."
docker compose run --rm \
  -e DATA_PATH=/data/tenants/default/ \
  collection-agent "$@"

echo "✅ Ingestion complete. Control Plane will automatically query new Delta Lake state."
