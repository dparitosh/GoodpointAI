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
```bash
git clone <repository-url>
cd graphTrace
```

### 2. Run System Diagnostics
Before installation, check system compatibility:
```bash
chmod +x diagnostics.sh
./diagnostics.sh
```

On Windows, use:

```powershell
./diagnostics/windows/diagnose-all.ps1
```

### 3. Run Installation Script
Install all dependencies:
```bash
chmod +x install.sh
./install.sh
```

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
```bash
chmod +x start-all.sh
./start-all.sh
```

### 6. Access Application
- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8011
- **API Docs:** http://localhost:8011/docs

## Manual Installation

### Backend Setup
```bash
cd python_backend

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirement.txt

# Create DB schema + seed default config
# NOTE: Requires DATABASE_URL (Postgres) or POSTGRES_* env vars.
python -m scripts.init_db_schema

# Create .env file
cp .env.example .env
# Edit .env with your credentials

# Start backend
python main.py
```

### Frontend Setup
```bash
cd e2etraceapp

# Install dependencies
npm install

# (Optional) Create .env
echo "VITE_API_BASE_URL=http://localhost:8011" > .env

# Start frontend
npm run dev
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
├── diagnostics.sh          # System validation script
├── install.sh              # Installation script
├── start-all.sh            # Start all services
└── stop-all.sh             # Stop all services
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

### diagnostics.sh
Validates system prerequisites and configuration:
- Checks Python, Node.js, npm versions
- Verifies required files exist
- Tests port availability
- Validates environment configuration
- Checks network connectivity

```bash
./diagnostics.sh
```

### install.sh
Installs all dependencies:
- Creates Python virtual environment
- Installs Python packages
- Installs npm packages
- Creates template .env files

```bash
./install.sh
```

### start-all.sh
Starts both backend and frontend:
- Activates Python venv
- Starts FastAPI on port 8000
- Starts Vite dev server on port 5173
- Logs to `logs/` directory

```bash
./start-all.sh
```

### stop-all.sh
Stops all running services:
```bash
./stop-all.sh
```

## Common Issues & Solutions

### Issue: Port Already in Use
```bash
# Check what's using the port
lsof -i :8011  # Backend
lsof -i :5173  # Frontend

# Kill the process
kill -9 <PID>
```

### Issue: Python packages not found
```bash
# Make sure virtual environment is activated
cd python_backend
source venv/bin/activate

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
```bash
# Backend logs
tail -f logs/backend.log

# Frontend logs
tail -f logs/frontend.log
```

## Testing

### Run Backend Tests
```bash
cd python_backend
source venv/bin/activate
pytest tests/
```

### Run Frontend Tests
```bash
cd e2etraceapp
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
```bash
cd e2etraceapp
npm run build
# Serve dist/ folder with nginx/apache
```

### Apache (optional)
See `apache/README.md` and `apache/graphtrace-httpd.conf` for a sample configuration.

## Known Issues

1. **requirement.txt typo**: File is named `requirement.txt` (should be `requirements.txt`) - this is intentional for backward compatibility
2. **Windows scripts**: Use `.bat` or `.ps1` versions for Windows
3. **Port conflicts**: Default ports can be changed in configuration

## Support

For issues or questions:
1. Check logs in `logs/` directory
2. Run `./diagnostics.sh` for system validation
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
