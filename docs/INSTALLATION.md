# Installation (Windows-first)

The runnable application lives under:

- Backend: `agentic-restored/python_backend` (FastAPI)
- Frontend: `agentic-restored/e2etraceapp` (React/Vite)

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
psql -U postgres -h localhost -p 5433 -c "CREATE DATABASE graphtrace;"
```

> If your Postgres runs on a different port, use that port.

### Configure backend connection

Edit:

- `agentic-restored/python_backend/.env`

Set `DATABASE_URL` like:

```dotenv
DATABASE_URL="postgresql://postgres:<password>@127.0.0.1:5433/graphtrace"
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

Open:

- UI: http://localhost:5173

## 4) Optional integrations

### Neo4j (optional)

Configure via the UI Admin pages:

- http://localhost:5173/#/admin

### OpenSearch (optional)

Configure via the UI Admin pages:

- http://localhost:5173/#/admin

## Troubleshooting

- **503 from report/persistence endpoints**: Postgres not reachable/configured.
- Ports in use: free **8011** (backend) and **5173** (frontend) and restart.
