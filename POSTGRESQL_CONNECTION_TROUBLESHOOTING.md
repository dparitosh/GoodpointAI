# PostgreSQL Connection Troubleshooting Guide

## Problem: PostgreSQL Connection Failing (Port 5432 vs 5433)

**Error Symptom:**
```
psycopg.OperationalError: FATAL: password authentication failed for user "postgres"
psycopg.OperationalError: could not translate host name "host" to address
Connection refused on port 5433
```

**Root Cause:** PostgreSQL is running on **port 5432** (standard), but the application is configured to connect to **port 5433** (development port).

---

## Quick Fix

### Option 1: Update DATABASE_URL (Recommended for Single Connection)

```bash
# For Port 5432 (standard PostgreSQL)
export DATABASE_URL="postgresql://postgres:YOUR_PASSWORD@YOUR_HOST:5432/graphtrace"

# Or if using .env file:
# Edit .env and change:
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@YOUR_HOST:5432/graphtrace
```

### Option 2: Use Individual POSTGRES_* Variables (Recommended for Flexibility)

When using individual variables, the application defaults to port 5432 if `POSTGRES_PORT` is not set:

```bash
export POSTGRES_HOST=your-postgres-host
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=graphtrace
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password

# Do NOT set DATABASE_URL (let it default to building from POSTGRES_* vars)
unset DATABASE_URL
```

In `.env` file:
```env
# Remove or comment out DATABASE_URL to use POSTGRES_* variables
# DATABASE_URL=...

POSTGRES_HOST=your-postgres-host
POSTGRES_PORT=5432
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
```

---

## Understanding the Connection Logic

The application follows this priority order:

```python
# Priority 1: Use DATABASE_URL from database_config.sqlalchemy_database_url (highest)
# Priority 2: Use DATABASE_URL environment variable
# Priority 3: Use POSTGRES_* environment variables (defaults to port 5432)
# Priority 4: Hard-coded defaults
```

**Code Reference:** `core/db_session.py` lines 15-33

```python
DATABASE_URL = (
    f"{database_config.sqlalchemy_database_url or ''}"
    or os.getenv("DATABASE_URL", "")
    or _default_postgres_url()  # <- Uses POSTGRES_* vars, defaults to 5432
)
```

---

## Configuration by Environment

### Development (Local)

`.env` file:
```env
GRAPH_TRACE_LOAD_DOTENV=true

# Option A: Using DATABASE_URL (if PostgreSQL on non-standard port)
DATABASE_URL=postgresql://postgres:password@127.0.0.1:5433/graphtrace

# Option B: Using POSTGRES_* variables (if PostgreSQL on standard port 5432)
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

### Docker (Standard Port 5432)

`docker-compose.yml`:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: graphtrace
    ports:
      - "5432:5432"  # Standard PostgreSQL port
    
  api:
    build: .
    environment:
      # Use POSTGRES_* variables (defaults to port 5432)
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DATABASE: graphtrace
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      # DO NOT set DATABASE_URL - let it build from POSTGRES_* vars
```

### Production (Azure/AWS/GCP)

**Azure Database for PostgreSQL:**
```bash
export POSTGRES_HOST=myserver.postgres.database.azure.com
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=graphtrace
export POSTGRES_USER=postgres@myserver
export POSTGRES_PASSWORD=secure_password_here
# Let DATABASE_URL build automatically
```

**AWS RDS PostgreSQL:**
```bash
export POSTGRES_HOST=mydb.c9akciq32.us-east-1.rds.amazonaws.com
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=graphtrace
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=secure_password_here
```

**Google Cloud SQL:**
```bash
export POSTGRES_HOST=10.0.0.2  # Private IP or use Cloud SQL Proxy
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=graphtrace
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=secure_password_here
```

---

## Troubleshooting Steps

### Step 1: Verify PostgreSQL is Running

```bash
# On the PostgreSQL server host
netstat -tuln | grep 5432

# Expected output:
# tcp  0  0 0.0.0.0:5432  0.0.0.0:*  LISTEN
# tcp6 0  0 :::5432       :::*       LISTEN
```

### Step 2: Test PostgreSQL Connectivity

```bash
# Using psql (if installed)
psql -h YOUR_HOST -p 5432 -U postgres -d graphtrace -c "SELECT version();"

# Using Python
python3 << 'EOF'
import psycopg
try:
    conn = psycopg.connect(
        host="YOUR_HOST",
        port=5432,
        user="postgres",
        password="YOUR_PASSWORD",
        dbname="graphtrace"
    )
    print("✓ Connection successful!")
    print(f"✓ Server version: {conn.info.server_version}")
    conn.close()
except Exception as e:
    print(f"✗ Connection failed: {e}")
EOF
```

### Step 3: Check Application Configuration

```bash
# Print active configuration
python3 << 'EOF'
import os
from core.external_config import database_config

print("Current Configuration:")
print(f"  DATABASE_URL env: {os.getenv('DATABASE_URL', 'NOT SET')}")
print(f"  POSTGRES_HOST: {database_config.postgres_host}")
print(f"  POSTGRES_PORT: {database_config.postgres_port}")
print(f"  POSTGRES_USER: {database_config.postgres_user}")
print(f"  POSTGRES_DATABASE: {database_config.postgres_database}")
EOF
```

### Step 4: Test Application Connection

```bash
# Try starting the application with verbose logging
export LOG_LEVEL=DEBUG
python -m uvicorn main:app --host 0.0.0.0 --port 8011

# Look for errors like:
# - "could not translate host name"
# - "Connection refused"
# - "password authentication failed"
```

---

## Common Errors and Solutions

### Error: "Connection refused"
**Cause:** PostgreSQL not running or port is wrong
**Solution:**
```bash
# Verify PostgreSQL is running
psql -h YOUR_HOST -p 5432 -U postgres -c "SELECT 1;"

# If port is custom, update POSTGRES_PORT or DATABASE_URL
```

### Error: "password authentication failed"
**Cause:** Wrong password
**Solution:**
```bash
# Verify credentials with psql first
psql -h YOUR_HOST -p 5432 -U postgres -W

# Update environment variables with correct password
export POSTGRES_PASSWORD=correct_password
```

### Error: "database 'graphtrace' does not exist"
**Cause:** Database not created yet
**Solution:**
```bash
# Create the database as superuser
psql -h YOUR_HOST -p 5432 -U postgres -c "CREATE DATABASE graphtrace;"

# Or run the initialization script
python -m scripts.init_db_schema
```

### Error: "could not translate host name"
**Cause:** Invalid hostname or DNS resolution issue
**Solution:**
```bash
# Verify hostname is resolvable
nslookup YOUR_HOST
ping YOUR_HOST

# If using private IP, ensure network connectivity
# If using VPN/private network, verify VPN is connected
```

---

## Development vs. Production Port Differences

| Aspect | Development | Production | Default |
|--------|-------------|------------|---------|
| **Port** | 5433 (custom) | 5432 (standard) | 5432 |
| **Host** | 127.0.0.1 | Remote host | localhost |
| **Database** | graphtrace | graphtrace | graphtrace |
| **User** | postgres | postgres | postgres |
| **.env Needed** | Yes | No (use secrets) | No |
| **PASSWORD_FILE** | ✓ Can use | ✗ Use secrets | ✗ Don't use |

**Why the difference?**
- Development: Uses custom port 5433 to avoid conflicts with production PostgreSQL
- Production: Uses standard port 5432 as expected by cloud providers and standard deployments
- Application defaults to 5432 when individual `POSTGRES_*` variables are used

---

## Recommended Approach

### For Local Development

Create `.env`:
```env
GRAPH_TRACE_LOAD_DOTENV=true

# Use individual POSTGRES_* variables (clearer and more flexible)
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5433  # Your local dev port
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=postgres
POSTGRES_PASSWORD=tcs12345

# DO NOT set DATABASE_URL - let it build from POSTGRES_* variables
```

### For Production/Customer Environments

**Never commit .env file to repository!**

Instead, use environment variables directly:
```bash
# In systemd service file, Docker, Kubernetes, or cloud provider
export POSTGRES_HOST=production-postgres.example.com
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=graphtrace
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=${SECRETS_MANAGER_PASSWORD}
```

---

## Migration Path

If you're using `DATABASE_URL` and need to switch to `POSTGRES_*` variables:

```bash
# Before (with DATABASE_URL)
export DATABASE_URL="postgresql://postgres:password@host:5432/graphtrace"

# After (using POSTGRES_* variables)
unset DATABASE_URL
export POSTGRES_HOST=host
export POSTGRES_PORT=5432
export POSTGRES_DATABASE=graphtrace
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=password
```

The application will automatically build the connection string from `POSTGRES_*` variables if `DATABASE_URL` is not set.

---

## Verification Checklist

- [ ] PostgreSQL is running and listening on port 5432
- [ ] Network connectivity from app to PostgreSQL (no firewall blocks)
- [ ] PostgreSQL credentials are correct (username/password/database)
- [ ] Environment variables are properly set
- [ ] `.env` file is not overriding with wrong port (if using GRAPH_TRACE_LOAD_DOTENV)
- [ ] Application starts without connection errors
- [ ] Health check endpoint returns ✓ postgres.ok=true

```bash
# Verify health
curl -s http://localhost:8011/health | jq '.dependencies.postgres'
# Expected: { "ok": true }
```

---

## For Support/Deployment Team

When deploying to customer environment:

1. **Determine PostgreSQL Port:** Ask customer if PostgreSQL is on standard 5432 or custom port
2. **Collect Credentials:**
   - PostgreSQL host (FQDN or IP)
   - Port (usually 5432)
   - Username (usually postgres)
   - Password (from customer or generated)
   - Database name (graphtrace or customer-specific)

3. **Set Environment Variables:**
   ```bash
   # Use POSTGRES_* variables (most flexible)
   POSTGRES_HOST=customer-host
   POSTGRES_PORT=5432
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=customer_password
   POSTGRES_DATABASE=graphtrace
   ```

4. **Test Connection:**
   ```bash
   python -m scripts.init_db_schema  # Creates schema if needed
   python -m uvicorn main:app        # Start app
   curl http://localhost:8011/health # Verify connectivity
   ```

5. **Document:** Record which POSTGRES_* values are used for that deployment for future reference.
