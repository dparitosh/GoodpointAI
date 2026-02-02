# Copilot instructions for GoodpointAI (GraphTrace)

## Repo layout (use this as the source of truth)
- **Primary app lives in `agentic-restored/`** (root-level `python_backend/` + `e2etraceapp/` are duplicates/legacy).
- Backend: `agentic-restored/python_backend` (FastAPI + Postgres, optional Neo4j/OpenSearch)
- Frontend: `agentic-restored/e2etraceapp` (React + Vite)

## Big picture architecture
- UI talks to backend via `/api/*` and `/health`.
  - In dev, **Vite proxies** these routes to FastAPI (see `agentic-restored/e2etraceapp/vite.config.js`).
  - API endpoints are centrally enumerated in `agentic-restored/e2etraceapp/src/config/api-config.js`.
- Backend entrypoint is `agentic-restored/python_backend/main.py`:
  - Routers are split across `graph_api/*_router.py` and `routers/*_router.py` and included into one `FastAPI()`.
  - Dependency readiness is tracked as `app.state.db_ok` / `app.state.neo4j_ok` (see `core/lifespan.py`), surfaced by `/health`.
- **Postgres is the single source of truth** for persistence and admin configuration.
  - Many runtime settings are **DB-backed + encrypted** (`core/config_store.py`, `models/configuration_models.py`).
  - `.env` is for local dev bootstrapping only; installed deployments expect DB-backed config.
  - Most operator-facing settings are edited via the UI Admin page: `http://localhost:5173/#/admin`.

## Dev workflows (Windows-first)
- Bootstrap/install: `./bootstrap.ps1` (repo root) or `agentic-restored/bootstrap.ps1`.
- Run full stack: `./start-all.ps1` (or VS Code task “Start Full Stack (Frontend + Backend)”).
- Backend manual: `python -m uvicorn --app-dir agentic-restored/python_backend main:app --reload --port 8011`.
- Frontend manual: `cd agentic-restored/e2etraceapp && npm install && npm run dev -- --host 127.0.0.1 --port 5173`.
- Tests:
  - Backend: run pytest in `agentic-restored/python_backend` (VS Code task “Backend: Test (Pytest)”).
  - Frontend: `npm test -- --run` in `agentic-restored/e2etraceapp` (Vitest; see `vitest.config.js`).

## Configuration rules that matter in this repo
- Backend loads repo-local `.env` **only when** `GRAPH_TRACE_LOAD_DOTENV=true` (see `core/external_config.py`).
- Keep `DATABASE_URL` correct in `agentic-restored/python_backend/.env` (Postgres required).
- Set `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` for decrypting DB-backed config.
  - If you changed the key and can’t decrypt old values: set `GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true` and run `python -m scripts.init_db_schema`.
- Optional services:
  - Neo4j connection is best-effort (API still starts without it); readiness is reflected in `/health`.
  - OpenSearch endpoints fail-closed unless `OPENSEARCH_URL` is configured.
 - CORS allow-origins can come from DB-backed encrypted config key `cors` (fallback: `ALLOWED_ORIGINS` env); see `_get_allowed_origins()` in `python_backend/main.py`.

## Backend conventions/patterns
- Security middleware is centralized in `core/security_middleware.py`:
  - Allowlisted paths: `/health`, `/docs`, `/openapi.json`, `/api/auth`, etc.
  - Optional auth via `GRAPH_TRACE_API_KEY` / JWT (`core/auth.py`). Mutating `/api/*` calls require `admin` role when auth is enabled.
  - Rate limiting is in-memory per-IP (`RATE_LIMIT_PER_MINUTE`).
- DB schema + seeding scripts:
  - Safe init: `scripts/init_db_schema.py` (create tables + seed defaults)
  - Destructive reset: `scripts/reset_postgres_schema.py` (requires `--yes`, supports `--dry-run`)

## Frontend conventions/patterns
- Prefer `API_CONFIG` + helper wrappers (`src/config/api-config.js`, `src/api/e2etrace-api.js`, `src/utils/apiClient.js`).
- For local dev, rely on relative `/api/...` URLs so Vite proxy handles routing; override proxy target with `VITE_DEV_PROXY_TARGET` if needed.
 - `VITE_API_BASE_URL` is intended for test/prod-style absolute routing; dev typically leaves it empty.
