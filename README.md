# GoodpointAI (GraphTrace)

GraphTrace is a local-first, full-stack application for **data lineage**, **PLM migration workflows**, and **analytics**.

## Start here

- 📦 **Installation**: [`docs/INSTALLATION.md`](docs/INSTALLATION.md)
- ▶️ **Step-by-step execution (runbook)**: [`docs/EXECUTION_GUIDE.md`](docs/EXECUTION_GUIDE.md)
- 👤 **End user guide**: [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)

## What you run locally

- Frontend (Vite/React): http://localhost:5173
- Backend (FastAPI): http://localhost:8011
- OpenAPI docs: http://localhost:8011/docs

## Persistence

This project uses **PostgreSQL** as the only supported persistence store for application data (reports, workflow state, configs when enabled). SQLite is **not supported**.
