# Installation & Deployment Specification

This document defines the **installation/deployment specification** for the GoodPoint AgenticAI (GraphTrace) application.

It is intentionally more formal than the step-by-step runbook in `docs/INSTALLATION.md`.

## Scope

This specification covers:

- Local developer/workstation installation (Windows-first)
- A “single-node” deployment model (all services on one machine or reachable over the network)

This specification does **not** cover enterprise HA/DR topologies.

## System overview

### Components

| Component | Path | Tech | Purpose |
|---|---|---|---|
| Frontend UI | `agentic-restored/e2etraceapp` | React + Vite | End-user web UI, routed with hash router |
| Backend API | `agentic-restored/python_backend` | FastAPI | REST API, persistence, integrations |
| Persistence DB (required) | external | PostgreSQL | **Required** persistence (workflows, reports, config) |
| Lineage graph DB (optional) | external | Neo4j | Optional lineage graph + graph exploration |
| Search/index (optional) | external | OpenSearch | Optional indexing & retrieval |

### Canonical ports

| Service | Default | Notes |
|---|---:|---|
| Backend (FastAPI) | 8011 | `uvicorn main:app --port 8011` |
| Frontend (Vite dev) | 5173 | `npm run dev -- --port 5173` |

> If you change ports, update your local run commands and any reverse proxy rules.

## Platform requirements

### Supported OS

- **Windows 10/11** (first-class support via PowerShell scripts)

Linux/macOS can work for development, but the repository automation scripts are Windows-oriented.

### Required software

- **Python 3.11+** (recommended: 3.12)
- **Node.js 18+** (recommended: 20)
- **PostgreSQL 14+** (required)

### Optional software (feature-gated)

- Neo4j (for `/#/lineage` and `/#/graph-explorer` graph features)
- OpenSearch (for retrieval/indexing features)

## Python dependencies

### Single requirements file

Backend dependencies are consolidated into:

- `agentic-restored/python_backend/requirements.txt`

Legacy files under the **canonical backend folder** (`agentic-restored/python_backend`) are retained only as compatibility wrappers and forward to `requirements.txt`:

- `agentic-restored/python_backend/requirement.txt`
- `agentic-restored/python_backend/requirements-dev.txt`
- `agentic-restored/python_backend/requirements_external_integrations.txt`

Note: this repository also contains a legacy duplicate backend folder at repo root (`python_backend/`). The primary application is `agentic-restored/python_backend`.

## Configuration specification

### Backend environment variables

Backend configuration is read from environment variables and optionally from:

- `agentic-restored/python_backend/.env`

The VS Code backend tasks run with dotenv loading enabled:

- `GRAPH_TRACE_LOAD_DOTENV=true`

#### Required variables

| Variable | Required | Example | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://user:pass@127.0.0.1:5432/graphtrace` | Postgres connection string |

#### Strongly recommended variables

| Variable | Recommended | Purpose |
|---|---|---|
| `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` | Yes | Encrypt/decrypt DB-backed admin configuration values |
| `GRAPH_TRACE_ALLOWED_LOCAL_ROOTS` | If using local folder datasources | Allowlist for filesystem import roots (semicolon-delimited on Windows) |

#### Auth-required mode (optional)

| Variable | Used when | Purpose |
|---|---|---|
| `GRAPH_TRACE_AUTH_REQUIRED=true` | Running backend in auth-required mode | Enforce JWT auth |
| `GRAPH_TRACE_JWT_SECRET` | auth-required | JWT signing secret |
| `GRAPH_TRACE_ADMIN_USERNAME` / `GRAPH_TRACE_ADMIN_PASSWORD` | auth-required | Bootstrap admin credentials |

## Installation procedure (normative)

### 1) Postgres setup

- A Postgres database MUST exist and be reachable from the backend host.
- `DATABASE_URL` MUST be set.

### 2) Backend setup

The backend MUST be installed in an isolated environment (venv recommended).

- Install Python dependencies from `agentic-restored/python_backend/requirements.txt`.
- Initialize schema:
  - `python -m scripts.init_db_schema` (from `agentic-restored/python_backend`)

### 3) Frontend setup

- Install Node dependencies in `agentic-restored/e2etraceapp`.
- Run the Vite dev server.

## Operational verification

A deployment is considered healthy when:

- `GET http://localhost:8011/health` returns HTTP 200
- `GET http://localhost:8011/docs` loads
- `GET http://localhost:5173` loads the UI
- `/#/admin` loads and can fetch configuration tabs

## Script audit (implementation notes)

Windows scripts are provided under repo root and `agentic-restored/`.

### Bootstrap

- `bootstrap.ps1` and `agentic-restored/bootstrap.ps1`
  - Creates/activates a venv
  - Installs backend deps (now `requirements.txt`)
  - Generates/loads `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY`
  - Initializes DB schema
  - Runs `npm install` for the frontend

### Start scripts

- `start-all.ps1` / `agentic-restored/start-all.ps1`: starts frontend+backend in separate shells
- `start-backend.ps1` / `.bat`: creates venv (if missing), installs deps, initializes schema best-effort, starts uvicorn
- `start-frontend.ps1` / `.bat`: runs the Vite dev server

### Diagnostics

- `diagnostics/windows/audit_frontend_backend.py` imports the backend app to compare routes and expects deps installed via `python_backend/requirements.txt`.

## Security considerations

- Do not commit real secrets to `.env`.
- Prefer using environment variables in your shell/session or a secrets manager for production.
- Keep `GRAPH_TRACE_ALLOWED_LOCAL_ROOTS` narrow; it controls local file access boundaries.

## References

- `docs/INSTALLATION.md` (step-by-step)
- `docs/EXECUTION_GUIDE.md` (runbook)
- `docs/USER_GUIDE.md` (UI/UX reference)
