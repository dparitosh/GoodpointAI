# Step-by-step execution (local runbook)

This is the shortest reliable path to run GraphTrace locally on Windows.

## 1) Start PostgreSQL

- Make sure Postgres is running.
- Verify your DB connection string in:
  - `agentic-restored/python_backend/.env` (`DATABASE_URL=...`)

## 2) Start the backend (FastAPI)

### Option A (recommended): VS Code task

Run the workspace task:

- **Start Backend Server**

This task runs the backend with dotenv loading enabled (`GRAPH_TRACE_LOAD_DOTENV=true`).

Expected:

- http://localhost:8011/health returns OK
- http://localhost:8011/docs loads Swagger UI

### Option B: script

From `agentic-restored/`:

- `start-backend.ps1` (PowerShell)
- `start-backend.bat` (cmd)

Equivalent manual command:

```powershell
python -m uvicorn --app-dir agentic-restored/python_backend main:app --host 0.0.0.0 --port 8011 --reload
```

## 3) Start the frontend (React/Vite)

### Option A (recommended): VS Code task

Run the workspace task:

- **Start Frontend Development Server**

Equivalent manual command:

```powershell
Push-Location agentic-restored/e2etraceapp
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:

- http://localhost:5173

## 4) First-time verification checklist

1. **Backend health**: open http://localhost:8011/health
2. **API docs**: open http://localhost:8011/docs
3. **UI loads**: open http://localhost:5173
4. **Admin config page loads**:
   - http://localhost:5173/#/admin

If any of the above fails:

- Check backend logs first.
- Confirm Postgres settings in `agentic-restored/python_backend/.env`.

## 5) Typical user flow (smoke)

1. Go to **Migration** wizard:
   - http://localhost:5173/#/migration
2. Walk through Connect → Discovery → Map → Validate → Execute.
3. Visit **Analytics Hub**:
   - http://localhost:5173/#/analytics
4. Export a quality report (JSON/CSV) where available.

## 6) Stop

- Stop the frontend and backend terminals (Ctrl+C), or close the windows started by `start-all.ps1`.
