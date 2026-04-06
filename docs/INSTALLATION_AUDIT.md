# Installation Audit (docs-and-scripts-restructure)

Date: 2026-04-06

This document audits installation scripts and documented installation steps on the `docs-and-scripts-restructure` branch.

## Executive summary

- The repo **does not contain** an `installation_scripts/` folder on this branch.
- The canonical "full stack" entrypoint on this branch is **`graphtrace.ps1`**, which runs:
  - `scripts/diagnostics.py` (preflight checks)
  - `scripts/start.py` (multi-process launcher)
- The "full stack" launcher starts **Frontend + Backend + MCP server + multiple agent services**.
  - Therefore installation steps must install **backend + MCP server** Python dependencies (and Node deps).
- Found and fixed a critical issue: **`mcp_server/main.py` was syntactically broken**, which would prevent MCP server startup.

## What exists vs what docs previously claimed

### Previously claimed layout (incorrect for this branch)

The installation guide previously referenced:

- `installation_scripts/bootstrap.ps1`
- `installation_scripts/start-all.ps1`
- `installation_scripts/start-backend.ps1`
- `installation_scripts/start-frontend.ps1`
- `installation_scripts/stop-all.ps1`

These do **not** exist in this branch.

### Actual entrypoints in this branch

- `graphtrace.ps1`
  - `-Check` runs `scripts/diagnostics.py`
  - `-Start` runs diagnostics then `scripts/start.py`

- `scripts/diagnostics.py`
  - Validates Python/Node/NPM are installed
  - Ensures `python_backend/.env` exists (copies from `.env.example` if missing)
  - Auto-generates `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` if missing
  - Treats `NEO4J_URI` and `OPENSEARCH_URL` as optional

- `scripts/start.py`
  - Sets `GRAPH_TRACE_LOAD_DOTENV=true`
  - Runs `python -m scripts.init_db_schema` in `python_backend/`
  - Starts:
    - Frontend (`npm run dev`)
    - Backend (`uvicorn main:app --port 8011`)
    - MCP server (`uvicorn mcp_server.main:app --port 8012`)
    - Multiple agent services (`python -m agent_services.<agent>.main`)

## Dependency installation coverage

### Observations

- The backend dependencies are in `python_backend/requirements.txt` (pinned).
- MCP server dependencies are in `mcp_server/requirements.txt` (includes `azure-servicebus`).
- Agents have their own small `requirements.txt` files, but most runtime imports are already covered by backend deps.

### Risk if only backend deps are installed

If you only run:

- `pip install -r python_backend/requirements.txt`

then the full stack launcher may fail when starting MCP server because `mcp_server/queue_client.py` imports `azure.servicebus.*`.

### Recommendation

For the full stack launcher (`graphtrace.ps1 -Start`), install:

- `pip install -r python_backend/requirements.txt -r mcp_server/requirements.txt`

and then install frontend deps:

- `cd e2etraceapp && npm install`

## Environment files (.env)

### Observations

- Backend uses `python_backend/.env`.
- Agent services explicitly load `python_backend/.env`.
- MCP server configuration originally loaded `.env` from the repo root, which was inconsistent.

### Fix applied

- MCP server now also loads config from `python_backend/.env`.

## Database/schema automation

- `python_backend/scripts/init_db_schema.py` exists and:
  - Validates `DATABASE_URL`
  - Runs `init_db()` (SQLAlchemy create_all)
  - Applies idempotent PLM migration statements
  - Seeds DB-backed configs (defaults + admin + pipeline)

- `python_backend/scripts/reset_postgres_schema.py` exists and supports safe destructive reset flags.

## Actionable checklist (validated)

1. Create and activate venv:
   - `python -m venv .venv`
   - `./.venv/Scripts/Activate.ps1`
2. Install Python deps:
   - `pip install -r python_backend/requirements.txt -r mcp_server/requirements.txt`
3. Install frontend deps:
   - `cd e2etraceapp; npm install; cd ..`
4. Configure Postgres and set `DATABASE_URL` in `python_backend/.env`.
5. Start stack:
   - `./graphtrace.ps1 -Start`

## Files changed as part of this audit

- `docs/INSTALLATION.md` — corrected script paths and dependency install steps
- `mcp_server/main.py` — repaired syntax and endpoint behavior
- `mcp_server/dag_executor.py`, `mcp_server/orchestrator.py` — cleaned to be consistent and error-free
- `mcp_server/config.py` — loads `python_backend/.env`
- `scripts/diagnostics.py` — path-safe, copies `.env.example`, treats optional services correctly
- `graphtrace.ps1` — path-safe and improved guidance
