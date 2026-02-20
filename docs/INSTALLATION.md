# Installation Guide

## Directory Structure

```
GoodpointAI/
├── python_backend/            # FastAPI backend (Python 3.11+)
├── e2etraceapp/               # React/Vite frontend (Node 18+)
├── agent_services/            # MCP-powered AI agents
├── mcp_server/                # MCP coordination server
├── installation_scripts/      # All PowerShell/Batch scripts
│   ├── bootstrap.ps1          # First-time environment setup
│   ├── start-all.ps1          # Launch entire stack
│   ├── start-backend.ps1      # Launch backend only
│   ├── start-frontend.ps1     # Launch frontend only
│   ├── stop-all.ps1           # Kill all services
│   └── start-agent-*.ps1      # Individual agent launchers
└── docs/                      # Documentation
```

## Prerequisites

| Requirement | Version | Notes |
| :--- | :--- | :--- |
| **Python** | 3.11+ (recommended: 3.12) | Must be on `PATH` |
| **Node.js** | 18+ (recommended: 20) | Includes npm |
| **PostgreSQL** | 14+ | Required for persistence |
| **Neo4j** | 5+ | Optional (graph lineage) |
| **OpenSearch** | 2+ | Optional (vector/fulltext search) |

## Installation Steps (Windows)

### Single-Machine Installation (Default)

#### Step 1: Clone the Repository
```powershell
git clone https://github.com/dparitosh/GoodpointAI.git
cd GoodpointAI
```

#### Step 2: Configure PostgreSQL

#### 2a. Create the Database
Connect to your local PostgreSQL instance (e.g. via `psql`) and create the `graphtrace` database:
```sql
-- Connect as superuser / postgres
CREATE DATABASE graphtrace
  WITH OWNER = postgres
       ENCODING = 'UTF8'
       LC_COLLATE = 'en_US.UTF-8'
       LC_CTYPE = 'en_US.UTF-8'
       TEMPLATE = template0;

-- (Optional) Create a dedicated application user
CREATE USER graphtrace_app WITH PASSWORD 'changeme';
GRANT ALL PRIVILEGES ON DATABASE graphtrace TO graphtrace_app;
```

> **Tip:** If you already have a `graphtrace` database, skip this step.

#### 2b. Create the `.env` File
Copy the example and edit your connection details:
```powershell
Copy-Item python_backend\.env.example python_backend\.env
```
Then edit `python_backend/.env` — at minimum set `DATABASE_URL`:
```dotenv
DATABASE_URL=postgresql://postgres:yourpassword@127.0.0.1:5433/graphtrace
GRAPH_TRACE_LOAD_DOTENV=true
```

> **Note:** The bootstrap script (Step 3) will automatically copy `.env.example` → `.env`
> if the file doesn't exist yet, but you **must** edit `DATABASE_URL` with your actual
> Postgres credentials before proceeding. The bootstrap script will now validate that you have
> changed the default credentials and fail safely with instructions if you haven't.

### Step 3: Bootstrap Environment
Run the bootstrap script. This will:
- Copy `python_backend/.env.example` → `python_backend/.env` (if `.env` doesn't exist)
- **Check configuration**: Verifies `DATABASE_URL` is configured (fails if default `yourpassword` detected)
- Create a Python virtual environment at `.venv/`
- Install all backend pip dependencies
- Generate an encryption key (`.graphtrace.encryption_key`)
- Initialize the PostgreSQL database schema (all tables via SQLAlchemy `create_all`)
- Seed default configuration (all automatic via `init_db_schema`):
  - **Encrypted config keys**: `system_configuration`, `neo4j`, `opensearch`, `cors`, `workflow_defaults`
  - **Admin connections**: Primary PostgreSQL, Neo4j, OpenSearch, Redis
  - **LLM providers**: OpenAI, Anthropic, Azure OpenAI, Ollama, HuggingFace
  - **Embedding models**: MiniLM, MPNet, OpenAI, Cohere
  - **Feature flags**: LLM Chat, Vector Search, GraphRAG, Pipeline Wizard, etc.
  - **Pipeline templates**: File patterns, search/index configs, Neo4j schema configs
- Install all frontend npm dependencies

```powershell
.\installation_scripts\bootstrap.ps1
```

### Step 4: Start the Full Stack
Launch Backend, Frontend, MCP Server, and all AI Agents:
```powershell
.\installation_scripts\start-all.ps1
```

### Step 5: Verify
Open a browser and check:
- **Frontend UI**: [http://localhost:5173](http://localhost:5173)
- **Backend Health**: [http://localhost:8011/health](http://localhost:8011/health)
- **MCP Server Health**: [http://localhost:8012/health](http://localhost:8012/health) *(if MCP server started)*
- **API Docs (Swagger)**: [http://localhost:8011/docs](http://localhost:8011/docs)

> **Note:** The 6 agent services (Data Analyst, ETL Orchestrator, Visualization, Query Planner, Quality Monitor, Chat Coordinator) will be running on ports 8020-8025 if started via `start-all.ps1`. They do not have web UIs but can be verified via their log output in their respective terminal windows.

## Manual Installation (Step-by-Step)

### Backend
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
cd python_backend
pip install -r requirements.txt

# 3. Initialize database schema + seed all default configurations
#    This single command creates all PostgreSQL tables AND automatically seeds:
#    - Admin configs (LLM providers, embedding models, connections, feature flags)
#    - Pipeline configs (templates, file patterns, search/index configs, Neo4j schema)
#    - Encrypted config keys (system_configuration, neo4j, opensearch, cors, workflow_defaults)
python -m scripts.init_db_schema

# Note: The following are OPTIONAL - init_db_schema already calls these automatically:
# python -m scripts.seed_admin_configs      # Auto-run by init_db_schema
# python -m scripts.seed_pipeline_configs   # Auto-run by init_db_schema

# 6. Start the server
python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
```

### Frontend
```powershell
cd e2etraceapp
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### Individual Agents (Optional)
Each agent can be started independently from the repo root:
```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m agent_services.etl_orchestrator.main
python -m agent_services.data_analyst.main
```

## Database Schema Details

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

## Script Reference

### Main Scripts

| Script | Purpose | Platform | Usage |
| :--- | :--- | :--- | :--- |
| `bootstrap.ps1` | First-time setup (venv, deps, DB schema, seed) | Windows (PowerShell) | Run once after clone |
| `start-all.ps1` | Launch full stack (Backend, MCP, 6 Agents, Frontend) | Windows (PowerShell) | Daily dev startup |
| `start-all.bat` | Launch full stack (same as .ps1) | Windows (CMD) | Alternative for batch users |
| `start-backend.ps1` | Backend API server only | Windows (PowerShell) | Add `-UpdateDeps` to force pip install |
| `start-backend.bat` | Backend API server only | Windows (CMD) | Batch equivalent |
| `start-frontend.ps1` | Frontend dev server only | Windows (PowerShell) | Add `-UpdateDeps` to force npm install |
| `start-frontend.bat` | Frontend dev server only | Windows (CMD) | Batch equivalent |
| `stop-all.ps1` | Kill all Python/Node processes | Windows (PowerShell) | Cleanup orphan processes |

### Individual Service Scripts

| Script | Service | Port |
| :--- | :--- | :--- |
| `start-mcp-server.ps1` | MCP Coordination Server | 8012 |
| `start-agent-data-analyst.ps1` | Data Analyst Agent | 8020 |
| `start-agent-etl-orchestrator.ps1` | ETL Orchestrator Agent | 8021 |
| `start-agent-visualization.ps1` | Visualization Agent | 8022 |
| `start-agent-query-planner.ps1` | Query Planner Agent | 8023 |
| `start-agent-quality-monitor.ps1` | Quality Monitor Agent | 8024 |
| `start-agent-chat-coordinator.ps1` | Chat Coordinator Agent | 8025 |

> **Note:** Individual service scripts are PowerShell-only. Use `start-all.bat` for batch file support of all services.

## Environment Variables

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Yes | *(none)* | Postgres connection string |
| `GRAPH_TRACE_LOAD_DOTENV` | No | `false` | Set `true` to load `.env` file |
| `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` | Auto | *(generated)* | Fernet key for encrypted DB config |
| `NEO4J_URI` | No | *(none)* | Neo4j connection (optional) |
| `OPENSEARCH_URL` | No | *(none)* | OpenSearch connection (optional) |
| `GRAPH_TRACE_AUTH_REQUIRED` | No | `false` | Enable JWT auth |

## Troubleshooting

- **"Missing module" errors**: Run `.\installation_scripts\start-backend.ps1 -UpdateDeps` to force reinstall.
- **Database connection refused**: Ensure PostgreSQL is running and `DATABASE_URL` in `python_backend/.env` is correct.
- **Encryption key mismatch**: Delete `.graphtrace.encryption_key` and re-run bootstrap, or set `GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true` then run `python -m scripts.init_db_schema`.
- **Port already in use**: Run `.\installation_scripts\stop-all.ps1` to kill orphan processes.

## Multi-VM Deployment

For production deployments across separate virtual machines, configure each component's `.env` file with network-accessible addresses instead of `localhost`/`127.0.0.1`.

### Example Architecture

```
VM 1 (Database): PostgreSQL (port 5433), Neo4j (port 7687), Redis (port 6379)
VM 2 (Backend):  FastAPI Backend (port 8011), MCP Server (port 8012)
VM 3 (Frontend): Vite Dev Server (port 5173) OR Nginx/Apache serving static build
VM 4 (Agents):   AI Agent Services (ports 8020-8025)
```

### Configuration Steps

#### 1. VM1 (Database Server)
Ensure PostgreSQL, Neo4j, and Redis are configured to accept network connections:

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

#### 2. VM2 (Backend Server)
Edit `python_backend/.env`:
```dotenv
# Use VM1's IP address (not localhost)
DATABASE_URL=postgresql://postgres:yourpassword@10.0.0.10:5433/graphtrace
NEO4J_URI=neo4j://10.0.0.10:7687
REDIS_HOST=10.0.0.10

# Bind to all interfaces so other VMs can reach the API
BACKEND_HOST=0.0.0.0

# Allow frontend VM origin
GRAPH_TRACE_ALLOWED_ORIGINS=["http://10.0.0.30:5173","https://yourdomain.com"]
```

Edit `mcp_server/.env`:
```dotenv
# MCP binds to all interfaces
MCP_SERVER_HOST=0.0.0.0

# Use VM1's database addresses
DATABASE_URL=postgresql://postgres:yourpassword@10.0.0.10:5433/graphtrace
REDIS_URL=redis://10.0.0.10:6379/0
```

#### 3. VM3 (Frontend Server)

**Development Mode:**
Edit `e2etraceapp/.env`:
```dotenv
# Point to VM2's backend
VITE_API_BASE_URL=http://10.0.0.20:8011
VITE_DEV_PROXY_TARGET=http://10.0.0.20:8011
```

**Production Mode:**
Build the static assets and configure your web server (Nginx/Apache) to proxy `/api/*` requests to VM2:

```nginx
# Nginx example
location /api/ {
    proxy_pass http://10.0.0.20:8011;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

#### 4. VM4 (Agent Services - Optional)
Each agent's `main.py` loads `python_backend/.env`. Create a shared `.env` or set environment variables:
```dotenv
DATABASE_URL=postgresql://postgres:yourpassword@10.0.0.10:5433/graphtrace
NEO4J_URI=neo4j://10.0.0.10:7687
REDIS_URL=redis://10.0.0.10:6379/0
```

Agents register with the MCP server on VM2:
```dotenv
MCP_SERVER_URL=http://10.0.0.20:8012
```

### Firewall Rules
Ensure the following ports are open between VMs:

| Source VM | Target VM | Ports | Purpose |
|-----------|-----------|-------|----------|
| VM2 (Backend) | VM1 (DB) | 5433, 7687, 6379 | Database access |
| VM3 (Frontend) | VM2 (Backend) | 8011 | API requests |
| VM4 (Agents) | VM1 (DB) | 5433, 7687, 6379 | Database access |
| VM4 (Agents) | VM2 (MCP) | 8012 | Agent registration |
| Client Browser | VM3 (Frontend) | 5173, 80, 443 | UI access |

### Security Considerations

1. **Do not use default passwords** — change all credentials in `.env` files
2. **Enable SSL/TLS** for PostgreSQL and Neo4j in production
3. **Use firewall rules** to restrict access between VMs
4. **Enable authentication** by setting `GRAPH_TRACE_AUTH_REQUIRED=true` in backend `.env`
5. **Use environment-specific secrets management** (Azure Key Vault, AWS Secrets Manager, etc.)
