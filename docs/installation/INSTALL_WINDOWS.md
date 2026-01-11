# Installation (Windows)

This is the recommended Windows install/run flow using the repo scripts.

## 1) Run diagnostics (recommended)

```powershell
./diagnostics/windows/diagnose-all.ps1
```

## 2) Bootstrap (recommended)

Bootstrap creates a Python venv, installs backend deps, seeds DB schema/config, and installs frontend deps.

```powershell
./bootstrap.ps1 -RunDiagnostics
```

Notes:
- GraphTrace uses DB-backed encrypted configuration. The bootstrap generates a session key and also saves a local key file at `python_backend/.graphtrace.encryption_key`.
- Postgres must be reachable for DB-backed features.

## 3) Start the app

```powershell
./start-all.ps1
```

Then open:
- Frontend: http://localhost:5173
- Backend: http://localhost:8011
- API docs: http://localhost:8011/docs

## Datasource seeding checklist (Postgres / Neo4j / OpenSearch)

### Postgres (required)

What you get automatically:
- `./bootstrap.ps1 -RunDiagnostics` runs `python -m scripts.init_db_schema`
	- Ensures the DB schema exists
	- Seeds default encrypted config keys (best-effort) via `scripts.seed_db_config`

Manual run (only if needed):

```powershell
Push-Location .\python_backend
./venv/Scripts/Activate.ps1
python -m scripts.init_db_schema
Pop-Location
```

### Neo4j (optional)

Recommended setup:
- Configure connection via UI: http://localhost:5173/#/admin

Optional fixture/schema seeding:
- `python -m scripts.seed_unstructured_workflows` can create Neo4j constraints/indexes
- Requires `NEO4J_PASSWORD` (and optionally `NEO4J_URI`, `NEO4J_USER`)

### OpenSearch (optional)

Recommended setup:
- Configure connection via UI: http://localhost:5173/#/admin

Optional fixture/index seeding:
- `python -m scripts.seed_unstructured_workflows` can create indices and index demo documents
- Uses `OPENSEARCH_URL` (default `http://localhost:9200`)

### Postgres “supporting configs” (optional)

If you want default admin entries and pipeline templates pre-populated:

```powershell
Push-Location .\python_backend
./venv/Scripts/Activate.ps1
python -m scripts.seed_admin_configs
python -m scripts.seed_pipeline_configs
Pop-Location
```

See also: `docs/installation/SCRIPTS_REFERENCE.md` for details and env vars.

## 4) Configure integrations

Use the UI (recommended):
- Admin / configuration: http://localhost:5173/#/admin

## 5) Optional smoke verification

For the analytics features across datasources, run:

```powershell
cd .\e2etraceapp
npm run smoke:analytics
```

## Start/stop individual services

Backend:

```powershell
./start-backend.ps1
```

Frontend:

```powershell
./start-frontend.ps1
```

Stop:
- If started via `start-all.ps1`, close the spawned PowerShell windows (or Ctrl+C inside each).

## Reset (clean venv/caches)

If you need a clean rebuild (recommended after dependency changes or when troubleshooting):

1. Stop services:
	- Close the `start-all.ps1` / `start-backend.ps1` / `start-frontend.ps1` windows, or press Ctrl+C in each.
2. Clean repo artifacts:

```powershell
./clean.ps1
```

3. Re-bootstrap:

```powershell
./bootstrap.ps1 -RunDiagnostics
```

4. Start again:

```powershell
./start-all.ps1
```
