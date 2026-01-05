# GraphTrace - Quick Reference (Windows)

## Quick Start (PowerShell)

```powershell
# 1) Validate system
./diagnostics/windows/diagnose-all.ps1

# 2) Bootstrap (creates venv, installs deps, seeds DB config)
./bootstrap.ps1 -RunDiagnostics

# 3) Start backend + frontend
./start-all.ps1
```

Then open: http://localhost:5173

## Key Workflows (Business Users)

- **Configure integrations**: `http://localhost:5173/#/data-config` (Neo4j/OpenSearch/Postgres-backed config)
- **Create mappings + transformations**: `http://localhost:5173/#/data-mapping` (save draft, validate, deploy)
- **Insights + reports**: `http://localhost:5173/#/reporting` (download JSON/CSV; open spreadsheet)
- **Spreadsheet**: `http://localhost:5173/#/spreadsheet` (import/export xlsx/csv/json/xml, charting)

## Required for Reports

Persisted reports (`/api/reports`) require Postgres to be reachable via `DATABASE_URL` or `POSTGRES_*` env vars. If Postgres is unavailable, the API returns **HTTP 503**.

## Quick Start (Command Prompt)

```cmd
start-all.bat
```

## Individual Service Control

### Backend Only (PowerShell)

```powershell
./start-backend.ps1
```

### Frontend Only (PowerShell)

```powershell
./start-frontend.ps1
```

## Access Points

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8011 |
| API Docs | http://localhost:8011/docs |
| Redoc | http://localhost:8011/redoc |

## Configuration

- Recommended: configure integrations from the UI at `http://localhost:5173/#/data-config`.
- Optional local dev env:
	- `python_backend/.env` (Neo4j and secrets)
	- `e2etraceapp/.env` (only if you want to override the API URL)

## Quick Troubleshooting (Windows)

### Port Already in Use

```powershell
# Stop the process owning port 8011
$pid = (Get-NetTCPConnection -LocalPort 8011 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
if ($pid) { Stop-Process -Id $pid -Force }

# Stop the process owning port 5173
$pid = (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
if ($pid) { Stop-Process -Id $pid -Force }
```

### Backend Won't Start

```powershell
cd .\python_backend
python -m pip install -r requirement.txt
```

### Frontend Won't Start

```powershell
cd .\e2etraceapp
Remove-Item -Recurse -Force .\node_modules -ErrorAction SilentlyContinue
Remove-Item -Force .\package-lock.json -ErrorAction SilentlyContinue
npm install
```

## View Logs (Windows)

```powershell
# Backend
Get-Content -Path .\logs\backend.log -Wait

# Frontend
Get-Content -Path .\logs\frontend.log -Wait
```

## Stop Services

- If you started via `start-all.ps1` / `start-all.bat`: close the spawned terminal windows, or press Ctrl+C in each.

## Full Documentation

- Windows setup: `README-WINDOWS.md`
- Installation guide: `INSTALLATION.md`
