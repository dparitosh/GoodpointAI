# Installation (Windows-first)

The runnable application lives under:

- Backend: `agentic-restored/python_backend` (FastAPI)
- Frontend: `agentic-restored/e2etraceapp` (React/Vite)

## Fastest path (recommended)

From repo root:

1) Run bootstrap once (creates `.venv`, installs deps, initializes DB schema):

```powershell
./bootstrap.ps1
```

2) Start everything:

```powershell
./start-all.ps1
```

Notes:

- If you prefer, you can use the VS Code task **Start Full Stack (Frontend + Backend)**.
- If you run from `agentic-restored/`, the equivalent scripts are `agentic-restored/bootstrap.ps1` and `agentic-restored/start-all.ps1`.

## Prerequisites

Install these first:

- **Python 3.11+** (recommended: 3.12)
- **Node.js 18+** (recommended: 20)
- **PostgreSQL 14+** (required)

Optional (only if you want the features):

- **Neo4j** (lineage graph)
- **OpenSearch** (index/search)

## 1) PostgreSQL (required)

GraphTrace is **Postgres-only** for persistence.

### Create a database

Create a database (example: `graphtrace`).

If `psql` is available:

```powershell
psql -U postgres -h localhost -p 5432 -c "CREATE DATABASE graphtrace;"
```

> If your Postgres runs on a different port (e.g., 5433), use that port.

### Configure backend connection

Edit:

- `agentic-restored/python_backend/.env`

Set `DATABASE_URL` like:

```dotenv
DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:5432/graphtrace"
```

Notes:

- VS Code tasks start the backend with `GRAPH_TRACE_LOAD_DOTENV=true`, so `.env` is loaded automatically.

## 2) Backend (FastAPI)

From repo root:

### Create a virtual environment

```powershell
python -m venv .venv
./.venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
```

Notes:

- This repo standardizes on a **single venv at repo root**: `.venv`.
- Where does `.venv` come from?
	- It is created by `bootstrap.ps1` (recommended) and also by `start-backend.ps1` / `start-backend.bat` if missing.
	- You should see it at: `GoodpointAI/.venv/`
- Why it matters: Python imports like `sqlalchemy` must be installed into the **same** interpreter that runs Uvicorn.

### Install backend dependencies

```powershell
pip install -r agentic-restored/python_backend/requirements.txt
```

### Initialize schema (Postgres)

```powershell
Push-Location agentic-restored/python_backend
python -m scripts.init_db_schema
Pop-Location
```

### Start the API

```powershell
python -m uvicorn --app-dir agentic-restored/python_backend main:app --host 0.0.0.0 --port 8011 --reload
```

Verify:

- Health: http://localhost:8011/health
- OpenAPI: http://localhost:8011/docs

## 3) Frontend (React/Vite)

```powershell
Push-Location agentic-restored/e2etraceapp
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### “npm reports vulnerabilities”

After `npm install`, npm may print something like “found X vulnerabilities”. This is an **npm dependency audit warning** (frontend ecosystem), not a Python error.

Recommended approach:

- For local dev, you can usually proceed.
- If you want to attempt a safe fix:
	- run `npm audit` to see details
	- run `npm audit fix` (non-breaking updates)
	- only use `npm audit fix --force` if you accept potentially breaking upgrades

Open:

- UI: http://localhost:5173

## 4) Optional integrations

### Neo4j (optional)

Configure via the UI Admin pages:

- http://localhost:5173/#/admin

### OpenSearch (optional)

Configure via the UI Admin pages:

- http://localhost:5173/#/admin

---

## Database Schema Management

All commands below assume you are in the `agentic-restored/python_backend` directory with the virtual environment activated.

### Initialize Schema (First-time / Safe)

Creates tables if they don't exist. Seeds default configuration. **Non-destructive**.

```powershell
python -m scripts.init_db_schema
```

This is automatically run by `bootstrap.ps1` and `start-backend.ps1`.

### Reset Schema (Drop & Recreate)

**⚠️ DESTRUCTIVE**: Drops all tables and recreates them empty. Use for dev/test cleanup.

```powershell
# Preview what will be dropped (safe):
python -m scripts.reset_postgres_schema --dry-run

# Actually reset (requires --yes):
python -m scripts.reset_postgres_schema --yes

# Reset with database name confirmation (recommended):
python -m scripts.reset_postgres_schema --yes --confirm-db graphtrace
```

After reset, run `init_db_schema` again to re-seed defaults:

```powershell
python -m scripts.init_db_schema
```

### Reset Encrypted Configuration Only

If encryption key changed and you want to reset only encrypted config (not all data):

```powershell
# Set this env var before running init_db_schema:
$env:GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG = "true"
python -m scripts.init_db_schema
```

### Initialize Rule Engine Tables

For the PLM Rule Engine specifically:

```powershell
# Create tables (safe):
python -m scripts.init_rule_engine_db

# Drop and recreate:
python -m scripts.init_rule_engine_db --drop
```

### Uninstall / Remove Database

To completely remove the GraphTrace database:

```powershell
# Option 1: Drop all tables but keep database
python -m scripts.reset_postgres_schema --yes --confirm-db graphtrace

# Option 2: Drop entire database (via psql)
psql -U postgres -h localhost -p 5432 -c "DROP DATABASE graphtrace;"
```

---

## Troubleshooting

- **503 from report/persistence endpoints**: Postgres not reachable/configured.
- **Encryption key errors**: Set `GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true` and re-run `init_db_schema`.
- Ports in use: free **8011** (backend) and **5173** (frontend) and restart.

### Dependency install failures / missing modules

If you see runtime errors like `ModuleNotFoundError: No module named 'pyodata'`, it usually means the backend dependencies were installed into a different Python environment than the one running Uvicorn.

- Ensure you are using the repo-root `.venv`.
- Reinstall with:
	- `pip install -r agentic-restored/python_backend/requirements.txt`

If the missing module is `sqlalchemy`, the fix is the same: install requirements into `.venv` and run Uvicorn using `.venv`.
