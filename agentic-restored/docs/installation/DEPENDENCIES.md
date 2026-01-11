# Dependencies (Windows)

This page lists the **software and services** GraphTrace expects.

## Required software

- **Python 3.10+** (tested with Python 3.12)
- **Node.js 18+** (tested with Node 20+)
- **npm** (bundled with Node)

Optional but recommended:
- **Git** (for cloning/updating the repository)

## Required services

- **PostgreSQL** (required for DB-backed features such as persisted reports)
  - Configure via `DATABASE_URL` or `POSTGRES_*` env vars.

## Optional services

- **Neo4j** (graph/lineage integrations)
- **OpenSearch** (search/vector features)
- **Apache HTTP Server** (optional reverse-proxy + serving the built frontend)

## Default local ports

| Service | Default port |
|---|---:|
| Frontend (Vite dev) | 5173 |
| Backend API (FastAPI) | 8011 |
| Neo4j (Bolt) | 7687 |
| PostgreSQL | 5432 (varies by your setup) |
| OpenSearch | 9200 |

## Quick verification (PowerShell)

```powershell
python --version
node --version
npm --version

# If already running:
Invoke-WebRequest http://localhost:8011/health -UseBasicParsing | Select-Object StatusCode
```
