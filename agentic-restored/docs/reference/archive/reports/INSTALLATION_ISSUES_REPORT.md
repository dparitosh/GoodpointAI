# GraphTrace Installation Documentation & Scripts - Issues Report

**Generated:** January 7, 2026  
**Analyst:** Comprehensive Review  

---

## Executive Summary

This report identifies **faults, inconsistencies, and gaps** in the installation documentation and scripts. The current installation process has multiple issues that prevent reliable deployment in new environments.

---

## 🔴 CRITICAL ISSUES

### CRIT-I01: Port Inconsistency Across Documentation
**Severity:** Critical  
**Files Affected:** All documentation and scripts

| Source | Backend Port |
|--------|--------------|
| `INSTALLATION.md` | 8011 |
| `QUICK_START.md` | 8011 |
| `README-WINDOWS.md` | 8011 |
| `start-backend.ps1` | 8011 |
| `start-all.ps1` | 8011 |
| **VS Code tasks.json** | **8000** |
| **Previous session** | **8000** |

**Impact:** Users following VS Code tasks get port 8000, while documentation says 8011. Frontend proxy may fail to connect.

**Recommended Fix:** Standardize on a single port (recommend 8011) across ALL files.

---

### CRIT-I02: PostgreSQL Required But Not Clearly Stated
**Severity:** Critical  
**Files Affected:** `INSTALLATION.md`, `README-WINDOWS.md`

**Issue:** Documentation lists PostgreSQL as "required for the app database" but:
1. No installation instructions for PostgreSQL
2. No guidance on creating the `graphtrace` database
3. Default port is non-standard (5433 vs default 5432)
4. `.env.example` shows `POSTGRES_PORT=5433` without explanation

**Impact:** Users will fail at `scripts.init_db_schema` step with connection errors.

**Recommended Fix:** Add PostgreSQL installation section with:
- Installation instructions
- Database creation command: `CREATE DATABASE graphtrace;`
- Port configuration explanation

---

### CRIT-I03: Scripts Reference Non-Existent Files/Paths
**Severity:** Critical  
**Files Affected:** Multiple scripts

**Issues Found:**
1. `bootstrap.ps1` calls `python -m scripts.init_db_schema` but schema requires working DB connection
2. Documentation references `python_backend/.env.example` but doesn't instruct to copy it
3. Scripts assume `venv` doesn't exist on first run but don't handle pip upgrade failures

---

### CRIT-I04: No Interactive Configuration During Installation
**Severity:** Critical  
**Files Affected:** All setup scripts

**Issue:** Installation scripts do not prompt for any configuration:
- No Neo4j connection details prompted
- No PostgreSQL connection details prompted  
- No port selection offered
- No encryption key entry option

**Impact:** Users must manually edit `.env` files after failed first run.

---

## 🟠 HIGH PRIORITY ISSUES

### HIGH-I01: Hardcoded Credentials in .env Files
**Severity:** High (Security)  
**File:** `python_backend/.env`

```dotenv
NEO4J_PASSWORD="tcs12345"
POSTGRES_PASSWORD="tcs12345"
```

**Issue:** Production credentials committed to repository.

**Recommended Fix:** 
1. Add `.env` to `.gitignore`
2. Only track `.env.example` with placeholder values
3. Interactive setup should generate `.env` from user input

---

### HIGH-I02: Missing Dependency: psycopg
**Severity:** High  
**File:** `python_backend/requirement.txt`

**Issue:** The `db_session.py` uses:
```python
f"postgresql+psycopg://{user}:{quote_plus(password)}@{host}:{port}/{database}"
```

But `psycopg` (not `psycopg2`) requires explicit installation and may not be in requirements.

**Impact:** SQLAlchemy connection will fail with `ModuleNotFoundError`.

---

### HIGH-I03: Inconsistent Requirements File Names
**Severity:** High  
**Files:** 
- `requirement.txt` (actual file)
- `requirements.txt` (also exists)
- `requirements_external_integrations.txt`

**Issue:** Documentation says "this is intentional for backward compatibility" but scripts only reference `requirement.txt`.

---

### HIGH-I04: GRAPH_TRACE_LOAD_DOTENV Not Set by Default
**Severity:** High  
**File:** `core/external_config.py`

```python
_LOAD_DOTENV = (os.getenv("GRAPH_TRACE_LOAD_DOTENV") or "").strip().lower() in {"1", "true", "yes"}
if _LOAD_DOTENV:
    load_dotenv(dotenv_path=dotenv_path, override=True)
```

**Issue:** By default, `.env` files are NOT loaded unless `GRAPH_TRACE_LOAD_DOTENV=1` is set.

**Impact:** Users following documentation will have `.env` files that are silently ignored.

**Recommended Fix:** Either:
1. Default to loading `.env` in development
2. Document the required environment variable
3. Set it in startup scripts

---

### HIGH-I05: Neo4j Cloud vs Local URI Confusion
**Severity:** High  
**Files:** `.env`, `.env.example`, documentation

**Inconsistencies:**
| Source | Neo4j URI |
|--------|-----------|
| `.env` (actual) | `neo4j://127.0.0.1:7687` |
| `.env.example` | `neo4j://127.0.0.1:7687` |
| Previous session `.env` | `neo4j+s://2cccd05b.databases.neo4j.io` |

**Issue:** No guidance on when to use `neo4j://` vs `neo4j+s://` (SSL).

---

## 🟡 MEDIUM PRIORITY ISSUES

### MED-I01: Bootstrap Script Missing Error Recovery
**File:** `bootstrap.ps1`

**Issues:**
1. No rollback if frontend npm install fails
2. No cleanup of partial venv on failure
3. Script continues even if DB schema creation fails

---

### MED-I02: Diagnostics Don't Validate Configuration
**File:** `diagnostics/windows/diagnose-all.ps1`

**Missing Checks:**
1. PostgreSQL connectivity
2. Neo4j connectivity  
3. `.env` file presence and validity
4. Required environment variables

---

### MED-I03: No Service Health Verification
**Files:** `start-all.ps1`, `start-backend.ps1`

**Issue:** Scripts start services but don't verify they're actually running:
- No health check after startup
- No retry logic
- No timeout for startup

---

### MED-I04: Frontend .env Auto-Creation with Wrong Values
**File:** `start-frontend.ps1`

```powershell
VITE_NEO4J_URI=bolt://localhost:7687
VITE_NEO4J_USER=neo4j
```

**Issue:** Creates `.env` with Neo4j values that frontend doesn't need (these should be backend-only).

---

### MED-I05: Documentation Says "Docker Not Required" But docker-compose.yml Exists
**Issue:** Mixed messaging about deployment options.

---

## 🟢 LOW PRIORITY ISSUES

### LOW-I01: Inconsistent PowerShell Script Structure
**Issue:** Some scripts use `Push-Location/Pop-Location`, others use `Set-Location`.

### LOW-I02: Missing Script Usage Comments
**Issue:** Scripts lack header comments explaining parameters and behavior.

### LOW-I03: No Uninstall/Clean Script
**Issue:** No way to cleanly remove installed components for fresh start.

### LOW-I04: Logs Directory Not Auto-Created
**Issue:** Documentation references `logs/` but it's not created by scripts.

---

## Configuration Requirements Summary

For a successful installation in a **new environment**, users need:

| Requirement | Current Status | Action Needed |
|-------------|----------------|---------------|
| Python 3.8+ | ✅ Documented | None |
| Node.js 18+ | ✅ Documented | None |
| PostgreSQL | ⚠️ Listed but no setup | Add installation guide |
| Neo4j | ⚠️ Mentioned but unclear | Add setup instructions |
| `.env` configuration | ❌ Not interactive | Create interactive setup |
| Port configuration | ❌ Hardcoded conflicts | Standardize or make configurable |
| Encryption key | ⚠️ Auto-generated but not explained | Document purpose |

---

## Recommended Installation Flow

The installation should follow this interactive flow:

```
1. System Check
   ├── Python version check
   ├── Node.js version check
   └── npm version check

2. Database Configuration (Interactive Prompts)
   ├── PostgreSQL Host [localhost]
   ├── PostgreSQL Port [5432]
   ├── PostgreSQL Database [graphtrace]
   ├── PostgreSQL User [postgres]
   └── PostgreSQL Password [****]

3. Neo4j Configuration (Interactive Prompts)
   ├── Neo4j URI [neo4j://localhost:7687]
   ├── Neo4j User [neo4j]
   ├── Neo4j Password [****]
   └── Neo4j Database [neo4j]

4. Application Configuration
   ├── Backend Port [8011]
   ├── Frontend Port [5173]
   └── Generate encryption key? [Y/n]

5. Generate Configuration Files
   ├── Create python_backend/.env
   ├── Create e2etraceapp/.env
   └── Create logs/ directory

6. Install Dependencies
   ├── Create Python venv
   ├── Install pip packages
   └── Install npm packages

7. Initialize Database
   ├── Create schema
   └── Seed default config

8. Verify Installation
   ├── Test PostgreSQL connection
   ├── Test Neo4j connection
   └── Display access URLs
```

---

## Next Steps

1. **Create interactive setup script** (`setup-interactive.ps1`)
2. **Standardize ports** across all documentation
3. **Add PostgreSQL setup documentation**
4. **Update .gitignore** to exclude `.env` files
5. **Add health checks** to startup scripts
