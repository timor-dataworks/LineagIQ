#!/usr/bin/env bash
# ==============================================================================
# LineagIQ Single-Server Bootstrap Script
# Target: Ubuntu 24.04 / 26.04 LTS (x86_64)
# Configures Docker Engine, Compose plugin, UFW Firewall, Swap, & Directories
# ==============================================================================
set -euo pipefail

echo "============================================================"
echo "🚀 LineagIQ Server Provisioning & Setup"
echo "============================================================"

# Ensure running as root
if [ "$(id -u)" -ne 0 ]; then
  echo "❌ This script must be run as root (or via sudo)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# 1. System Packages Update
echo "📦 Updating apt packages..."
apt-get update -y
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  gnupg \
  lsb-release \
  git \
  rsync \
  ufw \
  htop \
  jq

# 2. Configure 2GB Swap (for DuckDB memory headroom)
if [ "$(swapon --show | wc -l)" -le 1 ]; then
  echo "💾 Creating 2GB swapfile..."
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  if ! grep -q '/swapfile' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
  fi
  echo "✅ 2GB Swap active."
else
  echo "✅ Swap is already configured."
fi

# 3. Install Docker Engine & Compose Plugin (Official Docker Repo)
if ! command -v docker &>/dev/null; then
  echo "🐳 Installing Docker Engine & Docker Compose plugin..."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc

  UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "noble")
  # Fallback to noble if on newer preview/testing releases without docker repository yet
  if [ "$UBUNTU_CODENAME" = "resolute" ] || [ "$UBUNTU_CODENAME" = "plucky" ] || [ "$UBUNTU_CODENAME" = "questing" ]; then
    UBUNTU_CODENAME="noble"
  fi

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
    ${UBUNTU_CODENAME} stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  systemctl enable docker
  systemctl start docker
  echo "✅ Docker installed: $(docker --version)"
else
  echo "✅ Docker already installed: $(docker --version)"
fi

# 4. Configure UFW Firewall
echo "🛡️  Configuring UFW Firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH access"
ufw allow 80/tcp comment "HTTP web ingress"
ufw allow 443/tcp comment "HTTPS web ingress"
ufw allow 8000/tcp comment "Control Plane direct port"
ufw --force enable
echo "✅ Firewall active:"
ufw status verbose

# 5. Create LineagIQ Directory Structure
echo "📁 Setting up /opt/lineagiq directories..."
mkdir -p /opt/lineagiq/data/tenants/default
mkdir -p /opt/lineagiq/website
mkdir -p /opt/lineagiq/caddy/data
mkdir -p /opt/lineagiq/caddy/config
mkdir -p /opt/lineagiq/scripts
mkdir -p /opt/lineagiq/logs
mkdir -p /opt/lineagiq/sources

# Set permissions
chmod -R 755 /opt/lineagiq

echo "============================================================"
echo "🎉 Server setup completed successfully!"
echo "   Next: Run ./deploy/deploy.sh to push code & start services."
echo "============================================================"
