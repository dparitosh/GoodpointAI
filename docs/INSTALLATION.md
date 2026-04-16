# GraphTrace — Installation Guide

> **Single entry point:** `.\graphtrace.ps1` (PowerShell). There are no other startup scripts.

---

## 1. Directory Layout

```
GoodpointAI/
├── graphtrace.ps1              # Single entry point  (-Check | -Start)
├── scripts/
│   ├── diagnostics.py          # Preflight checks (called by graphtrace.ps1 -Check)
│   └── start.py                # Multiplexer — launches all services (called by graphtrace.ps1 -Start)
├── python_backend/             # FastAPI backend  (Python 3.11+)
│   ├── .env.example            # Template — copy to .env and edit
│   ├── requirements.txt        # Python dependencies
│   ├── main.py                 # FastAPI application
│   ├── core/                   # Config, DB session, auth, security middleware
│   ├── graph_api/              # API routers (data sources, migration, quality, etc.)
│   ├── models/                 # SQLAlchemy ORM models
│   ├── scripts/                # init_db_schema, seed scripts, reset script
│   └── services/               # Business logic services
├── e2etraceapp/                # React + Vite frontend (Node 18+)
│   ├── package.json
│   ├── vite.config.js          # Dev proxy → backend :8011
│   └── src/                    # React source
├── mcp_server/                 # MCP coordination server
│   ├── requirements.txt
│   └── main.py
├── agent_services/             # MCP-powered AI agents (8 agents)
│   ├── chat_coordinator/
│   ├── data_analyst/
│   ├── data_discovery/
│   ├── etl_orchestrator/
│   ├── quality_monitor/
│   ├── query_planner/
│   ├── task_decomposer/
│   └── visualization_agent/
└── docs/                       # Documentation (you are here)
```

---

## 2. Prerequisites

Install these **before** starting. All must be on your system `PATH`.

| Software | Minimum Version | Verify Command | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | 3.11+ | `python --version` | 3.12 recommended |
| **Node.js** | 18+ | `node --version` | 20 LTS recommended; includes npm |
| **PostgreSQL** | 14+ | `psql --version` | **Required** — the app does not start without it |
| **Neo4j** | 5+ | *(n/a)* | Optional — graph lineage features |
| **OpenSearch** | 2+ | *(n/a)* | Optional — vector/fulltext search |

---

## 3. Installation Steps (Windows)

### Step 1 — Clone the Repository

```powershell
git clone https://github.com/dparitosh/GoodpointAI.git
cd GoodpointAI
```

After cloning, your working directory is the **repo root** (`GoodpointAI/`). All paths below are relative to this root.

---

### Step 2 — Find Your PostgreSQL Port

Before anything else, confirm which port PostgreSQL is listening on:

```powershell
# Option A: Check via Windows service
netstat -ano | findstr LISTENING | findstr :5432
# If no output, try 5433:
netstat -ano | findstr LISTENING | findstr :5433

# Option B: Check via psql
psql -U postgres -h 127.0.0.1 -p 5432 -c "SELECT 1"
# If that fails, try -p 5433
```

Write down your port number — you will need it in Step 4.

- Standard PostgreSQL installations use **port 5432**.
- Some custom installations (e.g., EDB, pgAdmin bundles) use **port 5433**.
- The app works with either — just make sure your `.env` file matches.

---

### Step 3 — Create the `graphtrace` Database

Connect to your PostgreSQL instance and create the database:

```powershell
# Replace 5432 with YOUR actual port from Step 2
psql -U postgres -h 127.0.0.1 -p 5432
```

```sql
CREATE DATABASE graphtrace
  WITH OWNER = postgres
       ENCODING = 'UTF8'
       TEMPLATE = template0;

-- (Optional) Create a dedicated application user
CREATE USER graphtrace_app WITH PASSWORD 'your_chosen_password';
GRANT ALL PRIVILEGES ON DATABASE graphtrace TO graphtrace_app;

\q
```

> If the `graphtrace` database already exists, skip this step.

---

### Step 4 — Create and Edit `python_backend/.env`

```powershell
# From repo root
Copy-Item python_backend\.env.example python_backend\.env
```

Open `python_backend\.env` in a text editor and set **your actual** values:

```dotenv
# REQUIRED — replace with your real PostgreSQL password and port
DATABASE_URL=postgresql://postgres:YOUR_REAL_PASSWORD@127.0.0.1:5432/graphtrace

# REQUIRED — tells the backend to load this file
GRAPH_TRACE_LOAD_DOTENV=true

# Individual Postgres settings (DATABASE_URL takes precedence, but keep these in sync)
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_REAL_PASSWORD

# Optional — uncomment if you have Neo4j/OpenSearch
# NEO4J_URI=neo4j://127.0.0.1:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your_neo4j_password
# OPENSEARCH_URL=http://localhost:9200
```

**Checklist before continuing:**
- [ ] Replaced `YOUR_REAL_PASSWORD` with your actual PostgreSQL password
- [ ] Port in `DATABASE_URL` matches what you found in Step 2
- [ ] Port in `POSTGRES_PORT` matches `DATABASE_URL`
- [ ] No placeholder values like `yourpassword` or `your_postgres_password` remain

**Verify connectivity now:**
```powershell
# Replace port if yours is different
psql -U postgres -h 127.0.0.1 -p 5432 -d graphtrace -c "SELECT 1"
# Expected output: a single row with value 1
```

> **If this fails** — fix it before continuing. Common causes:
> - PostgreSQL not running: `Get-Service PostgreSQL*`
> - Wrong port: re-check Step 2
> - Wrong password: reset via `ALTER USER postgres WITH PASSWORD 'newpass';`

---

### Step 5 — Create Virtual Environment and Install Dependencies

```powershell
# From repo root (d:\...\GoodpointAI)
python -m venv .venv

# Activate the virtual environment
.\.venv\Scripts\Activate.ps1
# Your prompt should now show (.venv)

# Install backend + MCP server dependencies
pip install -r python_backend\requirements.txt
pip install -r mcp_server\requirements.txt

# Install frontend dependencies
cd e2etraceapp
npm install
cd ..
```

**Verify:**
```powershell
python --version          # 3.11+
npm --version             # 8+
pip list | Select-String "psycopg|uvicorn|fastapi"
# Should list: fastapi, uvicorn, psycopg
```

> **Every time** you open a new terminal, activate the venv first: `.\.venv\Scripts\Activate.ps1`

---

### Step 6 — Run Preflight Diagnostics

```powershell
# Venv must be active
.\graphtrace.ps1 -Check
```

**Expected output:**
```
====================================
   GraphTrace Health & Diagnostics
====================================
[OK] Python is installed.
[OK] Node.js is installed.
[OK] NPM is installed.

--- Checking Environment Configuration (d:\...\python_backend\.env) ---
[OK] DATABASE_URL is configured.
[OK] GRAPH_TRACE_CONFIG_ENCRYPTION_KEY is configured.
[INFO] DB URL (redacted): postgresql://postgres:***@127.0.0.1:5432/graphtrace
[OK] Postgres connectivity check passed.

====================================
Diagnostics Passed! You are ready to run.
```

**If you see `[FAIL]` or `[WARN]`:**

| Message | Fix |
| :--- | :--- |
| `Python is missing` | Add Python to Windows PATH, restart terminal |
| `Node.js is missing` | Install Node.js 18+, restart terminal |
| `DATABASE_URL is missing` | Edit `python_backend\.env` (Step 4) |
| `DATABASE_URL is using placeholder credentials` | Replace `yourpassword` in `.env` with real password |
| `Postgres connectivity check failed` | Check PostgreSQL is running and `.env` values are correct |

> **Do NOT proceed to Step 7 until diagnostics pass.**

---

### Step 7 — Start the Full Stack

```powershell
# Venv must be active
.\graphtrace.ps1 -Start
```

**What happens (in order):**
1. `scripts/diagnostics.py` runs preflight checks
2. `scripts/start.py` runs `python -m scripts.init_db_schema` (creates tables, seeds default config)
3. The multiplexer launches **all services in parallel**:
   - Frontend (Vite dev server on port 5173)
   - Backend (uvicorn on port 8011)
   - MCP Server (uvicorn on port 8012)
   - 8 AI agent services

**You should see output like:**
```
[System] Bootstrapping GraphTrace Database/Schema...
[System] Database OK! Schema and Settings seeded.
[System] Launching Multiplexer (11 microservices)...
[System] Stack Live! Press Ctrl+C to abort all services.

[Frontend] VITE v5.x.x ready in xxxms
[Backend]  Uvicorn running on http://0.0.0.0:8011
[MCP_Srv]  Uvicorn running on http://0.0.0.0:8012
[A:chat]   Agent started...
[A:data]   Agent started...
...
```

Wait 10–15 seconds for all services to initialize, then verify:

| Service | URL | Expected |
| :--- | :--- | :--- |
| **Frontend (UI)** | http://localhost:5173 | React dashboard loads |
| **Backend API** | http://localhost:8011/health | JSON: `{"health": "ok", ...}` |
| **Swagger Docs** | http://localhost:8011/docs | Interactive API documentation |
| **MCP Server** | http://localhost:8012/health | JSON: `{"health": "ok", ...}` |

**To stop all services:** Press `Ctrl+C` in the terminal running `graphtrace.ps1`.
---

## 4. Manual Installation (Component by Component)

Use this if you prefer to start each service individually instead of the multiplexer.

### 4a. Backend Only

```powershell
# From repo root, venv must be active
cd python_backend

# Initialize database schema + seed default configurations
# This creates all PostgreSQL tables and seeds:
#   - Admin configs (LLM providers, embedding models, connections, feature flags)
#   - Pipeline configs (templates, file patterns, search/index configs)
#   - Encrypted config keys (system_configuration, neo4j, opensearch, cors, workflow_defaults)
python -m scripts.init_db_schema

# Start the backend server
python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
```

Verify: open http://localhost:8011/health — should return `{"health": "ok", ...}`

### 4b. Frontend Only

```powershell
# From repo root
cd e2etraceapp
npm install     # first time only
npm run dev -- --host 127.0.0.1 --port 5173
```

Verify: open http://localhost:5173 — React dashboard loads.

> The frontend Vite dev server proxies `/api/*` requests to `http://localhost:8011` automatically (configured in `e2etraceapp/vite.config.js`).

### 4c. MCP Server Only

```powershell
# From repo root, venv must be active
python -m uvicorn mcp_server.main:app --host 0.0.0.0 --port 8012
```

### 4d. Individual Agents (Debugging)

```powershell
# From repo root, venv must be active
# The PYTHONPATH must include both repo root and python_backend
$env:PYTHONPATH = "$(Get-Location);$(Get-Location)\python_backend"

# Start a specific agent
python -m agent_services.chat_coordinator.main
python -m agent_services.data_analyst.main
python -m agent_services.etl_orchestrator.main
# etc.
```

> **Normal operation:** Use `.\graphtrace.ps1 -Start` to run everything at once.

---

## 5. Database Schema Details

### PostgreSQL Tables
All tables are created automatically by `python -m scripts.init_db_schema` via SQLAlchemy `Base.metadata.create_all()`. The ORM models are defined across:

| Module | Tables | Purpose |
| :--- | :--- | :--- |
| `models/configuration_models.py` | `data_source_configs`, `encrypted_configs` | Data source CRUD, encrypted settings |
| `models/admin_config_models.py` | `connection_configs`, `system_configurations`, `llm_provider_configs`, `embedding_model_configs`, `feature_flags`, `config_audit_logs` | Admin Configuration Center |
| `models/pipeline_config_models.py` | `file_pattern_configs`, `pipeline_templates`, `search_configurations`, `index_configurations`, `neo4j_schema_configs` | Pipeline Wizard, search, indexing |
| `models/plm_models.py` | `plm_parts`, `plm_etl_runs`, `plm_etl_staged_records` | PLM ETL and Migration Wizard |
| `models/quality_models.py` | `quality_scores`, `quality_issues` | Data quality / SODA validation |
| `models/rule_engine_models.py` | `rule_sets`, `rules`, `rule_templates`, `rule_set_executions`, `rule_executions`, `quarantine_records` | PLM Rule Engine |
| `models/workflow_models.py` | `workflow_*` | Workflow / pipeline execution |
| `models/report_models.py` | `reports`, `report_*` | Reporting |
| `models/graphql_models.py` | (various) | GraphQL schema |

### Neo4j Schema (Optional)
Neo4j constraints and indexes are **not created automatically** during bootstrap. They are applied:
1. **Via the Data Pipeline Wizard UI** — when a user runs a Neo4j pipeline with "Create constraints automatically" enabled.
2. **Via the seed script** — if Neo4j is running and `NEO4J_PASSWORD` is set:
   ```powershell
   cd python_backend
   $env:NEO4J_URI = "bolt://localhost:7687"
   $env:NEO4J_USER = "neo4j"
   $env:NEO4J_PASSWORD = "your-neo4j-password"
   python -m scripts.seed_unstructured_workflows
   ```
   This creates:
   - `CONSTRAINT doc_id` (unique Document.doc_id)
   - `CONSTRAINT entity_id` (unique Entity.entity_id)
   - `CONSTRAINT part_id` (unique Part.part_id)
   - `CONSTRAINT assembly_id` (unique Assembly.assembly_id)
   - `INDEX doc_title` (Document.title)
   - `INDEX entity_name` (Entity.name)
   - `INDEX part_name` (Part.name)
3. **Manually** via Cypher in the Neo4j Browser:
   ```cypher
   CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;
   CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.entity_id IS UNIQUE;
   CREATE CONSTRAINT part_id IF NOT EXISTS FOR (p:Part) REQUIRE p.part_id IS UNIQUE;
   CREATE CONSTRAINT assembly_id IF NOT EXISTS FOR (a:Assembly) REQUIRE a.assembly_id IS UNIQUE;
   CREATE INDEX doc_title IF NOT EXISTS FOR (d:Document) ON (d.title);
   CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name);
   CREATE INDEX part_name IF NOT EXISTS FOR (p:Part) ON (p.name);
   ```

> **Note:** Neo4j is optional. The application starts without it; readiness is reflected in the `/health` endpoint.

### Resetting the Database
For development, you can drop and recreate all tables:
```powershell
cd python_backend
python -m scripts.reset_postgres_schema --yes --confirm-db graphtrace
# Then re-initialize:
python -m scripts.init_db_schema
```

## 6. Script Reference

| Script | Purpose | How to Run |
| :--- | :--- | :--- |
| `graphtrace.ps1` | **Single entry point** — diagnostics + full stack launcher | `.\graphtrace.ps1 -Check` or `.\graphtrace.ps1 -Start` |
| `scripts/diagnostics.py` | Preflight checks (Python, Node, .env, Postgres connectivity) | Called automatically by `graphtrace.ps1` |
| `scripts/start.py` | Multiplexer — launches all 11 services in parallel | Called automatically by `graphtrace.ps1 -Start` |
| `python_backend/scripts/init_db_schema.py` | Creates all PostgreSQL tables + seeds default config | Called automatically by `scripts/start.py` |
| `python_backend/scripts/reset_postgres_schema.py` | **Destructive** — drops and recreates all tables | `python -m scripts.reset_postgres_schema --yes --confirm-db graphtrace` |
| `python_backend/smoke-backend.ps1` | Quick backend smoke test (dev helper) | `.\python_backend\smoke-backend.ps1` |

---

## 7. Environment Variables Reference

All variables are set in `python_backend/.env`. The backend reads this file when `GRAPH_TRACE_LOAD_DOTENV=true`.

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | **Yes** | *(none)* | Full Postgres connection string (`postgresql://user:pass@host:port/db`) |
| `GRAPH_TRACE_LOAD_DOTENV` | **Yes** (local dev) | `false` | Must be `true` for the backend to read `python_backend/.env` |
| `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` | Auto-generated | *(auto)* | Fernet key for encrypted DB config; auto-generated by diagnostics if missing |
| `POSTGRES_HOST` | No | `localhost` | Individual Postgres setting (overridden by `DATABASE_URL`) |
| `POSTGRES_PORT` | No | `5432` | Individual Postgres setting (overridden by `DATABASE_URL`) |
| `POSTGRES_DATABASE` | No | `graphtrace` | Individual Postgres setting (overridden by `DATABASE_URL`) |
| `POSTGRES_USER` | No | `postgres` | Individual Postgres setting (overridden by `DATABASE_URL`) |
| `POSTGRES_PASSWORD` | No | *(empty)* | Individual Postgres setting (overridden by `DATABASE_URL`) |
| `NEO4J_URI` | No | *(none)* | Neo4j connection (optional) |
| `NEO4J_USER` | No | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | No | *(none)* | Neo4j password |
| `OPENSEARCH_URL` | No | *(none)* | OpenSearch connection (optional) |
| `GRAPH_TRACE_AUTH_REQUIRED` | No | `false` | Enable JWT authentication |
| `GRAPH_TRACE_JWT_SECRET` | If auth enabled | *(none)* | JWT signing secret |
| `GRAPH_TRACE_API_KEY` | No | *(none)* | Optional API key authentication |
| `GRAPH_TRACE_SKIP_DB_CHECK` | No | `false` | Skip Postgres connectivity check in diagnostics |
| `GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG` | No | `false` | Allow re-encryption of DB-backed config if key changed |

---

## 8. Troubleshooting

| Problem | Solution |
| :--- | :--- |
| **"Missing module" errors** | Activate `.venv` and reinstall: `.\.venv\Scripts\Activate.ps1` then `pip install -r python_backend\requirements.txt` |
| **"Database connection refused"** | Verify PostgreSQL is running (`Get-Service PostgreSQL*`), check port (`netstat -ano \| findstr :5432`), verify `DATABASE_URL` in `python_backend\.env` |
| **"Encryption key mismatch"** | Set `GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true` in `.env`, then run `cd python_backend; python -m scripts.init_db_schema` |
| **"Port already in use"** | Press `Ctrl+C` in the multiplexer terminal, or kill the process: `Get-Process -Id (Get-NetTCPConnection -LocalPort 8011).OwningProcess \| Stop-Process` |
| **Frontend shows blank page** | Check backend is running: `curl http://localhost:8011/health` |
| **`graphtrace.ps1` says "Virtual environment not found"** | Run: `python -m venv .venv` from repo root, then retry |
| **Diagnostics say "placeholder credentials"** | Edit `python_backend\.env` — replace `yourpassword` with your real PostgreSQL password |

---

## 9. Multi-VM Deployment

For production deployments across separate virtual machines, configure each component's `.env` file with network-accessible addresses instead of `localhost`/`127.0.0.1`.

> **Port note:** Replace `<PG_PORT>` below with your actual PostgreSQL port (5432 or 5433 — whatever your DBA configured on VM1).

### Example Architecture

```
VM 1 (Database): PostgreSQL, Neo4j (7687), Redis (6379)
VM 2 (Backend):  FastAPI Backend (8011), MCP Server (8012)
VM 3 (Frontend): Vite Dev Server (5173) OR Nginx/Apache serving static build
VM 4 (Agents):   AI Agent Services (8020-8025)
```

### Configuration Steps

#### VM1 — Database Server
Ensure PostgreSQL, Neo4j, and Redis accept network connections:

**PostgreSQL** (`postgresql.conf`):
```conf
listen_addresses = '*'  # Or specific IP
```

**PostgreSQL** (`pg_hba.conf`):
```conf
host    graphtrace    postgres    10.0.0.0/24    scram-sha-256
```

**Neo4j** (`neo4j.conf`):
```conf
dbms.default_listen_address=0.0.0.0
```

#### VM2 — Backend Server
Edit `python_backend/.env`:
```dotenv
# Use VM1's IP address and YOUR PostgreSQL port
DATABASE_URL=postgresql://postgres:REAL_PASSWORD@10.0.0.10:<PG_PORT>/graphtrace
POSTGRES_PORT=<PG_PORT>
NEO4J_URI=neo4j://10.0.0.10:7687
REDIS_HOST=10.0.0.10

# Bind to all interfaces so other VMs can reach the API
BACKEND_HOST=0.0.0.0

# Allow frontend VM origin
GRAPH_TRACE_ALLOWED_ORIGINS=["http://10.0.0.30:5173","https://yourdomain.com"]
```

The MCP server reads from the same `python_backend/.env` file automatically.

#### VM3 — Frontend Server

**Development Mode** — edit `e2etraceapp/.env`:
```dotenv
VITE_API_BASE_URL=http://10.0.0.20:8011
VITE_DEV_PROXY_TARGET=http://10.0.0.20:8011
```

**Production Mode** — build static assets and proxy via Nginx/Apache:
```powershell
cd e2etraceapp
npm run build    # outputs to dist/
```

```nginx
# Nginx config on VM3
server {
    listen 80;
    root /path/to/e2etraceapp/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://10.0.0.20:8011;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /health {
        proxy_pass http://10.0.0.20:8011;
    }
}
```

#### VM4 — Agent Services (Optional)
Set environment variables or create a `.env` with VM1 addresses:
```dotenv
DATABASE_URL=postgresql://postgres:REAL_PASSWORD@10.0.0.10:<PG_PORT>/graphtrace
NEO4J_URI=neo4j://10.0.0.10:7687
REDIS_URL=redis://10.0.0.10:6379/0
MCP_SERVER_URL=http://10.0.0.20:8012
```

### Firewall Rules

| Source | Target | Port | Protocol | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| VM2 (Backend) | VM1 (DB) | `<PG_PORT>` | TCP | PostgreSQL |
| VM2 (Backend) | VM1 (DB) | 7687 | TCP | Neo4j Bolt |
| VM2 (Backend) | VM1 (DB) | 6379 | TCP | Redis |
| VM3 (Frontend) | VM2 (Backend) | 8011 | TCP | Backend API |
| VM4 (Agents) | VM1 (DB) | `<PG_PORT>`, 7687, 6379 | TCP | Database access |
| VM4 (Agents) | VM2 (MCP) | 8012 | TCP | MCP registration |
| Client browser | VM3 (Frontend) | 80/443 | TCP | UI access |

### Security Checklist

- [ ] Replace all default/placeholder passwords in `.env` files
- [ ] Enable SSL/TLS for PostgreSQL (`sslmode=require` in `DATABASE_URL`)
- [ ] Enable SSL/TLS for Neo4j
- [ ] Set `GRAPH_TRACE_AUTH_REQUIRED=true` in backend `.env`
- [ ] Configure `GRAPH_TRACE_JWT_SECRET` with a strong random value
- [ ] Restrict firewall rules to only the VMs that need access
- [ ] Use environment-specific secrets management (Azure Key Vault, HashiCorp Vault, etc.)
