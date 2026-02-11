# GoodpointAI (GraphTrace)

GraphTrace is a local-first, full-stack application for **data lineage**, **PLM migration workflows**, and **analytics**.

## Quick Start

### Prerequisites
- **Python 3.11+** (recommended: 3.12)
- **Node.js 18+** (recommended: 20)
- **PostgreSQL 14+** (required for persistence)

### One-command Bootstrap
```powershell
.\installation_scripts\bootstrap.ps1
```
This creates virtual environments, installs dependencies, and initializes the database schema.

### Start Everything
```powershell
.\installation_scripts\start-all.ps1
```
Or use the VS Code task: **Start Full Stack (Frontend + Backend)**

## Documentation

- **Installation**: [docs/INSTALLATION.md](docs/INSTALLATION.md) — Single-machine and multi-VM deployment
- **User Guide**: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- **Architecture**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Application Guide**: [docs/APP_GUIDE.md](docs/APP_GUIDE.md)

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
├── python_backend/            # FastAPI backend
├── e2etraceapp/               # React/Vite frontend
├── agent_services/            # MCP-powered AI agents
├── mcp_server/                # MCP coordination server
├── installation_scripts/      # Bootstrap, start, stop scripts
├── docs/                      # Documentation
└── config/                    # Runtime configuration
```

## Persistence

This project uses **PostgreSQL** as the only supported persistence store.

1. Copy the example config:
   ```powershell
   copy python_backend\.env.example python_backend\.env
   ```

2. Edit `python_backend/.env` and set your actual PostgreSQL credentials:

```dotenv
DATABASE_URL="postgresql://postgres:yourpassword@127.0.0.1:5433/graphtrace"
```

> **Important:** Replace `yourpassword` with your actual PostgreSQL password.  
> For multi-VM deployment, see [docs/INSTALLATION.md](docs/INSTALLATION.md#multi-vm-deployment).
