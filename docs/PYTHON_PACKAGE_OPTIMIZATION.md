# Python Package Optimization Guide

## Current Dependency Analysis

### **Total Packages: ~60-70** (including transitive dependencies)

**Breakdown by Category:**

| Category | Packages | Can Optimize? |
|----------|----------|---------------|
| Core Web Framework | 5 | ❌ Required |
| Database | 6 | ⚠️ Partial |
| File Formats | 7 | ✅ Yes |
| AI/LLM | 4 | ✅ Optional |
| Background Jobs | 2 | ✅ Optional |
| Monitoring | 2 | ✅ Optional |
| SOAP/OData | 2 | ✅ Optional |
| Testing | 3 | ⚠️ Dev only |
| Utilities | 10+ | ⚠️ Partial |

---

## Optimization Strategies

### 1. **Make Heavy Dependencies Optional (Lazy Loading)**

**Current Problem:**
- All packages are installed even if features aren't used
- Heavy packages loaded unconditionally

**Solution: Fail-Closed Pattern**

```python
# ✅ GOOD: Lazy import with graceful degradation
def process_excel(file_path: str):
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path)
        # ...process
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Excel support requires: pip install openpyxl"
        )
```

**Packages to Make Optional:**

```python
# requirements.txt -> Split into requirements-core.txt + requirements-optional.txt

# Core (always installed)
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.35
psycopg[binary]==3.2.3
pydantic==2.9.2

# Optional: Excel/Office
# openpyxl==3.1.5
# python-docx==1.1.2
# xlrd==2.0.1

# Optional: AI/LLM
# openai==1.57.0
# anthropic==0.39.0
# ollama==0.4.4

# Optional: SOAP/Legacy
# zeep==4.2.1
# pyodata==1.11.2

# Optional: Background Jobs
# celery==5.4.0
# kombu==5.4.2

# Optional: Monitoring
# sentry-sdk==2.18.0
# prometheus-client==0.21.0
```

---

### 2. **Replace Heavy Packages with Lighter Alternatives**

#### **A. Pandas → Standard Library (when possible)**

**Current: pandas==2.2.3 (~100MB installed)**

```python
# ❌ HEAVY: Using pandas for simple CSV
import pandas as pd
df = pd.read_csv('data.csv')
result = df.to_dict('records')

# ✅ LIGHT: Use standard library csv
import csv
with open('data.csv') as f:
    result = list(csv.DictReader(f))
```

**When to use pandas:**
- Complex transformations (groupby, pivot, merge)
- Statistical operations
- Time series analysis
- ETL with intelligent column mapping (keep for migration service)

**When to avoid pandas:**
- Simple CSV reading/writing
- JSON transformations
- Basic data filtering

#### **B. Requests → httpx (already have it)**

**Current: Both requests==2.32.3 AND httpx==0.27.2**

```python
# ❌ TWO PACKAGES for HTTP
import requests  # Sync
import httpx     # Async

# ✅ ONE PACKAGE (httpx supports both)
import httpx

# Sync
response = httpx.get(url)

# Async
async with httpx.AsyncClient() as client:
    response = await client.get(url)
```

**Action: Remove `requests` package, use `httpx` everywhere**

#### **C. python-dateutil → datetime (standard library)**

**Current: python-dateutil==2.9.0**

```python
# ❌ External dependency
from dateutil.parser import parse
dt = parse("2024-01-15T10:30:00Z")

# ✅ Standard library
from datetime import datetime
dt = datetime.fromisoformat("2024-01-15T10:30:00+00:00")
```

**When to keep dateutil:**
- Parsing ambiguous date strings
- Relative date calculations (relativedelta)
- Complex timezone calculations

**Action: Review usage, replace simple cases with stdlib**

---

### 3. **Remove Duplicate/Overlapping Packages**

#### **Database Drivers: Too Many**

**Current:**
```
psycopg[binary]==3.2.3  # Postgres (sync)
asyncpg==0.30.0         # Postgres (async)
oracledb>=2.0.0         # Oracle
pyodbc>=5.0.0           # SQL Server
```

**Recommendation:**
```python
# Core requirement (always installed)
psycopg[binary]==3.2.3

# Optional extras in requirements-migration.txt
# oracledb>=2.0.0
# pyodbc>=5.0.0
```

**Rationale:**
- Oracle/SQL Server only needed for migration workflows
- Most deployments use PostgreSQL only
- Install on-demand: `pip install -r requirements-migration.txt`

#### **Remove asyncpg if not used**

Check if async Postgres is actually used:
```bash
grep -r "import asyncpg" python_backend/
grep -r "from asyncpg" python_backend/
```

If not found → **Remove asyncpg==0.30.0** (psycopg supports async via `psycopg.AsyncConnection`)

---

### 4. **Split Requirements by Feature**

**Proposed Structure:**

```
python_backend/
├── requirements.txt              # Core only (minimal installation)
├── requirements-ai.txt           # LLM/embeddings (openai, anthropic, ollama)
├── requirements-migration.txt    # Database migration (oracledb, pyodbc, pandas)
├── requirements-office.txt       # Excel/Word support (openpyxl, python-docx)
├── requirements-monitoring.txt   # Sentry, Prometheus
├── requirements-jobs.txt         # Celery background jobs
├── requirements-dev.txt          # Testing, linting (pytest, black, ruff)
└── requirements-all.txt          # Everything (includes all above)
```

**Install examples:**
```bash
# Minimal installation (core API only)
pip install -r requirements.txt

# With AI features
pip install -r requirements.txt -r requirements-ai.txt

# With database migration
pip install -r requirements.txt -r requirements-migration.txt

# Everything
pip install -r requirements-all.txt
```

---

### 5. **Use Extras Instead of Separate Files**

**setup.py / pyproject.toml approach:**

```toml
# pyproject.toml
[project]
name = "graphtrace"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "sqlalchemy>=2.0.35",
    "psycopg[binary]>=3.2.3",
    "pydantic>=2.9.2",
]

[project.optional-dependencies]
ai = [
    "openai>=1.57.0",
    "anthropic>=0.39.0",
    "ollama>=0.4.4",
]
migration = [
    "oracledb>=2.0.0",
    "pyodbc>=5.0.0",
    "pandas>=2.2.3",
]
office = [
    "openpyxl>=3.1.5",
    "python-docx>=1.1.2",
]
monitoring = [
    "sentry-sdk>=2.18.0",
    "prometheus-client>=0.21.0",
]
dev = [
    "pytest>=8.3.4",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=6.0.0",
]
all = [
    "graphtrace[ai,migration,office,monitoring]",
]

# Install examples:
# pip install .                    # Core only
# pip install .[ai]                # With AI
# pip install .[ai,migration]      # AI + Migration
# pip install .[all]               # Everything
```

---

### 6. **Remove Unused Test Dependencies from Production**

**Current: Testing packages in main requirements.txt**

```
pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
```

**Action: Move to requirements-dev.txt**

```bash
# Production deployment (no tests)
pip install -r requirements.txt

# Development environment (with tests)
pip install -r requirements.txt -r requirements-dev.txt
```

---

### 7. **Audit and Remove Truly Unused Packages**

**Run dependency analysis:**

```bash
# Install pipdeptree
pip install pipdeptree

# Show dependency tree
pipdeptree

# Find unused packages (requires pip-autoremove)
pip install pip-autoremove
pip-autoremove <package-name> --dry-run
```

**Packages to Review:**

| Package | Usage | Action |
|---------|-------|--------|
| `schedule==1.2.2` | Background scheduling | Check if used, consider APScheduler alternative |
| `cachetools==5.5.0` | Caching utilities | Check if needed (Redis already installed) |
| `tenacity==9.0.0` | Retry logic | Check if used, simple to implement manually |
| `lxml==5.3.0` | XML parsing | If xmltodict covers use cases, remove lxml |
| `xmlschema==3.4.3` | XML validation | Check if actually needed |

**Find actual usage:**

```bash
# Check if package is imported
grep -r "import schedule" python_backend/
grep -r "from schedule" python_backend/

grep -r "import cachetools" python_backend/
grep -r "from cachetools" python_backend/

grep -r "import tenacity" python_backend/
grep -r "from tenacity" python_backend/
```

If no matches → **Safe to remove**

---

### 8. **Vendor Small Utility Libraries**

**Instead of installing entire packages for single functions:**

```python
# ❌ Install package for one function
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
def api_call():
    pass

# ✅ Vendor/implement simple retry
import time
from functools import wraps

def retry(max_attempts=3, delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay)
        return wrapper
    return decorator
```

**Packages to consider vendoring:**
- Simple utilities (<100 lines)
- No active maintenance needed
- Single-function usage

---

## Recommended Action Plan

### **Phase 1: Quick Wins (Immediate)**

1. ✅ **Split testing dependencies** → `requirements-dev.txt`
2. ✅ **Remove `requests`** → use `httpx` everywhere
3. ✅ **Make Oracle/SQL Server optional** → `requirements-migration.txt`
4. ✅ **Make AI packages optional** → `requirements-ai.txt`
5. ✅ **Check if `asyncpg` is used** → remove if not needed

**Expected reduction: 15-20 packages from base install**

### **Phase 2: Medium Effort (This Sprint)**

6. ⚠️ **Audit unused packages** → use pipdeptree + grep
7. ⚠️ **Replace pandas** in simple cases → use csv module
8. ⚠️ **Make monitoring optional** → `requirements-monitoring.txt`
9. ⚠️ **Make Celery optional** → `requirements-jobs.txt`
10. ⚠️ **Create requirements-all.txt** → for full installation

**Expected reduction: 10-15 additional packages**

### **Phase 3: Long Term (Future)**

11. 📋 **Migrate to pyproject.toml** → proper extras support
12. 📋 **Review file format libraries** → lazy load openpyxl, python-docx
13. 📋 **Consider fastapi-slim** → if don't need all features
14. 📋 **Evaluate pandas alternatives** → polars (if keeping heavy data processing)

---

## Measuring Success

### **Current Baseline:**
```bash
pip install -r requirements.txt
du -sh .venv/  # ~500-800 MB
```

### **Target After Optimization:**
```bash
# Core only
pip install -r requirements.txt
du -sh .venv/  # Target: ~200-300 MB (50-60% reduction)

# With common extras (AI + Migration)
pip install -r requirements.txt -r requirements-ai.txt -r requirements-migration.txt
du -sh .venv/  # Target: ~400-500 MB
```

---

## Dependencies File Examples

### **requirements.txt (Core)**
```pip-requirements
# Core Web Framework
fastapi==0.115.0
uvicorn[standard]==0.32.0
python-multipart==0.0.12
httpx==0.27.2
aiofiles==24.1.0

# Database (Postgres only)
sqlalchemy==2.0.35
alembic==1.13.1
psycopg[binary]==3.2.3

# Graph/Search (if always needed)
neo4j==5.25.0
opensearch-py==3.1.0

# Config/Validation
pydantic==2.9.2
pydantic-settings==2.6.0
python-dotenv==1.0.1
jsonschema==4.23.0
pyyaml==6.0.2

# Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
cryptography==44.0.0

# Basic utilities
python-dateutil==2.9.0
```

### **requirements-migration.txt**
```pip-requirements
-r requirements.txt

# Database connectors for migration
oracledb>=2.0.0
pyodbc>=5.0.0

# Data processing for ETL
pandas==2.2.3
pyarrow==18.1.0
```

### **requirements-ai.txt**
```pip-requirements
-r requirements.txt

openai==1.57.0
anthropic==0.39.0
ollama==0.4.4
mcp[cli]>=1.2.0,<2.0.0
```

### **requirements-office.txt**
```pip-requirements
-r requirements.txt

openpyxl==3.1.5
python-docx==1.1.2
xlrd==2.0.1
```

### **requirements-dev.txt**
```pip-requirements
-r requirements.txt

pytest==8.3.4
pytest-asyncio==0.24.0
pytest-cov==6.0.0
black==24.0.0
ruff==0.1.0
```

---

## Implementation Example

**Step 1: Create split files**
```bash
cd python_backend
# Backup current
cp requirements.txt requirements-backup.txt

# Create new structure
# ... (create files as shown above)
```

**Step 2: Test core installation**
```bash
python -m venv test-venv
source test-venv/bin/activate  # Windows: test-venv\Scripts\activate
pip install -r requirements.txt

# Should work: Basic API
python -m uvicorn main:app --host 0.0.0.0 --port 8011

# Should fail gracefully: Migration endpoints
curl http://localhost:8011/api/migration/advanced/rdbms/supported-types
# Returns: {"detail": "Migration support requires: pip install -r requirements-migration.txt"}
```

**Step 3: Update documentation**
- Update [INSTALLATION.md](../docs/INSTALLATION.md)
- Update [README.md](../README.md)
- Add installation options to docs

---

## Monitoring Package Bloat

**Add to CI/CD:**

```yaml
# .github/workflows/dependency-check.yml
name: Dependency Size Check

on: [pull_request]

jobs:
  check-size:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
      - name: Install and check size
        run: |
          python -m venv venv
          source venv/bin/activate
          pip install -r requirements.txt
          SIZE=$(du -sm venv | cut -f1)
          echo "Virtual env size: ${SIZE}MB"
          if [ $SIZE -gt 400 ]; then
            echo "❌ Environment too large: ${SIZE}MB (limit: 400MB)"
            exit 1
          fi
```

---

## Summary

**Recommended Immediate Actions:**

1. ✅ Create `requirements-dev.txt` for testing packages
2. ✅ Create `requirements-migration.txt` for Oracle/SQL Server
3. ✅ Create `requirements-ai.txt` for LLM packages
4. ✅ Remove `requests` and use `httpx` 
5. ✅ Check and potentially remove `asyncpg`

**Expected Results:**
- **Base installation:** 50-60% smaller (~200-300MB vs ~500-800MB)
- **Faster CI/CD:** Fewer packages to download/install
- **Better security:** Smaller attack surface
- **Clearer dependencies:** Know what features require what packages
- **Easier troubleshooting:** Isolate issues to specific feature sets

**This approach maintains all functionality while making the application more modular and efficient.**
