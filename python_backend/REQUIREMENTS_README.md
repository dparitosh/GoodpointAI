# Python Requirements Structure

## Overview

GraphTrace dependencies are split into modular files to reduce installation size and allow feature-specific installations.

## Files

| File | Purpose | Size Impact |
|------|---------|-------------|
| `requirements-core.txt` | **Core API server** (FastAPI, PostgreSQL, Neo4j, OpenSearch) | ~200-300 MB |
| `requirements-migration.txt` | **Database migration** (Oracle, SQL Server, pandas, Excel) | +150-200 MB |
| `requirements-ai.txt` | **AI/LLM features** (OpenAI, Anthropic, Ollama, MCP) | +100-150 MB |
| `requirements-monitoring.txt` | **Monitoring** (Prometheus, Sentry) | +20-30 MB |
| `requirements-jobs.txt` | **Background jobs** (Celery, Redis) | +50-80 MB |
| `requirements-dev.txt` | **Testing** (pytest, coverage) | +30-50 MB |
| `requirements-all.txt` | **Everything** | ~600-800 MB |
| `requirements.txt` | **Legacy** (currently same as requirements-all.txt) | ~600-800 MB |

## Installation Examples

### Minimal (Core Only)
```bash
pip install -r requirements-core.txt
```
**Use case:** Simple API deployment without migration or AI features

### With AI Features
```bash
pip install -r requirements-core.txt -r requirements-ai.txt
```
**Use case:** Using LLM providers, agent orchestration

### With Database Migration
```bash
pip install -r requirements-core.txt -r requirements-migration.txt
```
**Use case:** Migrating from SQL Server, Oracle, MySQL to PostgreSQL

### Full Stack (Most Common)
```bash
pip install -r requirements-all.txt
```
**Use case:** Development, full-featured deployment

### Development Environment
```bash
pip install -r requirements-core.txt -r requirements-dev.txt
```
**Use case:** Running tests, development, CI/CD

## Feature Detection

The application uses **fail-closed patterns** for optional dependencies:

```python
# Example: Excel support
def process_excel():
    try:
        import openpyxl
        # ... process
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail="Excel support requires: pip install -r requirements-migration.txt"
        )
```

## Migration from Legacy requirements.txt

**Before (single file):**
```bash
pip install -r requirements.txt  # 60-70 packages, ~600-800 MB
```

**After (modular):**
```bash
# Core only (25-30 packages, ~200-300 MB)
pip install -r requirements-core.txt

# Add features as needed
pip install -r requirements-ai.txt         # +AI
pip install -r requirements-migration.txt  # +Migration
```

**Benefits:**
- 50-60% smaller base installation
- Faster CI/CD (fewer packages to download)
- Better security (smaller attack surface)
- Clearer feature dependencies

## Package Audit Results

**Removed from core:**
- `schedule==1.2.2` - Not used (Remove entirely)
- `cachetools==5.5.0` - Not used (Remove entirely)
- `pytest*` - Dev only (→ requirements-dev.txt)
- `celery`, `kombu` - Optional (→ requirements-jobs.txt)
- `sentry-sdk`, `prometheus-client` - Optional (→ requirements-monitoring.txt)
- `openai`, `anthropic`, `ollama` - Optional (→ requirements-ai.txt)
- `oracledb`, `pyodbc` - Optional (→ requirements-migration.txt)

**Still in core (essential):**
- `fastapi`, `uvicorn` - Web framework
- `sqlalchemy`, `psycopg`, `asyncpg` - Database
- `neo4j`, `opensearch-py` - Graph/search
- `pydantic` - Validation
- `python-jose`, `cryptography` - Security
- `tenacity` - Used by MCP client

## Next Steps

1. **Test core installation:**
   ```bash
   python -m venv test-env
   source test-env/bin/activate
   pip install -r requirements-core.txt
   python -m uvicorn --app-dir python_backend main:app
   ```

2. **Update documentation:**
   - Installation guide
   - Deployment instructions
   - Feature flags documentation

3. **Update CI/CD:**
   - Use requirements-core.txt for base image
   - Install optional features per job

4. **Future: Migrate to pyproject.toml** for better extras support

## References

- [PYTHON_PACKAGE_OPTIMIZATION.md](../../docs/PYTHON_PACKAGE_OPTIMIZATION.md) - Detailed optimization guide
- [INSTALLATION.md](../../docs/INSTALLATION.md) - Installation instructions
