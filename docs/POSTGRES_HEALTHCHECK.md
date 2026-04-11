# PostgreSQL Health Check Guide

## Quick Start

Run a fast Postgres connectivity and schema check **without starting the full stack**:

```bash
python scripts/check_postgres.py
```

**Expected output when healthy:**
```
INFO: 📋 Connection: postgres@127.0.0.1:5433/graphtrace
INFO: Testing PostgreSQL connection...
INFO: ✅ Connection OK
INFO: ✅ Schema initialized (20 tables)
✅ PostgreSQL is healthy and ready!
```

## Command Options

### Basic Check
```bash
python scripts/check_postgres.py
```
- ✅ Tests connection to Postgres
- ✅ Verifies schema is initialized
- ⚠️ Shows how-to if schema is missing
- Exit code: **0 = healthy**, **1 = error**

### Detailed Check (Show Version)
```bash
python scripts/check_postgres.py --detailed
```
- Adds PostgreSQL version info
- Example: `PostgreSQL 15.2 (Ubuntu 15.2-1.pgdg...)`

### Auto-Initialize Schema
```bash
python scripts/check_postgres.py --init-schema
```
- Automatically runs `scripts/init_db_schema.py` if schema is missing
- Safer than manual init (handles dependencies automatically)
- Requires write access to database

## Prerequisites

### 1. PostgreSQL Server Running
Verify Postgres is accessible:
```powershell
psql -U postgres -h 127.0.0.1 -p 5433 -d graphtrace
# Or check connection: psql -c "SELECT version()"
```

### 2. Connection Configuration in `.env`
Located at: `python_backend/.env`

Required setting:
```env
DATABASE_URL=postgresql://postgres:your_password@127.0.0.1:5433/graphtrace
```

**Copy from template if missing:**
```bash
cp python_backend/.env.example python_backend/.env
# Then edit .env with actual Postgres credentials
```

### 3. Python Packages Installed
Ensure psycopg (Postgres driver) is installed:
```bash
pip install 'psycopg[binary]'
```

Or install all backend requirements:
```bash
pip install -r python_backend/requirements.txt
```

## Troubleshooting

### Error: "DATABASE_URL not set"
**Cause:** `.env` file not found or not loaded  
**Fix:**
```bash
cp python_backend/.env.example python_backend/.env
# Edit with actual credentials
```

### Error: "psycopg3 not installed"
**Cause:** Postgres driver missing  
**Fix:**
```bash
pip install 'psycopg[binary]'
```

### Error: "Connection refused" on port 5433
**Cause:** Postgres server not running OR different port  
**Fix:**
- Verify Postgres service is running: `pg_isready -h 127.0.0.1 -p 5433`
- Check actual port in `python_backend/.env` (`DATABASE_URL`)
- Default port is often `5432`, not `5433` — adjust config if needed

**Windows (via PowerShell):**
```powershell
# Check if Postgres service is running
Get-Service -Name postgresql* | Select-Object Status, Name
# Start Postgres (adjust service name if needed)
Start-Service -Name "postgresql-x64-15"
```

### Error: "Authentication failed"
**Cause:** Wrong username/password in `DATABASE_URL`  
**Fix:**
```bash
# Test manually with your credentials
psql -U postgres -h 127.0.0.1 -p 5433 -d graphtrace -c "SELECT 1"
# Update .env with correct credentials
```

### Error: "Schema NOT initialized"
**Cause:** Database exists but tables not created  
**Fix (auto):**
```bash
python scripts/check_postgres.py --init-schema
```

**Fix (manual):**
```bash
cd python_backend
python scripts/init_db_schema.py --initialize
```

### Error: "Relation 'data_source' does not exist"
**Same as above** — schema not initialized. Run init script.

## Integration with Deployment Scripts

### Before Starting Full Stack
```bash
# 1. Check Postgres health
python scripts/check_postgres.py

# 2. All OK? Start services
./graphtrace.ps1 -Start
```

### CI/CD Pipeline
```bash
# In GitHub Actions / Azure Pipelines:
- name: Check Postgres Connectivity
  run: python scripts/check_postgres.py --detailed
  continue-on-error: false  # Fail pipeline if Postgres not healthy
```

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| `0` | ✅ Postgres healthy, schema initialized | Safe to start full stack |
| `1` | ❌ Connection failed or schema missing | Fix errors (see Troubleshooting) |

## Quick Postgres Setup Reminder

### Windows (using PostgreSQL installer)
1. **Install PostgreSQL** (https://www.postgresql.org/download/windows/)
   - Remember password for `postgres` user
   - Keep port as `5432` (or if changed, update `.env`)

2. **Create database**
   ```bash
   psql -U postgres -c "CREATE DATABASE graphtrace"
   ```

3. **Update `.env`**
   ```env
   DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/graphtrace
   POSTGRES_HOST=127.0.0.1
   POSTGRES_PORT=5432
   POSTGRES_PASSWORD=YOUR_PASSWORD
   ```

4. **Verify**
   ```bash
   python scripts/check_postgres.py
   ```

### Docker (Quick Test)
```bash
# Start a test Postgres container
docker run --name graphtrace-db \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=graphtrace \
  -p 5433:5432 \
  -d postgres:15

# Update .env
# DATABASE_URL=postgresql://postgres:testpass@127.0.0.1:5433/graphtrace

# Check health
python scripts/check_postgres.py
```

## See Also
- [Installation Guide](INSTALLATION.md) — Full setup with Postgres
- [Schema Initialization](../python_backend/scripts/init_db_schema.py) — Manual DB setup
- [Diagnostics](../scripts/diagnostics.py) — System-wide preflight checks
