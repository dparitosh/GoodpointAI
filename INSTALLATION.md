# GraphTrace Installation & Setup Guide

## Prerequisites

- **Python 3.8+** (Tested with 3.12.1)
- **Node.js 18+** (Tested with Node 20+)
- **npm 9+**
- **Neo4j Database** (Cloud or local instance)
- **PostgreSQL** (required for the app database)
- **OpenSearch** (optional, for vector/search features)
- **Apache HTTP Server** (optional, for production reverse-proxy + serving the built frontend)
- **Git** (optional but recommended)

## Quick Start

### 1. Clone or Download Repository
```powershell
git clone <repository-url>
cd graphTrace\agentic-restored
```

### 2. Run System Diagnostics
Before installation, check system compatibility:
```powershell
./diagnostics/windows/diagnose-all.ps1
```

### 3. Run Installation Script
On Windows, the recommended bootstrap is:

```powershell
./bootstrap.ps1 -RunDiagnostics
```

### 4. Configuration (DB-seeded, UI-managed)

GraphTrace seeds DB-backed configuration on first run and the UI is the recommended way to configure integrations:

- Open the UI: `http://localhost:5173/#/data-config`
- Configure Neo4j + OpenSearch there

Bootstrap secret required for encrypted config:

```env
GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=your-secret
```

Legacy `.env` remains optional for local development.

### 5. Start Services
```powershell
./start-all.ps1
```

Or using Command Prompt:

```cmd
start-all.bat
```

### 6. Access Application
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8011
- **API Docs:** http://localhost:8011/docs

### Notes on persistence (important)

- **Postgres is required** for DB-backed features like persisted reports (`/api/reports`). If the DB is unreachable, the API returns **HTTP 503** with a clear message.
- **Data Mapping rules/templates** are currently stored as local JSON files created at runtime:
	- `python_backend/mapping_rules.json`
	- `python_backend/mapping_templates.json`
	These files are intentionally **ignored by git** (local dev artifact).
- **Mapping execution** (`/api/data-mapping/rules/{id}/execute`) intentionally returns **HTTP 503** unless source/target connectors + an execution engine are configured.

## Manual Installation

### Backend Setup
```powershell
cd .\python_backend

# Create virtual environment
python -m venv venv

# Activate virtual environment (PowerShell)
.\venv\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirement.txt

# Create DB schema + seed default config
# NOTE: Requires DATABASE_URL (Postgres) or POSTGRES_* env vars.
python -m scripts.init_db_schema

# Create .env file (optional)
Copy-Item .\.env.example .\.env -Force

# Start backend
python -m uvicorn --app-dir . main:app --host 0.0.0.0 --port 8011 --reload
```

### Frontend Setup
```powershell
cd .\e2etraceapp

# Install dependencies
npm install

# (Optional) Create .env
Set-Content -Path .\.env -Value "VITE_API_BASE_URL=http://localhost:8011"

# Start frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

## Directory Structure

```
graphTrace/
├── python_backend/          # FastAPI backend
│   ├── main.py             # Entry point
│   ├── requirement.txt     # Python dependencies
│   ├── .env                # Environment variables (create this)
│   ├── core/               # Core configuration
│   ├── graph_api/          # API routers
│   ├── models/             # Pydantic models
│   └── services/           # Business logic
├── e2etraceapp/            # React frontend
│   ├── package.json        # npm dependencies
│   ├── vite.config.js      # Vite configuration
│   ├── index.html          # Entry HTML
│   └── src/                # Source code
├── logs/                   # Application logs
├── bootstrap.ps1           # Bootstrap (Windows)
├── start-all.ps1           # Start all services (Windows)
├── start-all.bat           # Start all services (Windows, cmd)
└── diagnostics/            # Windows diagnostics scripts
```

## Scripts Reference
### DB schema + seed

```bash
cd python_backend
python -m scripts.init_db_schema
```

### DB/config diagnostics

```bash
cd python_backend
python -m scripts.diagnose_db_config
```

### Windows scripts

- Diagnostics: `./diagnostics/windows/diagnose-all.ps1`
- Bootstrap (recommended): `./bootstrap.ps1 -RunDiagnostics`
- Start all: `./start-all.ps1` or `start-all.bat`
- Start backend: `./start-backend.ps1` or `start-backend.bat`
- Start frontend: `./start-frontend.ps1` or `start-frontend.bat`

## Common Issues & Solutions

### Issue: Port Already in Use
```powershell
# Stop the process owning port 8011
$pid = (Get-NetTCPConnection -LocalPort 8011 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
if ($pid) { Stop-Process -Id $pid -Force }

# Stop the process owning port 5173
$pid = (Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess)
if ($pid) { Stop-Process -Id $pid -Force }
```

### Issue: Python packages not found
```powershell
# Make sure virtual environment is activated
cd .\python_backend
.\venv\Scripts\Activate.ps1

# Reinstall packages
pip install -r requirement.txt
```

### Issue: npm install fails
```bash
# Clear npm cache
cd e2etraceapp
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### Issue: Neo4j connection fails
Check:
1. Neo4j instance is running
2. Credentials in `.env` are correct
3. Firewall allows connection
4. URI format is correct (neo4j+s:// or bolt://)

### Issue: CORS errors
Update `ALLOWED_ORIGINS` in `python_backend/.env`:
```env
ALLOWED_ORIGINS=http://localhost:5173,http://localhost:5174,http://localhost:3000
```

## Development

### Backend Hot Reload
Backend uses uvicorn with `--reload` flag for automatic reloading.

### Frontend Hot Module Replacement
Vite provides instant HMR - changes appear immediately.

### Viewing Logs
```powershell
# Backend logs
Get-Content -Path .\logs\backend.log -Wait

# Frontend logs
Get-Content -Path .\logs\frontend.log -Wait
```

## Testing

### Run Backend Tests
```powershell
cd .\python_backend
.\venv\Scripts\Activate.ps1
pytest tests/
```

### Run Frontend Tests
```powershell
cd .\e2etraceapp
npm test
```

## Production Deployment

### Backend
1. Set `ENVIRONMENT=production` in .env
2. Use production ASGI server (gunicorn + uvicorn)
3. Set proper `ALLOWED_ORIGINS`
4. Enable HTTPS
5. Use environment variables for secrets

### Frontend
```powershell
cd .\e2etraceapp
npm run build
```

Serve `e2etraceapp/dist/` using a Windows-friendly static server or Apache (optional).

### Apache (optional)
See `apache/README.md` and `apache/graphtrace-httpd.conf` for a sample configuration.

## Known Issues

1. **requirement.txt typo**: File is named `requirement.txt` (should be `requirements.txt`) - this is intentional for backward compatibility
2. **Windows scripts**: Use `.bat` or `.ps1` versions for Windows
3. **Port conflicts**: Default ports can be changed in configuration

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Run `./diagnostics/windows/diagnose-all.ps1` for system validation
3. Review this README for common issues
4. Check Neo4j connectivity separately

## Version Information

- **Backend Framework**: FastAPI 0.115.0
- **Frontend Framework**: React 19.1.0
- **Build Tool**: Vite 6.3.5
- **Database**: Neo4j 5.25.0
- **Node Version**: 18+ required
- **Python Version**: 3.8+ required

## License

[Add your license information here]
