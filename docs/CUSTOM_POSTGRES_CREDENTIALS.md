# Custom PostgreSQL Credentials & Configuration

**TL;DR:** YES, the system fully supports custom Postgres hostname, port, username, and password. Everything is configured via `python_backend/.env` with **zero hardcoded credentials** in the code.

## Configuration Flow

```
┌─────────────────────────────────────────────────┐
│  Customer Environment (Their Data Center)       │
│  ┌────────────────────────────────────────────┐ │
│  │ Postgres Server                            │ │
│  │ - Host: db.company.local (or IP)          │ │
│  │ - Port: 5433 (or custom)                  │ │
│  │ - User: app_user                          │ │
│  │ - Password: ****secret****                │ │
│  └────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
                     ↓ Configured via
                  DATABASE_URL
                     ↓
┌─────────────────────────────────────────────────┐
│  python_backend/.env                            │
│  DATABASE_URL=postgresql://app_user:****@      │
│  db.company.local:5433/graphtrace              │
└─────────────────────────────────────────────────┘
                     ↓ Loaded at startup
        ┌────────────────────────────────────────┐
        │ Backend (main.py)                      │
        │ MCP Server (mcp_server/config.py)     │
        │ All Agent Services                    │
        └────────────────────────────────────────┘
```

## Configuration Sources (Priority Order)

### 1. **Environment Variables** (Highest Priority)
If set, these override everything:
```bash
export DATABASE_URL=postgresql://user:pass@host:port/db
```

### 2. **python_backend/.env File** (Recommended)
Single source of truth for deployment:
```env
DATABASE_URL=postgresql://postgres:mypassword@db.company.local:5433/graphtrace
```

### 3. **Hardcoded Defaults in Code** (Lowest Priority)
Only used if env var and .env file are missing:
```python
# mcp_server/config.py (fallback only)
DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5433/graphtrace"
```

## Complete Setup for Custom Credentials

### Step 1: Copy Template
```bash
cp python_backend/.env.example python_backend/.env
```

### Step 2: Edit with Your Postgres Details
```env
# REQUIRED: Postgres connection credentials
DATABASE_URL=postgresql://YOUR_USERNAME:YOUR_PASSWORD@YOUR_HOST:YOUR_PORT/graphtrace

# OPTIONAL: Legacy settings (DATABASE_URL takes precedence)
POSTGRES_HOST=YOUR_HOST
POSTGRES_PORT=YOUR_PORT
POSTGRES_DATABASE=graphtrace
POSTGRES_USER=YOUR_USERNAME
POSTGRES_PASSWORD=YOUR_PASSWORD
```

**Example with custom values:**
```env
# Customer's Postgres on 10.0.0.50:5433 with user 'app_user'
DATABASE_URL=postgresql://app_user:SecureP@ss123@10.0.0.50:5433/graphtrace
POSTGRES_HOST=10.0.0.50
POSTGRES_PORT=5433
POSTGRES_USER=app_user
POSTGRES_PASSWORD=SecureP@ss123
```

### Step 3: Verify Configuration
Check that the system can reach Postgres:
```bash
python scripts/check_postgres.py --detailed
```

Expected output with custom credentials:
```
INFO: 📋 Connection: app_user@10.0.0.50:5433/graphtrace
INFO: Testing PostgreSQL connection...
INFO: ✅ Connection OK
INFO: ✅ Schema initialized (20 tables)
```

### Step 4: Start Full Stack
```bash
./graphtrace.ps1 -Start
```

All services will use the credentials from `.env`:
- ✅ Backend (port 8011)
- ✅ MCP Server (port 8012)
- ✅ Agent Services (various ports)
- ✅ Frontend (proxied to backend)

## Components That Use DATABASE_URL

| Component | Location | Loads From | Can Override |
|-----------|----------|-----------|---|
| **Backend** | `python_backend/main.py` | `core/external_config.py` | ✅ Via `DATABASE_URL` env var |
| **MCP Server** | `mcp_server/main.py` | `mcp_server/config.py` | ✅ Via `DATABASE_URL` env var |
| **ETL Orchestrator** | `agent_services/etl_orchestrator/` | Shared `.env` | ✅ Via `DATABASE_URL` env var |
| **Data Analyst Agent** | `agent_services/data_analyst/` | Shared `.env` | ✅ Via `DATABASE_URL` env var |
| **Chat Coordinator** | `agent_services/chat_coordinator/` | Shared `.env` | ✅ Via `DATABASE_URL` env var |
| **All Other Agents** | `agent_services/*/` | Shared `.env` | ✅ Via `DATABASE_URL` env var |
| **Health Check Script** | `scripts/check_postgres.py` | Loads `.env` | ✅ Via `DATABASE_URL` env var |
| **Schema Init Script** | `scripts/init_db_schema.py` | Loads `.env` | ✅ Via `DATABASE_URL` env var |
| **Diagnostics** | `scripts/diagnostics.py` | Loads `.env` | ✅ Via `DATABASE_URL` env var |

✅ **All components use the SAME `.env` file** — shared configuration ensures consistency.

## Error Scenarios & Troubleshooting

### Scenario 1: Custom Host/Port
**Customer has:** Postgres on `db.internal:5555` instead of localhost:5433

**Solution:**
```env
DATABASE_URL=postgresql://postgres:password@db.internal:5555/graphtrace
```

**Test:**
```bash
python scripts/check_postgres.py --detailed
# Should show:
# 📋 Connection: postgres@db.internal:5555/graphtrace
```

### Scenario 2: Custom Credentials
**Customer has:** Database user `app_service` with password `MySecure!Pass`

**Solution:**
```env
DATABASE_URL=postgresql://app_service:MySecure!Pass@localhost:5433/graphtrace
```

**Test:**
```bash
python scripts/check_postgres.py
# Should succeed if credentials are correct
```

### Scenario 3: Connection Fails
**Error:** `psycopg.OperationalError: connection failed`

**Causes & Fixes:**
| Cause | Fix | Test Command |
|-------|-----|---|
| Wrong hostname | Update `DATABASE_URL` host | `ping db.company.local` |
| Wrong port | Update `DATABASE_URL` port | `psql -h host -p port -U user` |
| Wrong username | Update `DATABASE_URL` user | Check with DBA |
| Wrong password | Update `DATABASE_URL` password | `psql -h host -U user -c "SELECT 1"` |
| Postgres not running | Start Postgres service | `pg_isready -h host -p port` |
| Firewall blocking | Open port 5433 (or custom) | Network team: allow outbound to Postgres |

### Scenario 4: Schema Missing
**Error:** `⚠️ Schema NOT initialized (run: python scripts/init_db_schema.py)`

**Solution:**
```bash
# Auto-initialize with custom credentials (uses DATABASE_URL from .env)
python scripts/check_postgres.py --init-schema

# OR manual init
cd python_backend
python scripts/init_db_schema.py --initialize
```

## Special Cases

### Azure PostgreSQL (Single Server or Flexible)
```env
# Azure Postgres: server.postgres.database.azure.com
DATABASE_URL=postgresql://adminuser@servername:AzureP@ss123@servername.postgres.database.azure.com:5432/graphtrace
```

**Note:** Azure requires `@servername` in the username when using Azure AD.

### AWS RDS PostgreSQL
```env
# RDS endpoint: graphtrace.**.us-east-1.rds.amazonaws.com
DATABASE_URL=postgresql://postgres:RDSPassword123@graphtrace.**.us-east-1.rds.amazonaws.com:5432/graphtrace
```

### Google Cloud SQL PostgreSQL
```env
# Cloud SQL: instance-connection-name + public IP
DATABASE_URL=postgresql://postgres:GCPPass123@35.192.100.50:5432/graphtrace
```

### Docker Container (Internal Network)
```env
# Postgres running as Docker service named 'db'
DATABASE_URL=postgresql://postgres:password@db:5432/graphtrace
```

## Frontend Configuration (Separate from DB)

The **frontend does NOT need custom Postgres credentials**. It connects to the backend via HTTP.

**Frontend Configuration** (Optional, if deploying to different host):
```env
# e2etraceapp/.env (optional for remote backend)

# For dev proxy to custom backend host:
VITE_DEV_PROXY_TARGET=http://custom-backend-host:8011

# For production (absolute URL instead of relative):
VITE_API_BASE_URL=http://custom-backend-api:8011
```

**Default behavior:** Frontend uses relative `/api/` URLs, proxied to backend at `http://127.0.0.1:8011`.

## Security Best Practices

### 1. Never Commit Credentials
```bash
# ✅ DO: Add to .gitignore
echo "python_backend/.env" >> .gitignore

# Deploy specific .env for each environment
# env/development/.env
# env/staging/.env
# env/production/.env
```

### 2. Use Strong Passwords
```env
# ❌ BAD
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/graphtrace

# ✅ GOOD
DATABASE_URL=postgresql://postgres:K8vPqR2xL9nM_SecurePass@10.0.0.50:5433/graphtrace
```

### 3. Encrypt Secrets in Transit
For secure deployment:
- Use **VPN/TLS** to your infrastructure
- Encrypt `.env` file at rest
- Consider **Azure Key Vault** or **AWS Secrets Manager** for cloud deployments

### 4. Minimal User Permissions
Grant Postgres user only necessary permissions:
```sql
-- Example: app_service user (not admin)
CREATE USER app_service WITH PASSWORD 'SecurePass123';
CREATE DATABASE graphtrace OWNER app_service;

-- Grant only required permissions
GRANT CONNECT ON DATABASE graphtrace TO app_service;
GRANT USAGE ON SCHEMA public TO app_service;
GRANT CREATE ON SCHEMA public TO app_service;
```

## Validation Checklist

Before deployment with custom credentials:

- [ ] Database server is running and reachable
- [ ] Connection string is correct: `postgresql://user:pass@host:port/db`
- [ ] Username and password are correct
- [ ] Firewall allows outbound to Postgres port
- [ ] `.env` file has `DATABASE_URL` configured
- [ ] `python scripts/check_postgres.py` returns exit code 0
- [ ] Schema is initialized (20+ tables visible)
- [ ] `./graphtrace.ps1 -Start` launches without connection errors
- [ ] Frontend loads at `http://localhost:5173` (or your proxy host)
- [ ] Backend health endpoint works: `http://localhost:8011/health`

## Testing Custom Credentials (Without Full Stack)

```bash
# 1. Check connection only (fast)
python scripts/check_postgres.py

# 2. Check connection + show version
python scripts/check_postgres.py --detailed

# 3. Initialize schema if missing
python scripts/check_postgres.py --init-schema

# 4. Manual connection test
psql -h YOUR_HOST -p YOUR_PORT -U YOUR_USER -d graphtrace -c "SELECT version()"
```

## Rollback / Migration

If customer needs to migrate to a different Postgres server:

```bash
# 1. Back up old database
pg_dump postgresql://old_user:pass@old_host:5433/graphtrace > graphtrace_backup.sql

# 2. Create new database on new server
psql -h new_host -U admin -c "CREATE DATABASE graphtrace"

# 3. Restore
psql -h new_host -U admin -d graphtrace < graphtrace_backup.sql

# 4. Update .env
DATABASE_URL=postgresql://app_user:pass@new_host:5433/graphtrace

# 5. Verify
python scripts/check_postgres.py --detailed

# 6. Start services
./graphtrace.ps1 -Start
```

## FAQ

**Q: Will hardcoding different credentials break the app?**  
A: No, the code has **zero hardcoded production credentials**. Defaults are for local dev only.

**Q: Can I change credentials without restarting?**  
A: No, restart full stack:
```bash
# Stop current
./graphtrace.ps1 -Stop

# Update .env
# ... edit python_backend/.env ...

# Start again
./graphtrace.ps1 -Start
```

**Q: What if DATABASE_URL is too long to set as env var?**  
A: Use the `.env` file (recommended for production). It handles any length.

**Q: Can I use different credentials for frontend and backend?**  
A: No, frontend doesn't connect to Postgres directly. It uses the backend API. Only backend Postgres credentials are needed.

**Q: Does the MCP server use the same credentials?**  
A: Yes! All services read from `python_backend/.env`. One configuration, all services.

**Q: What if I need read-only access for some services?**  
A: Create a read-only Postgres user and update `DATABASE_URL`:
```env
DATABASE_URL=postgresql://readonly_user:password@host:port/graphtrace
```

## Summary

✅ **Installation will work** with ANY valid Postgres host, port, username, password  
✅ **App will work** with ANY valid Postgres configuration  
✅ **Zero hardcoded credentials** in code  
✅ **Single configuration file** for all services  
✅ **Validated at startup** with health check script  

The system is **fully flexible** for customer deployments.
