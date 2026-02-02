# agentic-restored

This folder contains the **main application source code**.

## Structure

```
agentic-restored/
├── python_backend/     # FastAPI backend (Python 3.11+)
├── e2etraceapp/        # React/Vite frontend (Node 18+)
├── bootstrap.ps1       # Setup dependencies
├── clean.ps1           # Reset/clean artifacts
├── start-all.ps1/.bat  # Start both services
├── start-backend.ps1/.bat
└── start-frontend.ps1/.bat
```

## Quick Start

From this folder:

```powershell
.\bootstrap.ps1      # One-time setup
.\start-all.ps1      # Start both services
```

## Documentation

See the repo root `docs/` folder:
- [Installation](../docs/INSTALLATION.md)
- [Execution Guide](../docs/EXECUTION_GUIDE.md)
- [User Guide](../docs/USER_GUIDE.md)
