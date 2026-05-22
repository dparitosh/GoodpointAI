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

## PowerShell Execution Policy (Windows Users)

If you encounter the error: `cannot be loaded because running scripts is disabled on this system`, you need to allow PowerShell script execution.

Run PowerShell **as Administrator** and execute:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

This allows PowerShell scripts to run in the current user context. You can verify it worked with:

```powershell
Get-ExecutionPolicy
```

It should return `RemoteSigned` (or higher).

**Alternative (per-command)**: You can bypass execution policy for a single script without changing global policy:

```powershell
powershell -ExecutionPolicy Bypass -File .\bootstrap.ps1
```

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

## Installation (Recommended: Manual Method)

The manual step-by-step approach is **reliable and predictable** across Windows environments. Use this method for consistent results.

### 2) Backend (FastAPI)

From repo root:

#### Create a virtual environment

```powershell
Push-Location agentic-restored/python_backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

#### Install backend dependencies

```powershell
pip install -r requirements.txt
```

#### Initialize schema (Postgres)

```powershell
python -m scripts.init_db_schema
```

Then return to repo root:

```powershell
Pop-Location
```

### 3) Frontend (React/Vite)

```powershell
Push-Location agentic-restored/e2etraceapp
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

- UI: http://localhost:5173

## Alternative: Bootstrap Script (One-Command Setup)

If you prefer automated setup instead of the manual steps above, run the bootstrap script:

```powershell
# From repo root
.\agentic-restored\bootstrap.ps1
```

This handles **Backend + Frontend** setup automatically in one command:

- Creates Python virtual environment
- Installs all dependencies  
- Initializes database schema
- Generates encryption key
- Installs frontend npm packages

**Note**: The bootstrap script may encounter pip cache-related issues on some Windows configurations. If you experience `pip` hash validation errors, use the **manual installation** method described above instead.

## 4) Start the servers

### Option A: VS Code tasks (recommended)

Open VS Code and run the task:

- **Start Full Stack (Frontend + Backend)** (or start each separately)

### Option B: Manual start

#### Backend

From repo root:

```powershell
Push-Location agentic-restored/python_backend
.\venv\Scripts\Activate.ps1
python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
```

#### Frontend

From another terminal:

```powershell
Push-Location agentic-restored/e2etraceapp
npm run dev -- --host 127.0.0.1 --port 5173
```

### Option C: Scripts

From `agentic-restored/`:

- `start-all.ps1` (both servers)
- `start-backend.ps1` (backend only)
- `start-frontend.ps1` (frontend only)

## 5) Verification

Verify the installation:

- Health: http://localhost:8011/health
- OpenAPI: http://localhost:8011/docs
- UI: http://localhost:5173
- Admin: http://localhost:5173/#/admin

## 6) Optional integrations

### Neo4j (optional)

Configure via the UI Admin pages:

- http://localhost:5173/#/admin

### OpenSearch (optional)

Configure via the UI Admin pages:

- http://localhost:5173/#/admin

## Troubleshooting

- **503 from report/persistence endpoints**: Postgres not reachable/configured.
- **Script execution blocked**: See [PowerShell Execution Policy](#powershell-execution-policy-windows-users) section above.
- **Ports in use**: Free **8011** (backend) and **5173** (frontend), then restart.
- **Schema initialization fails**: Verify `DATABASE_URL` in `agentic-restored/python_backend/.env` and that Postgres is running.
