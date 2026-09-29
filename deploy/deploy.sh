#!/usr/bin/env bash
# ==============================================================================
# LineagIQ Remote Deployment Automation Script
# Deploys Static Website, Control Plane, and Collection Agent to Ubuntu Server
# Usage:
#   ./deploy/deploy.sh [user@host]
# Default target:
#   root@62.238.48.203
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_SERVER="${1:-root@62.238.48.203}"
REMOTE_DIR="/opt/lineagiq"

echo "============================================================"
echo "🚀 LineagIQ Production Deployment"
echo "   Target Server: ${TARGET_SERVER}"
echo "   Remote Path:   ${REMOTE_DIR}"
echo "============================================================"

# 1. Verify SSH Connectivity
echo "📡 Verifying SSH connection to ${TARGET_SERVER}..."
if ! ssh -o BatchMode=yes -o ConnectTimeout=8 "${TARGET_SERVER}" "echo 'SSH connected successfully.'" 2>/dev/null; then
  echo "⚠️  Strict SSH connection failed. Attempting with accept-new host key policy..."
  ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "${TARGET_SERVER}" "echo 'SSH connection verified.'"
fi

# 2. Check if Docker & Host Environment are provisioned
echo "🔍 Checking remote Docker runtime..."
HAS_DOCKER=$(ssh "${TARGET_SERVER}" "command -v docker &>/dev/null && echo 'yes' || echo 'no'")

if [ "$HAS_DOCKER" != "yes" ]; then
  echo "⚡ Docker not detected on remote host. Running bootstrap setup..."
  ssh "${TARGET_SERVER}" "bash -s" < "${SCRIPT_DIR}/setup_server.sh"
else
  echo "✅ Remote Docker runtime ready."
  # Ensure base directories exist
  ssh "${TARGET_SERVER}" "mkdir -p ${REMOTE_DIR}/{website,caddy,scripts,logs,sources,data/tenants/default}"
fi

# 3. Synchronize Application Files
echo "📦 Synchronizing application files to ${TARGET_SERVER}:${REMOTE_DIR}..."

# Sync static website
rsync -avz --delete \
  "${REPO_ROOT}/website/" \
  "${TARGET_SERVER}:${REMOTE_DIR}/website/"

# Copy docker compose and Caddyfile
scp "${SCRIPT_DIR}/docker-compose.yml" "${TARGET_SERVER}:${REMOTE_DIR}/docker-compose.yml"
scp "${SCRIPT_DIR}/Caddyfile" "${TARGET_SERVER}:${REMOTE_DIR}/caddy/Caddyfile"

# Copy maintenance and helper scripts
scp "${SCRIPT_DIR}/seed_demo_data.sh" "${TARGET_SERVER}:${REMOTE_DIR}/scripts/seed_demo_data.sh"
scp "${SCRIPT_DIR}/run_collection.sh" "${TARGET_SERVER}:${REMOTE_DIR}/scripts/run_collection.sh"
ssh "${TARGET_SERVER}" "chmod +x ${REMOTE_DIR}/scripts/*.sh"

# Create .env from template if missing
ssh "${TARGET_SERVER}" "if [ ! -f ${REMOTE_DIR}/.env ]; then printf 'LINEAGIQ_VERSION=v0.1.0\nDATA_PATH=/data/tenants/default/\n' > ${REMOTE_DIR}/.env; fi"

# 4. Pull Latest Images & Launch Services
echo "🐳 Pulling latest container images and launching services..."
ssh "${TARGET_SERVER}" "cd ${REMOTE_DIR} && docker compose pull && docker compose up -d --remove-orphans"

# 5. Seed Demo Lineage Data if Empty
echo "🌱 Checking if tenant data lake requires initialization..."
HAS_DATA=$(ssh "${TARGET_SERVER}" "find ${REMOTE_DIR}/data/tenants/default -name '*.parquet' 2>/dev/null | wc -l")

if [ "$HAS_DATA" -eq 0 ]; then
  echo "📥 Data directory empty. Waiting 5s for control-plane container before seeding..."
  sleep 5
  ssh "${TARGET_SERVER}" "bash ${REMOTE_DIR}/scripts/seed_demo_data.sh ${REMOTE_DIR}"
else
  echo "✅ Found existing lineage Delta Lake parquet files ($HAS_DATA files)."
fi

# 6. Verify Service Health
echo "🩺 Verifying service health..."
sleep 4

ssh "${TARGET_SERVER}" "
  echo '--- Control Plane Health (Port 8000) ---'
  curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://127.0.0.1:8000/
  echo '--- Caddy Reverse Proxy & Website (Port 80) ---'
  curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://127.0.0.1/
"

# 7. Print Deployment Summary
HOST_IP=$(echo "${TARGET_SERVER}" | cut -d'@' -f2)

echo ""
echo "============================================================"
echo "🎉 Deployment Completed Successfully!"
echo "============================================================"
echo "🌐 Direct IP Endpoints (Available immediately):"
echo "   - Marketing Website:       http://${HOST_IP}/"
echo "   - Control Plane UI & API:  http://${HOST_IP}:8000/"
echo "   - OpenAPI Docs:            http://${HOST_IP}:8000/docs"
echo ""
echo "🔐 Domain Endpoints (Active once DNS A records point to ${HOST_IP}):"
echo "   - Marketing Website:       https://lineagiq.com & https://www.lineagiq.com"
echo "   - Control Plane UI:        https://plane.lineagiq.com"
echo "   - OpenAPI Docs:            https://plane.lineagiq.com/docs"
echo "   *(Caddy will automatically provision Let's Encrypt SSL/TLS upon DNS pointing)*"
echo ""
echo "🛠️ Server Management Commands (via ssh ${TARGET_SERVER}):"
echo "   - View running containers:  cd ${REMOTE_DIR} && docker compose ps"
echo "   - Tail logs:                cd ${REMOTE_DIR} && docker compose logs -f"
echo "   - Run metadata ingestion:   cd ${REMOTE_DIR} && ./scripts/run_collection.sh --demo-fixtures"
echo "   - Re-seed demo graph:       cd ${REMOTE_DIR} && ./scripts/seed_demo_data.sh"
echo "============================================================"
