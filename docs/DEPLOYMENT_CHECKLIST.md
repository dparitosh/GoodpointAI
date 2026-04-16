# Deployment Checklist

Use this checklist to validate your GraphTrace deployment before shipping to customers.

## Pre-Deployment Validation

### 1. Configuration Files
- [ ] All `.env.example` files contain **no hardcoded passwords**
- [ ] All `.env.example` files include **VM deployment guidance comments**
- [ ] Port numbers are consistent across all config files:
  - Backend: `8011`
  - MCP Server: `8012`
  - Frontend Dev: `5173`
  - PostgreSQL: `5433` (recommended to avoid conflicts with default 5432)
  - Agents: `8020-8025`

### 2. Documentation Accuracy
- [ ] `docs/INSTALLATION.md` reflects current script behavior
- [ ] Multi-VM deployment section is complete
- [ ] Security considerations are documented
- [ ] Troubleshooting section covers common errors
- [ ] All file paths in docs match actual repo structure

### 3. Installation Scripts
- [ ] `graphtrace.ps1 -Check` validates `.env` configuration before proceeding
- [ ] `graphtrace.ps1 -Start` fails safely if credentials are not configured
- [ ] `start-backend.bat` includes same validation as PowerShell version
- [ ] All scripts use relative paths (no hardcoded absolute paths)
- [ ] Scripts provide clear error messages with remediation steps

### 4. Source Code
- [ ] No hardcoded passwords in any file (check with: `git grep -i "password.*=.*['\"].*['\"]"`)
- [ ] No hardcoded `localhost` or `127.0.0.1` in service URLs (use config/env vars)
- [ ] Database seed scripts respect environment variables for connection strings
- [ ] CORS allowed origins come from config, not hardcoded arrays

### 5. Database Configuration
- [ ] Seed scripts (`seed_db_config.py`, `seed_admin_configs.py`) check environment variables first
- [ ] Default values are safe (empty passwords, localhost only for dev)
- [ ] Schema init script (`init_db_schema.py`) provides clear error messages
- [ ] Reset script (`reset_postgres_schema.py`) requires explicit confirmation

## Deployment Testing Checklist

### Single-Machine Deployment Test
```powershell
# 1. Fresh clone
git clone <repo> && cd <repo>

# 2. Configure database
# Manually create PostgreSQL database 'graphtrace'

# 3. Configure credentials
copy python_backend\.env.example python_backend\.env
# Edit python_backend\.env with actual credentials

# 4. Validate
.\graphtrace.ps1 -Check

# 5. Start services
.\graphtrace.ps1 -Start

# 6. Verify
# - Backend health: http://localhost:8011/health
# - Frontend: http://localhost:5173
# - API Docs: http://localhost:8011/docs
```

**Expected Results:**
- [ ] Bootstrap completes without errors
- [ ] Database tables created successfully
- [ ] Encryption key generated at `python_backend/.graphtrace.encryption_key`
- [ ] Backend starts and shows "Application startup complete"
- [ ] Frontend loads and can reach backend API
- [ ] Health endpoint returns `{"status": "healthy", "db_ok": true, ...}`

### Multi-VM Deployment Test

#### VM1: Database Server
```powershell
# Install PostgreSQL, Neo4j, Redis
# Configure to accept network connections
# Create firewall rules for ports 5433, 7687, 6379
```

#### VM2: Backend Server
```powershell
git clone <repo> && cd <repo>

# Edit python_backend\.env with VM1 IPs
DATABASE_URL=postgresql://postgres:pass@<VM1_IP>:5433/graphtrace
NEO4J_URI=neo4j://<VM1_IP>:7687
REDIS_HOST=<VM1_IP>

# Bootstrap and start
.\graphtrace.ps1 -Check
.\graphtrace.ps1 -Start

# Verify backend is accessible from other VMs
# Test: curl http://<VM2_IP>:8011/health
```

#### VM3: Frontend Server
```powershell
git clone <repo> && cd <repo>\e2etraceapp

# Edit .env
echo "VITE_API_BASE_URL=http://<VM2_IP>:8011" > .env

# Build production assets
npm install
npm run build

# Serve with web server (Nginx/Apache)
# OR for testing: npm run dev
```

**Expected Results:**
- [ ] Backend can connect to databases on VM1
- [ ] Frontend can reach backend API on VM2
- [ ] CORS allows requests from frontend VM
- [ ] No localhost/127.0.0.1 connection errors

## Security Validation

### Credential Hygiene
- [ ] No credentials committed to git history
- [ ] `.env` files are in `.gitignore`
- [ ] Default passwords in `.env.example` are **not real passwords**
- [ ] Documentation warns users to change default credentials

### Network Security
- [ ] Backend does not bind to `0.0.0.0` by default (only when explicitly configured)
- [ ] CORS origins are restrictive (not `*`)
- [ ] Rate limiting is enabled
- [ ] Health check endpoint does not leak sensitive data

### Authentication
- [ ] `GRAPH_TRACE_AUTH_REQUIRED` can be enabled
- [ ] JWT secret is required when auth is enabled
- [ ] Admin user creation is documented
- [ ] API key validation works for protected endpoints

## Common Customer Issues (Resolved)

### Issue: Bootstrap fails silently
**Root Cause:** User didn't update `.env` with real credentials  
**Fix:** Bootstrap script now validates credentials and fails with clear error message

### Issue: Backend starts but can't connect to database
**Root Cause:** Port mismatch (5432 vs 5433)  
**Fix:** All config files now consistently use 5433 (or respect env vars)

### Issue: Frontend can't reach backend in multi-VM setup
**Root Cause:** Vite proxy target hardcoded to `localhost`  
**Fix:** Added `VITE_DEV_PROXY_TARGET` env var with clear documentation

### Issue: Agent services fail with "password" error
**Root Cause:** Hardcoded password "password" in agent default config  
**Fix:** Removed all hardcoded passwords, agents now require `.env` config

### Issue: Seed scripts create localhost-only connections
**Root Cause:** Seed scripts ignored env vars and hardcoded 127.0.0.1  
**Fix:** Seed scripts now check env vars first, allow overrides

## Final Checks

- [ ] Run `git status` - no uncommitted config changes
- [ ] Verify `.env` files are not tracked by git
- [ ] All documentation uses correct file paths
- [ ] Version tag is applied (e.g., `v1.0.0`)
- [ ] Release notes document known limitations
- [ ] Customer success contact info is in README

## Shipping Artifacts

Create a release package with:
1. Source code (git archive or GitHub release)
2. `docs/INSTALLATION.md` (primary installation guide)
3. `docs/DEPLOYMENT_CHECKLIST.md` (this file)
4. `docs/USER_GUIDE.md` (getting started guide)
5. `docs/ARCHITECTURE.md` (system overview)
6. Pre-flight verification script (optional: create `verify-install.ps1`)

---

**Last Updated:** {{ date }}  
**Validated By:** {{ team member }}  
**Deployment Environment Tested:** Single-machine Windows, Multi-VM Windows
