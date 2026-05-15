# GraphTrace v2.0 Deployment Guide

## Overview

This guide covers deployment of **GraphTrace v2.0** to customer environments. v2.0 includes significant refactoring:
- **New Workflow Orchestration System** - Formal agent/tool framework for data migration
- **Shared Code Modules** - Elimination of code duplication (400+ KB freed)
- **Enhanced Migration Wizard** - 6-step unified migration workflow
- **MCP Client Hardening** - Graceful degradation when agents unavailable

---

## Pre-Deployment Checklist

### For Operators/DevOps Teams

- [ ] Review this deployment guide
- [ ] Backup current PostgreSQL database (see "Backup Your Data")
- [ ] Stop running GraphTrace services
- [ ] Verify PostgreSQL is running and accessible
- [ ] Confirm Python 3.11+ and Node.js 18+ available
- [ ] Have `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY` value (for encrypted config decryption)

### For Development Teams

- [ ] Pull latest code from `main` or release branch
- [ ] Review changelog for breaking changes (none expected in v2.0)
- [ ] Run migration script on staging before production
- [ ] Execute full workflow test (Steps 1-6)
- [ ] Verify Admin Configuration page loads and settings persist

---

## Step 1: Backup Your Data

### PostgreSQL Full Backup (Recommended)

```powershell
# Windows — use full path to pg_dump
$DumpPath = "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe"
$BackupFile = "graphtrace_backup_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"

& $DumpPath -U postgres -h 127.0.0.1 -p 5433 -d graphtrace -Fc -f $BackupFile

Write-Host "Backup saved to: $BackupFile"
```

### Alternative: Application-Level Backup

The migration script automatically creates a backup of:
- Encrypted configurations (database settings, LLM providers, API keys)
- Workflow instance metadata
- Sample data

This is saved in `./backups/TIMESTAMP_v2_0_migration/` directory.

---

## Step 2: Stop Current Services

```powershell
# Stop backend (if running in terminal)
# Press Ctrl+C in the backend terminal

# Stop frontend (if running in terminal)
# Press Ctrl+C in the frontend terminal

# Or use PowerShell to kill processes
Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" } | Stop-Process -Force
```

---

## Step 3: Update Code

### Clone/Pull Latest

```powershell
cd path\to\GoodpointAI

# If you haven't cloned yet
git clone https://github.com/dparitosh/GoodpointAI.git

# If already cloned, pull latest
git checkout main
git pull origin main
```

### Verify Key Files Exist

```powershell
# Check migration script
Test-Path python_backend\scripts\migrate_to_v2_0.py
# Expected: True

# Check new workflow models
Test-Path python_backend\models\workflow_models.py
# Expected: True

# Check agentic router
Test-Path python_backend\graph_api\agentic_router.py
# Expected: True
```

---

## Step 4: Run Migration Script (Pre-Production)

### Preview Changes (Recommended First Step)

```powershell
cd GoodpointAI

# Set environment
$env:GRAPH_TRACE_LOAD_DOTENV = "true"

# Preview what will change
python -m scripts.migrate_to_v2_0 --dry-run -v

# Review output for:
# - New tables to be created
# - Schema columns to be added
# - Indexes to be created
# - Verification results
```

### Execute Migration

```powershell
# Run actual migration (creates backup automatically)
python -m scripts.migrate_to_v2_0 --yes -v

# Expected output:
# ✓ workflow_instances table created
# ✓ PLM schema migrations complete
# ✓ File batch processing schema ensured
# ✓ Migration to v2.0 complete
```

### Handle Migration Failures

If the migration fails:

1. **Check the log file**: `migration_YYYYMMDD_HHMMSS.log`
2. **Review backup location**: `./backups/TIMESTAMP_v2_0_migration/`
3. **Common issues**:
   - PostgreSQL not running → Start PostgreSQL service
   - DATABASE_URL incorrect → Verify in `python_backend/.env`
   - Encryption key changed → See "Decryption Errors" section below

---

## Step 5: Verify Database State

```powershell
# Check workflow_instances table exists
$DumpPath = "C:\Program Files\PostgreSQL\17\bin\psql.exe"

& $DumpPath -U postgres -h 127.0.0.1 -p 5433 -d graphtrace -c `
  "SELECT tablename FROM pg_tables WHERE tablename='workflow_instances';"

# Expected output:
#  tablename
# --------------------
#  workflow_instances

# Check table structure
& $DumpPath -U postgres -h 127.0.0.1 -p 5433 -d graphtrace -c `
  "\d workflow_instances"

# Check row count
& $DumpPath -U postgres -h 127.0.0.1 -p 5433 -d graphtrace -c `
  "SELECT COUNT(*) FROM workflow_instances;"
```

---

## Step 6: Update Environment (if needed)

### New Environment Variables in v2.0

Add to `python_backend/.env` if you want new features:

```dotenv
# Agentic orchestration configuration (optional)
GRAPH_TRACE_AGENTIC_ENABLED=true
GRAPH_TRACE_ORCHESTRATION_MODE=intelligent  # reactive|proactive|intelligent

# MCP (Model Context Protocol) server connection
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8006

# Optional: If encryption key changed, allow reset
# GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true
```

### Configuration That May Need Updates

If customer has custom `.env` values:

```dotenv
# These remain the same as before v2.0:
DATABASE_URL=...
POSTGRES_HOST=...
POSTGRES_PORT=...
POSTGRES_USER=...
POSTGRES_PASSWORD=...

# These are NEW in v2.0 (optional):
GRAPH_TRACE_AGENTIC_ENABLED=true
MCP_SERVER_HOST=127.0.0.1
MCP_SERVER_PORT=8006
```

---

## Step 7: Start Services

### Start Backend

```powershell
cd python_backend

# Activate virtual environment (if using venv)
.\.venv\Scripts\Activate.ps1

# Install/update dependencies
pip install -r requirements.txt

# Start backend
python -m uvicorn main:app --reload --port 8011 --host 0.0.0.0
```

### Start Frontend

```powershell
# In another PowerShell window
cd e2etraceapp

npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### Start MCP Server (Optional but Recommended)

```powershell
# In a third PowerShell window
cd mcp_server

pip install -r requirements.txt
python main.py
```

---

## Step 8: Verify Deployment

### Check Health Endpoint

```powershell
# Should return 200 with service details
curl -s http://localhost:8011/health | ConvertFrom-Json | Format-Table

# Expected response:
# {
#   "status": "ok",
#   "service": "graphtrace-backend",
#   "dependencies": {
#     "postgres": { "ok": true },
#     "neo4j": { "ok": false },  # OK if not configured
#     "mcp": { "ok": true }       # NEW in v2.0
#   }
# }
```

### Access Web UI

```
http://localhost:5173/
# or with hash navigation
http://127.0.0.1:5173/#/admin
```

### Check Admin Configuration Page

1. Navigate to **Admin** (⚙️ icon in left sidebar)
2. Verify all settings load correctly
3. Check that LLM provider, API keys, and connections are visible
4. No errors in browser console (F12 → Console tab)

---

## Step 9: Test Migration Workflow (Critical!)

### Run Full E2E Workflow Test

1. **Navigate to**: `http://localhost:5173/#/migration`
2. **Step 1 - Connect**: 
   - Select source system (e.g., "IMAN22_Teamcenter")
   - Select target system (e.g., "Primary PostgreSQL")
   - Click **Next**
3. **Step 2 - Discovery**:
   - Click **Run Discovery**
   - Wait for discovery to complete
   - Verify file list appears
4. **Step 3 - Map**:
   - Configure field mappings (use defaults if first test)
   - Click **Next**
5. **Step 4 - Validate**:
   - Click **Run Quality Scan**
   - Wait for validation to complete
   - Verify quality score is displayed
6. **Step 5 - Execute**:
   - Click **Execute Migration**
   - Monitor progress bar
   - Wait for completion
7. **Step 6 - Report**:
   - Review migration readiness score
   - Check recommendations
   - Click **Export Report** (if desired)

### Expected Results

- ✅ All steps complete without errors
- ✅ Data appears in progress indicators
- ✅ No red error messages
- ✅ Browser console has no critical errors

---

## Troubleshooting

### Decryption Errors When Starting Backend

**Error message**: `"Cannot decrypt encrypted config with current key"`

**Solution**:

```powershell
# Option A: Set encryption key to match old deployment
# In python_backend/.env:
GRAPH_TRACE_CONFIG_ENCRYPTION_KEY=<original_encryption_key>

# Option B: Reset encrypted config (development only!)
# In python_backend/.env:
GRAPH_TRACE_ALLOW_RESET_ENCRYPTED_CONFIG=true

# Then run:
python -m scripts.init_db_schema

# Then remove the flag from .env
```

### Migration Script Fails with "Database connectivity failed"

**Cause**: PostgreSQL not running or DATABASE_URL incorrect

**Solution**:

```powershell
# 1. Check PostgreSQL is running
Get-Service *postgres*

# 2. Verify DATABASE_URL in python_backend/.env
# Should be: postgresql://postgres:PASSWORD@127.0.0.1:PORT/graphtrace

# 3. Test connectivity
$psqlPath = "C:\Program Files\PostgreSQL\17\bin\psql.exe"
& $psqlPath -U postgres -h 127.0.0.1 -p 5433 -c "SELECT 1"

# 4. If connection fails, check:
# - Is postgres user password correct?
# - Is port correct (5432 or 5433)?
# - Is graphtrace database created?
```

### Workflow Step Fails with "Agent Unavailable"

**Cause**: MCP server not running or agent service down

**Solution**:

```powershell
# 1. Start MCP server (if not running)
cd mcp_server
python main.py

# 2. Check if specific agent is available
curl -s http://localhost:8011/api/agentic/agents | ConvertFrom-Json | Format-Table

# 3. Check MCP server logs for errors
# Look in mcp_server logs directory

# 4. Workflow will continue with local fallback (graceful degradation)
# Data migration will proceed without MCP enhancements
```

### Frontend Shows Blank Pages

**Cause**: Frontend dev server not running or API calls failing

**Solution**:

```powershell
# 1. Check frontend is running on port 5173
netstat -ano | Select-String "LISTENING" | Select-String "5173"

# 2. Check browser console for errors (F12 → Console)
# Common error: "Cannot GET /api/agentic/status"

# 3. Check backend is running on port 8011
curl -s http://localhost:8011/health

# 4. If both services running but errors persist:
# - Clear browser cache (Ctrl+Shift+Delete)
# - Hard refresh (Ctrl+Shift+R)
# - Check CORS settings in python_backend/.env
```

---

## Post-Deployment Monitoring

### Check Logs

```powershell
# Backend logs (in terminal where backend is running)
# Look for:
# - Any ERROR level messages
# - Any MCP connection warnings
# - Database migration confirmations

# Migration log
Get-Content migration_*.log | Select-Object -Last 50  # Last 50 lines

# Frontend logs (browser console, F12)
# Look for:
# - Network errors (red)
# - API call failures
```

### Monitor Performance

**New in v2.0**: Agentic orchestration adds overhead during first run

- **Expected initial latency**: +500-1000ms per discovery/profiling step
- **After warmup**: Latency normalizes
- **If consistently slow**: 
  - Check MCP server is running: `curl http://localhost:8006/health`
  - Check database query performance: `ANALYZE workflow_instances`
  - Review PostgreSQL logs

---

## Rollback Procedure (If Needed)

### If v2.0 Doesn't Work

```powershell
# 1. Stop services
Get-Process | Where-Object { $_.ProcessName -like "*python*" -or $_.ProcessName -like "*node*" } | Stop-Process -Force

# 2. Restore database from backup
$BackupFile = "graphtrace_backup_20240515.sql"  # From Step 1
$RestorePath = "C:\Program Files\PostgreSQL\17\bin\psql.exe"

& $RestorePath -U postgres -h 127.0.0.1 -p 5433 -d graphtrace < $BackupFile

# 3. Checkout previous version
git checkout v1.9  # or your previous stable version

# 4. Restart services with previous code
```

---

## Code Refactoring Changes (v2.0)

### What Changed (Developer-Facing)

These changes won't affect deployment but may affect custom extensions:

1. **Shared API Response Models**: `api_response_models.py`
   - Replaces 45+ hardcoded response envelope definitions
   - Import: `from models.api_response_models import SuccessResponse`

2. **Shared Validation Functions**: `config_validators.py`
   - Centralizes validation logic
   - Import: `from services.config_validators import validate_required_fields`

3. **Shared CSS Theme**: `src/styles/_theme.css`
   - 50+ CSS custom properties for colors, spacing, typography
   - Import: `@import url('./theme.css')`

4. **MCP Client Hardening**: `services/mcp_client.py`
   - Added 5-second health check caching
   - Graceful degradation instead of exceptions
   - Reduced timeout from 10s to 2s

### What Didn't Change

- Database schema (except new workflow_instances table)
- API endpoint signatures (backward compatible)
- .env configuration keys (only new optional keys added)
- Frontend routes and navigation

---

## Customer Support Contacts

**For technical issues**:
- Check `migration_*.log` file (in root directory after migration)
- Review logs in `./logs/` directory
- Share backend output (Ctrl+C in backend terminal may show errors)

**For backup recovery**:
- Full database backup location: Customer's backup directory
- Application-level backups: `./backups/TIMESTAMP_v2_0_migration/`

---

## Verification Checklist (Final)

- [ ] Database migration completed successfully
- [ ] Backend starts without errors
- [ ] Frontend loads at http://localhost:5173
- [ ] Health endpoint returns 200: http://localhost:8011/health
- [ ] Admin page loads and shows no red errors
- [ ] Full workflow test (Steps 1-6) completes
- [ ] No ERROR level messages in backend logs
- [ ] Encrypted configuration is accessible
- [ ] MCP server running (if enabled in env)

---

**Deployment Date**: _____________  
**Deployed By**: _____________  
**Notes**: _____________

---

For more details, see:
- [INSTALLATION.md](./INSTALLATION.md) - Initial setup guide
- [AGENTIC_ORCHESTRATION_ARCHITECTURE.md](./AGENTIC_ORCHESTRATION_ARCHITECTURE.md) - v2.0 architecture
- [README.md](./README.md) - Overview and features
