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
├── docs/                      # Documentation
└── config/                    # Runtime configuration files
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

### Step 1: Clone the Repository
```powershell
git clone https://github.com/dparitosh/GoodpointAI.git
cd GoodpointAI
```

### Step 2: Configure PostgreSQL
Create a database named `graphtrace` in your local PostgreSQL instance:
```sql
CREATE DATABASE graphtrace;
```
Then create `python_backend/.env` with your connection string:
```dotenv
DATABASE_URL=postgresql://postgres:yourpassword@127.0.0.1:5432/graphtrace
```

### Step 3: Bootstrap Environment
Run the bootstrap script. This will:
- Create a Python virtual environment at `.venv/`
- Install all backend pip dependencies
- Generate an encryption key (`.graphtrace.encryption_key`)
- Initialize the database schema and seed default configuration
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
- **API Docs (Swagger)**: [http://localhost:8011/docs](http://localhost:8011/docs)

## Manual Installation (Step-by-Step)

### Backend
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
cd python_backend
pip install -r requirements.txt

# 3. Initialize database schema
python -m scripts.init_db_schema

# 4. Start the server
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

## Script Reference

| Script | Purpose | Usage |
| :--- | :--- | :--- |
| `bootstrap.ps1` | First-time setup (venv, deps, DB) | Run once after clone |
| `start-all.ps1` | Launch entire stack | Daily dev startup |
| `start-backend.ps1` | Backend only | `start-backend.ps1 -UpdateDeps` to force pip install |
| `start-frontend.ps1` | Frontend only | `start-frontend.ps1 -UpdateDeps` to force npm install |
| `stop-all.ps1` | Kill all Python/Node processes | Cleanup |

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
