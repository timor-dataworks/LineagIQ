# LineagIQ Server Deployment Guide

Production-ready, single-server deployment configuration and automation for **LineagIQ** on an Ubuntu Linux server (`62.238.48.203`).

---

## 🏛️ Architecture Overview

```text
[ Internet / Browser / API Clients ]
                 │
                 ├── :80, :443 (HTTP/HTTPS)
                 ▼
┌────────────────────────────────────────────────────────┐
│  Caddy 2 Reverse Proxy (Docker)                        │
│  - Automatic HTTPS (Let's Encrypt / ZeroSSL)           │
│  - lineagiq.com, www.lineagiq.com -> /var/www/html     │
│  - plane.lineagiq.com             -> control-plane:8000│
│  - Direct IP fallback (:80)       -> /var/www/html     │
└───────────────┬────────────────────────┬───────────────┘
                │                        │
       Static Assets                     │ Proxy :8000
                ▼                        ▼
┌────────────────────────┐      ┌────────────────────────┐
│ Static Website         │      │ Control Plane Engine   │
│ - HTML5, CSS3, JS      │      │ - FastAPI Web App      │
│ - Full Product Showcase│      │ - Pure NumPy CSR/CSC   │
│ - Time Travel Demos    │      │ - GraphRAG AI Assistant│
└────────────────────────┘      └───────────┬────────────┘
                                            │ Reads
                                            ▼
                                ┌────────────────────────┐
                                │ Shared Delta Lake Data │
                                │ /opt/lineagiq/data/    │
                                └───────────▲────────────┘
                                            │ Writes
                                ┌───────────┴────────────┐
                                │ Collection Agent       │
                                │ - dbt Manifest/Catalog │
                                │ - SQL Information Schema│
                                │ - OpenLineage & Logs   │
                                └────────────────────────┘
```

---

## 🚀 Quick Deployment (One Command)

From your local machine, run:

```bash
./deploy/deploy.sh
```

Or target an alternate user/host:

```bash
./deploy/deploy.sh root@62.238.48.203
```

### What `deploy.sh` automates:
1. **Connectivity Check**: Verifies SSH communication to the target host.
2. **Server Bootstrap**: Automatically provisions Docker Engine, Docker Compose plugin, 2GB swap space, and UFW firewall rules (`22`, `80`, `443`, `8000`) if not yet installed.
3. **Asset Sync**: Rsyncs `/website/` and deployment configurations to `/opt/lineagiq/`.
4. **Service Launch**: Pulls public GHCR container images and starts Caddy + Control Plane services in the background.
5. **Data Seeding**: Automatically initializes the Delta Lake storage with a realistic 3-version historical lineage graph if empty.
6. **Health Verification**: Performs live HTTP smoke tests against internal endpoints.

---

## 🌐 Endpoints

### 1. Direct Server IP Access (Available immediately without DNS changes)
* **Marketing Website**: `http://62.238.48.203/`
* **Control Plane Visualizer UI**: `http://62.238.48.203:8000/`
* **OpenAPI Documentation**: `http://62.238.48.203:8000/docs`

### 2. Domain Access (Active after pointing DNS A Records to `62.238.48.203`)
* **Marketing Website**: `https://lineagiq.com` & `https://www.lineagiq.com`
* **Control Plane UI**: `https://plane.lineagiq.com`
* **Interactive API Docs**: `https://plane.lineagiq.com/docs`

> **Note on TLS/SSL**: Caddy handles certificate generation and auto-renewal automatically through Let's Encrypt as soon as the DNS records resolve to `62.238.48.203`.

---

## 🧭 DNS Configuration

In your DNS provider (e.g., Cloudflare, Namecheap, Route 53, etc.), configure:

| Type | Name | Value | TTL |
| :--- | :--- | :--- | :--- |
| **A** | `@` (lineagiq.com) | `62.238.48.203` | Automatic / 300 |
| **A** | `www` | `62.238.48.203` | Automatic / 300 |
| **A** | `plane` | `62.238.48.203` | Automatic / 300 |

---

## 🛠️ Server Management (via `ssh root@62.238.48.203`)

### Check Service Status
```bash
cd /opt/lineagiq
docker compose ps
```

### View Live Logs
```bash
cd /opt/lineagiq
docker compose logs -f
# or specific service:
docker compose logs -f control-plane
docker compose logs -f caddy
```

### Ingest Lineage Metadata
Run the metadata Collection Agent against sample fixtures:
```bash
cd /opt/lineagiq
./scripts/run_collection.sh
# or generate full multi-version history:
./scripts/run_collection.sh --multiversion-demo
```

Or ingest your actual data platform artifacts (place files in `/opt/lineagiq/sources/`):
```bash
cd /opt/lineagiq
./scripts/run_collection.sh \
  --dbt-manifest /sources/manifest.json \
  --dbt-catalog /sources/catalog.json
```

### Re-seed Demo Dataset
To reset or re-populate the 3-version historical dataset:
```bash
cd /opt/lineagiq
./scripts/seed_demo_data.sh
```

### Configure AI Assistant (OpenAI / Gemini)
Edit `/opt/lineagiq/.env`:
```bash
nano /opt/lineagiq/.env
```
Set your keys:
```env
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```
Restart the control plane:
```bash
cd /opt/lineagiq && docker compose up -d control-plane
```
