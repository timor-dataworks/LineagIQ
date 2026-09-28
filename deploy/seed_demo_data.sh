#!/usr/bin/env bash
# ==============================================================================
# LineagIQ Demo Data Seeder
# Executes multi-version lineage generator inside the running control-plane container
# Writes Delta Lake tables (nodes, edges, vectors) into /opt/lineagiq/data/tenants/default/
# ==============================================================================
set -euo pipefail

TARGET_DIR="${1:-/opt/lineagiq}"
cd "$TARGET_DIR"

echo "🌱 Seeding 3-version demo lineage knowledge graph into Delta Lake..."

docker compose exec -T \
  -e DATA_PATH=/data/tenants/default/ \
  control-plane python scripts/generate_multiversion_demo.py

echo "✅ Seeding complete! Control plane now has historical lineage data for time-travel queries."
