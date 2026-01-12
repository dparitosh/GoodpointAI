# GraphTrace Quick Setup Guide

**One document to rule them all.** Follow these steps in order.

---

## Prerequisites

| Software | Version | Check Command |
|----------|---------|---------------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | `node --version` |
| PostgreSQL | 14+ | `psql --version` |

---

## Step 1: Install PostgreSQL (If Not Installed)

### Windows (easiest)
1. Download from https://www.postgresql.org/download/windows/
2. Run installer, use these settings:
   - **Port**: `5432` (default)
   - **Password**: Set a password (e.g., `postgres123`) — **WRITE THIS DOWN**
   - **Locale**: Default
3. Complete installation

### Verify PostgreSQL is running
```powershell
# Check if PostgreSQL service is running
Get-Service -Name postgresql*
```

If not running:
```powershell
Start-Service postgresql-x64-16  # or your version number
```

---

## Step 2: Create the Database

Open PowerShell and run:

```powershell
# Connect to PostgreSQL (enter your password when prompted)
psql -U postgres -h localhost

# In the psql shell, create the database:
CREATE DATABASE graphtrace;
\q
```

**Alternative** (if psql is not in PATH):
```powershell
# Find psql location (usually here)
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost
```

---

## Step 3: Create the .env File

Navigate to the backend folder and create your configuration:

```powershell
cd d:\Download\graphTrace-feature-xstate-agentic-integration\agentic-restored\python_backend
```

Create a new file called `.env` with this **minimal** content:

```env
# PostgreSQL - REQUIRED (update password to match your PostgreSQL password)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD_HERE

# Neo4j - OPTIONAL (can configure later in UI)
# NEO4J_URI=neo4j://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=your_neo4j_password
# NEO4J_DATABASE=neo4j
```

**⚠️ IMPORTANT:** Replace `YOUR_POSTGRES_PASSWORD_HERE` with the password you set during PostgreSQL installation.

### Quick .env Creation (PowerShell)
```powershell
@"
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=YOUR_POSTGRES_PASSWORD_HERE
"@ | Out-File -FilePath ".env" -Encoding UTF8

# Now edit the file to set your actual password:
notepad .env
```

---

## Step 4: Run Bootstrap

From the `agentic-restored` folder:

```powershell
cd d:\Download\graphTrace-feature-xstate-agentic-integration\agentic-restored

# Run the bootstrap script
.\bootstrap.ps1
```

This will:
1. Create Python virtual environment
2. Install Python dependencies
3. Generate encryption key
4. Initialize database schema
5. Install frontend dependencies

**Expected output:**
```
GraphTrace bootstrap (Windows)
[1/3] Backend: venv + deps + DB schema + seed
...
[2/3] Frontend: npm install
...
Bootstrap complete.
Next: .\start-all.ps1
```

---

## Step 5: Start the Application

```powershell
.\start-all.ps1
```

This opens two new PowerShell windows:
- **Backend**: http://localhost:8011 (API docs at http://localhost:8011/docs)
- **Frontend**: http://localhost:5173

---

## Troubleshooting

### Problem: "password authentication failed"

**Cause:** PostgreSQL password in `.env` doesn't match.

**Fix:**
1. Open `python_backend\.env`
2. Update `POSTGRES_PASSWORD=` with your actual PostgreSQL password
3. Restart the backend

### Problem: "database 'graphtrace' does not exist"

**Fix:**
```powershell
psql -U postgres -h localhost -c "CREATE DATABASE graphtrace;"
```

### Problem: "psql is not recognized"

**Fix:** Add PostgreSQL bin to PATH:
```powershell
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
# Then retry the psql command
```

Or use full path:
```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -h localhost
```

### Problem: "connection refused" on port 5432

**Cause:** PostgreSQL service not running.

**Fix:**
```powershell
# List PostgreSQL services
Get-Service -Name postgresql*

# Start it (replace with your version)
Start-Service postgresql-x64-16
```

### Problem: Script execution disabled

**Fix:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Problem: "cryptography" module errors

**Fix:** The bootstrap handles this, but if needed:
```powershell
cd python_backend
.\venv\Scripts\Activate.ps1
pip install cryptography
```

---

## Reset Everything (Start Fresh)

If something is broken and you want to start over:

```powershell
cd d:\Download\graphTrace-feature-xstate-agentic-integration\agentic-restored

# Remove virtual environment
Remove-Item -Recurse -Force python_backend\venv -ErrorAction SilentlyContinue

# Remove node modules
Remove-Item -Recurse -Force e2etraceapp\node_modules -ErrorAction SilentlyContinue

# Remove encryption key (will regenerate)
Remove-Item python_backend\.graphtrace.encryption_key -ErrorAction SilentlyContinue

# Drop and recreate database (CAUTION: loses all data)
psql -U postgres -h localhost -c "DROP DATABASE IF EXISTS graphtrace;"
psql -U postgres -h localhost -c "CREATE DATABASE graphtrace;"

# Run bootstrap again
.\bootstrap.ps1
```

---

## Minimal .env Template

Copy this to `python_backend\.env` and fill in your password:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=
```

---

## Next Steps (Optional)

After basic setup is working:

1. **Neo4j Integration**: Add Neo4j credentials to `.env` or configure via the UI
2. **OpenSearch**: For vector search features
3. **LLM Integration**: Add OpenAI/Anthropic API keys for AI features

All optional integrations can be configured later through the application UI at http://localhost:5173 → Settings.

---

## Quick Reference

| Action | Command |
|--------|---------|
| Start everything | `.\start-all.ps1` |
| Start backend only | `.\start-backend.ps1` |
| Start frontend only | `.\start-frontend.ps1` |
| Run full setup | `.\bootstrap.ps1` |
| View API docs | http://localhost:8011/docs |
| Open app | http://localhost:5173 |
