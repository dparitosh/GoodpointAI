# Scripts Reference (Windows)

This page documents the repo scripts that bootstrap and start GraphTrace.

## Bootstrap

### `bootstrap.ps1`

Purpose:
- Validates prerequisites (optionally runs diagnostics)
- Creates backend venv and installs backend dependencies
- Installs frontend dependencies
- Initializes DB schema (Postgres) and seeds DB-backed configuration
- Creates/writes the configuration encryption key file for local dev

Typical usage:

```powershell
./bootstrap.ps1 -RunDiagnostics
```

Related diagnostics:
- `./diagnostics/windows/diagnose-all.ps1`

## Postgres schema + config seeding

These scripts live under `python_backend/scripts/`.

### `python -m scripts.init_db_schema`

Purpose:
- Ensures the **Postgres schema** exists (SQLAlchemy `create_all`)
- Seeds DB-backed encrypted config keys (best-effort) via `scripts.seed_db_config`

This is the script `bootstrap.ps1` runs.

### `python -m scripts.seed_db_config`

Purpose:
- Seeds default encrypted configuration keys if missing:
	- `system_configuration`, `neo4j`, `opensearch`, `cors`, `workflow_defaults`

Usage:

```powershell
Push-Location .\python_backend
./venv/Scripts/Activate.ps1
python -m scripts.seed_db_config
Pop-Location
```

Overwrite existing keys (careful):

```powershell
python -m scripts.seed_db_config --force
```

### `python -m scripts.seed_admin_configs`

Purpose:
- Seeds admin-facing tables (LLM providers, embedding models, connections, feature flags, system configs)

When to run:
- After DB migrations / when you want default admin entries in the database.

### `python -m scripts.seed_pipeline_configs`

Purpose:
- Seeds pipeline templates and related configurations (file patterns, search configs, index configs, Neo4j schema configs) into Postgres.

## Optional: seed OpenSearch + Neo4j fixtures

### `python -m scripts.seed_unstructured_workflows`

Purpose:
- Seeds demo/fixture workflows and optionally:
	- OpenSearch indices (creates indices + indexes documents)
	- Neo4j constraints/indexes (schema)

Inputs:
- Fixture file: `python_backend/fixtures/unstructured_workflows.json`
- Optional data folder: set `SPLM_FOLDER` to a directory containing `*.stp` and `*.xml` files.
	- If `SPLM_FOLDER` is not set, the script will look under `python_backend/fixtures/SPLM`.

Environment variables:
- OpenSearch: `OPENSEARCH_URL` (default `http://localhost:9200`)
- Neo4j: `NEO4J_URI` (default `bolt://localhost:7687`), `NEO4J_USER` (default `neo4j`), `NEO4J_PASSWORD` (required to seed)

Usage:

```powershell
Push-Location .\python_backend
./venv/Scripts/Activate.ps1
python -m scripts.seed_unstructured_workflows
Pop-Location
```

## Starting services

### `start-all.ps1`

Purpose:
- Starts backend + frontend (dev mode)

Typical usage:

```powershell
./start-all.ps1
```

Default URLs:
- Frontend: http://localhost:5173
- Backend: http://localhost:8011

### `start-backend.ps1`

Purpose:
- Starts the FastAPI backend (Uvicorn)

Typical usage:

```powershell
./start-backend.ps1
```

### `start-frontend.ps1`

Purpose:
- Starts the Vite frontend dev server

Typical usage:

```powershell
./start-frontend.ps1
```

## Command Prompt wrappers

- `start-all.bat`
- `start-backend.bat`
- `start-frontend.bat`

These are convenience wrappers for environments where PowerShell execution policies are restrictive.

## Other scripts

### `setup-interactive.ps1`

Purpose:
- Interactive setup flow (useful when you want prompts instead of defaults)

### `clean.ps1`

Purpose:
- Cleans build artifacts / temporary folders (useful before a fresh bootstrap)

Typical sequence:

```powershell
# Stop running services first
./clean.ps1
./bootstrap.ps1 -RunDiagnostics
./start-all.ps1
```
