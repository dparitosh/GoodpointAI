# GoodpointAI (GraphTrace)

GraphTrace is a local-first, full-stack application for **data lineage**, **PLM migration workflows**, and **analytics**.

## Quick Start

### Prerequisites
- **Python 3.11+** (recommended: 3.12)
- **Node.js 18+** (recommended: 20)
- **PostgreSQL 14+** (required for persistence)

### One-command Bootstrap
```powershell
.\bootstrap.ps1
```
This creates virtual environments, installs dependencies, and initializes the database schema.

### Start Everything
```powershell
.\start-all.ps1
```
Or use the VS Code task: **Start Full Stack (Frontend + Backend)**

## Documentation

- 📦 **Installation**: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- ▶️ **Execution Guide**: [docs/EXECUTION_GUIDE.md](docs/EXECUTION_GUIDE.md)
- 👤 **User Guide**: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)

## Access Points (Local Development)

| Service | URL |
|---------|-----|
| Frontend (UI) | http://localhost:5173 |
| Backend API | http://localhost:8011 |
| API Docs (Swagger) | http://localhost:8011/docs |
| Health Check | http://localhost:8011/health |

## Project Structure

```
GoodpointAI/
├── agentic-restored/          # Main application source
│   ├── python_backend/        # FastAPI backend
│   └── e2etraceapp/           # React/Vite frontend
├── docs/                      # Documentation
├── bootstrap.ps1              # One-time setup
├── start-all.ps1/.bat         # Start both services
├── start-backend.ps1/.bat     # Start backend only
└── start-frontend.ps1/.bat    # Start frontend only
```

## Persistence

This project uses **PostgreSQL** as the only supported persistence store.

1. Copy the example config:
   ```powershell
   copy agentic-restored\python_backend\.env.example agentic-restored\python_backend\.env
   ```

2. Edit `agentic-restored/python_backend/.env` and set the connection:

```dotenv
DATABASE_URL="postgresql://postgres:password@127.0.0.1:5432/graphtrace"
```
