# GoodpointAI - Quick Reference Guide

## System Overview At-A-Glance

| Aspect | Details |
|--------|---------|
| **Project Name** | GoodpointAI (GraphTrace) |
| **Purpose** | PLM Data Migration, Lineage Tracking, ETL Orchestration |
| **Architecture** | React SPA + FastAPI microservices + PostgreSQL + Neo4j |
| **License** | Not specified in codebase |
| **Target Users** | Enterprise PLM teams, Data engineers, Analytics teams |
| **Deployment** | Local-first (Windows-first), containerizable |

---

## Quick Start Commands

### Prerequisites
```bash
# 1. Install requirements
- Python 3.11+ (3.12 recommended)
- Node.js 18+
- PostgreSQL 14+
- Neo4j (optional, for lineage)
- OpenSearch (optional, for search)

# 2. Create PostgreSQL database
psql -U postgres -h localhost -c "CREATE DATABASE graphtrace;"

# 3. Configure .env
# Backend: agentic-restored/python_backend/.env
DATABASE_URL="postgresql://postgres:password@127.0.0.1:5433/graphtrace"
NEO4J_URI="neo4j://127.0.0.1:7687"
NEO4J_PASSWORD="your_neo4j_password"
```

### Start Application

**Option A: VS Code Tasks (Recommended)**
```
1. Run task: "Start Backend Server"
2. Run task: "Start Frontend Development Server"
3. Open: http://localhost:5173
```

**Option B: PowerShell Scripts**
```powershell
cd agentic-restored
.\start-all.ps1  # Starts backend + frontend
```

**Option C: Manual**
```powershell
# Terminal 1: Backend
cd agentic-restored/python_backend
python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload

# Terminal 2: Frontend
cd agentic-restored/e2etraceapp
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### Verify Installation
```
✓ http://localhost:8011/health         → Backend health check
✓ http://localhost:8011/docs           → Swagger UI (OpenAPI)
✓ http://localhost:5173                → Frontend UI
✓ http://localhost:5173/#/admin        → Admin config page
```

---

## Key Ports

| Service | Port | Purpose |
|---------|------|---------|
| Frontend Dev Server | 5173 | React app |
| Backend API | 8011 | FastAPI endpoints |
| PostgreSQL | 5432 | Database (default) |
| Neo4j | 7687 | Graph database |
| OpenSearch | 9200 | Search engine (optional) |
| Apache (optional) | 80/443 | Production reverse proxy |

---

## File Structure Quick Reference

### Frontend Structure
```
e2etraceapp/
├── src/
│   ├── api/                  # API fetch wrappers
│   ├── components/           # 30+ React components
│   ├── pages/                # 12 route pages
│   ├── services/             # Business logic (8 services)
│   ├── contexts/             # React context providers (3)
│   ├── config/               # Configuration
│   ├── hooks/                # Custom React hooks
│   ├── i18n/                 # Internationalization
│   └── styles/               # Global CSS
├── vite.config.js            # Build configuration
└── package.json              # Dependencies (React 19, Vite 6.3)
```

### Backend Structure
```
python_backend/
├── main.py                   # FastAPI app entry point
├── core/                     # Core modules (database, auth, config)
├── models/                   # SQLAlchemy ORM + Pydantic models (9 types)
├── graph_api/                # FastAPI routers (25+ routers)
├── routers/                  # Additional routers (3)
├── services/                 # Business logic layer (8 services)
├── scripts/                  # Utility scripts
├── tests/                    # Pytest suite (15+ test files)
└── requirements.txt          # Python dependencies
```

---

## Core Technology Stack Reference

### Frontend Stack
- **React 19.1.0** - UI framework
- **Vite 6.3.5** - Build tool
- **React Router 7.6.2** - Client-side routing
- **Recoil 0.7.7** - State management
- **Cytoscape 3.32.0** - Graph visualization
- **ECharts 5.6.0** - Data visualization
- **Vitest 4.0.13** - Unit testing

### Backend Stack
- **FastAPI 0.115.0** - Web framework
- **Uvicorn 0.32.0** - ASGI server
- **SQLAlchemy 2.0.35** - ORM
- **Pydantic 2.7.0+** - Validation
- **asyncpg 0.30.0** - PostgreSQL async driver
- **neo4j 5.25.0** - Graph database driver
- **Alembic 1.13.1** - Database migrations

### Database Stack
- **PostgreSQL 14+** - Primary data persistence (required)
- **Neo4j 5.x** - Data lineage graph (optional)
- **OpenSearch 3.1.0** - Full-text search (optional)

---

## API Endpoint Summary

### Core Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/graph` | Fetch lineage graph |
| POST | `/api/custom-query` | Execute Cypher queries |
| GET | `/api/analytics` | Get analytics metrics |
| POST | `/api/migration/plans` | Create migration plan |
| POST | `/api/migration/plans/{id}/execute` | Execute migration |
| GET | `/api/workflow-manager/workflows` | List workflows |
| POST | `/api/data-mapping` | Define field mappings |
| GET | `/api/quality/metrics` | Get data quality metrics |
| POST | `/api/quality/scan` | Scan data quality |
| POST | `/api/rule-engine/validate` | Validate business rules |
| POST | `/api/agentic/task` | Dispatch agentic task |
| GET | `/api/agentic/task/{id}` | Get task result |
| POST | `/api/auth/login` | Authenticate (JWT) |
| POST | `/api/graphql` | GraphQL query execution |
| GET | `/api/opensearch/search` | Full-text search |

**Full endpoint list**: 40+ endpoints across 25+ routers

---

## Authentication & Authorization

### Default Admin Credentials
```
Username: admin (configurable via GRAPH_TRACE_ADMIN_USERNAME)
Password: (set via GRAPH_TRACE_ADMIN_PASSWORD or GRAPH_TRACE_ADMIN_PASSWORD_HASH)
```

### JWT Configuration
```python
# Environment variables
GRAPH_TRACE_JWT_SECRET           # Signing key
GRAPH_TRACE_JWT_ALGORITHM        # Default: HS256
GRAPH_TRACE_AUTH_REQUIRED        # Enable/disable auth
GRAPH_TRACE_AUTH_REQUIRED=true   # Default when secret is set
```

### API Key Authentication
```
Header: X-API-Key: your-api-key
Environment: GRAPH_TRACE_API_KEY
```

### Role-Based Access Control (RBAC)
```python
# Available roles
- "admin"      # Full access
- "analyst"    # Read/write migration workflows
- "viewer"     # Read-only (future)

# Usage in handlers
@require_admin()           # Requires admin role
@require_principal()       # Requires any authenticated user
```

---

## Configuration Management

### Environment Variables

**Database**
```env
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**Neo4j**
```env
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
NEO4J_DATABASE=neo4j
```

**Authentication**
```env
GRAPH_TRACE_JWT_SECRET=your-secret-key
GRAPH_TRACE_ADMIN_USERNAME=admin
GRAPH_TRACE_ADMIN_PASSWORD=password
GRAPH_TRACE_AUTH_REQUIRED=true
```

**OpenSearch (Optional)**
```env
OPENSEARCH_URL=http://localhost:9200
OPENSEARCH_TIMEOUT_S=30
```

**Application**
```env
GRAPH_TRACE_LOAD_DOTENV=true  # Load .env file
ENVIRONMENT=development        # development | production
LOG_LEVEL=INFO                # DEBUG | INFO | WARNING | ERROR
```

### Agentic Configuration

**File**: `python_backend/agentic_config.json`

```json
{
  "configuration": {
    "metadata": { "version": "2.0.0", "environment": "development" },
    "deployment": {
      "auto_deploy": true,
      "deployment_strategy": "progressive"
    },
    "agentic_orchestration": {
      "enabled": true,
      "orchestration_mode": "intelligent"
    },
    "security": {
      "encryption": { "encrypt_at_rest": false },
      "access_control": { "enable_rbac": false }
    }
  }
}
```

---

## Database Tables Overview

### PostgreSQL Schema

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `workflow_instances` | ETL workflow definitions | id, source_id, target_id, status, progress |
| `plm_ingestion_runs` | PLM ETL run metadata | id, source_system, target_system, status |
| `plm_staged_records` | Raw PLM payloads | run_id, object_type, payload |
| `plm_parts` | Part master data | part_number, name, classification |
| `plm_bom_items` | BOM relationships | parent_part_number, child_part_number, qty |
| `data_quality_scan_reports` | DQ scan results | run_id, report, issues_found |
| `business_rules` | Rule engine rules | name, rule_definition, severity |
| `persisted_graphql_queries` | Saved GraphQL queries | name, query, variables |
| `encrypted_admin_config` | Encrypted configuration | key, value (encrypted) |

---

## Frontend Pages & Routes

| Route | Page | Purpose |
|-------|------|---------|
| `/#/dashboard` | Dashboard | Main landing page |
| `/#/migration` | Migration Wizard | 5-step migration workflow |
| `/#/graph-explorer` | Graph Explorer | Neo4j lineage visualization |
| `/#/analytics` | Analytics Hub | KPI dashboards & reports |
| `/#/lineage` | Lineage Viewer | Data flow tracking |
| `/#/rule-engine` | Rule Management | Business rule CRUD |
| `/#/search` | Advanced Search | Full-text + filters |
| `/#/settings` | Settings | App configuration |
| `/#/admin` | Admin Config | System administration |
| `/#/workflow-manager` | Workflow Manager | Workflow history & status |
| `/#/observability` | Observability | System monitoring |
| `/#/api-docs` | API Documentation | REST API reference |

---

## Common Tasks

### 1. Create a New Migration Workflow
```bash
POST /api/migration/plans
{
  "name": "Teamcenter to Neo4j",
  "source": "teamcenter",
  "target": "neo4j",
  "config": { "connection": "..." }
}
```

### 2. Execute Migration
```bash
POST /api/migration/plans/{plan_id}/execute
```

### 3. Monitor Migration Progress
```bash
GET /api/migration/plans/{plan_id}/status
# Returns: { status, stage, progress %, processed_records, total_records }
```

### 4. Run Data Quality Scan
```bash
POST /api/quality/scan
{
  "source_id": "teamcenter",
  "rules": ["row_count", "uniqueness", "referential_integrity"]
}
```

### 5. Query Graph Lineage
```bash
GET /api/graph
# Returns: { nodes: [...], edges: [...] }
```

### 6. Execute Custom Cypher Query
```bash
POST /api/custom-query
{
  "query": "MATCH (p:Part) RETURN p LIMIT 100",
  "params": {}
}
```

### 7. Get Analytics Metrics
```bash
GET /api/analytics
# Returns node counts, relationship density, quality scores, etc.
```

### 8. Create Agentic Task
```bash
POST /api/agentic/task
{
  "type": "DATA_ANALYSIS",
  "payload": { "query": "Analyze data quality" }
}
```

### 9. Authenticate (Get JWT Token)
```bash
POST /api/auth/login
{
  "username": "admin",
  "password": "password"
}
# Returns: { "access_token": "eyJ...", "token_type": "bearer" }
```

---

## Testing

### Frontend Tests
```bash
cd e2etraceapp
npm test                    # Watch mode
npm test -- --run          # Single run
npm run lint               # ESLint
```

### Backend Tests
```bash
cd python_backend
pytest                     # Run all tests
pytest -v                  # Verbose output
pytest tests/test_*.py     # Specific test file
```

### Test Files
- `test_integration_neo4j_xstate.py` - Workflow + graph
- `test_plm_etl_soda_gate_fail_closed.py` - PLM ETL + quality
- `test_postgres_url_detection.py` - Database config
- `test_cors_and_system_config_db.py` - Security

---

## Troubleshooting

### Frontend Issues

**Issue**: Port 5173 already in use
```bash
# Kill existing process or use different port
npm run dev -- --host 127.0.0.1 --port 5174
```

**Issue**: API calls fail (CORS error)
```
Solution: Ensure backend is running on port 8011
Check: http://localhost:8011/health
Verify proxy config in vite.config.js
```

**Issue**: Graph not loading
```
Solution: Check Neo4j connection
Run: GET http://localhost:8011/api/graph
Check Neo4j service status
```

### Backend Issues

**Issue**: Database connection refused
```
Solution: Verify PostgreSQL is running
Check DATABASE_URL in .env
Run: psql -U postgres -h localhost -c "SELECT version();"
```

**Issue**: Neo4j connection failed
```
Solution: Check Neo4j service running
Verify NEO4J_URI in .env
Run: cypher-shell -u neo4j -p password
```

**Issue**: ModuleNotFoundError
```bash
Solution: Install requirements
cd python_backend
pip install -r requirements.txt
```

**Issue**: 401 Unauthorized
```
Solution: Check JWT secret is set
Run: echo $GRAPH_TRACE_JWT_SECRET
For development: Set GRAPH_TRACE_AUTH_REQUIRED=false
```

---

## Development Workflows

### Adding a New Router (Backend)

```python
# File: python_backend/graph_api/new_feature_router.py
from fastapi import APIRouter, Depends
from .dependencies import get_driver

router = APIRouter(prefix="/api/new-feature", tags=["New Feature"])

@router.get("/endpoint")
async def get_data(driver = Depends(get_driver)):
    # Your implementation
    return response

# Register in main.py:
# from graph_api.new_feature_router import router as new_feature_router
# app.include_router(new_feature_router)
```

### Adding a New Component (Frontend)

```jsx
// File: e2etraceapp/src/components/NewComponent.jsx
import React from 'react'
import './NewComponent.css'

export const NewComponent = () => {
  return <div>Component content</div>
}

// Use in page:
import { NewComponent } from '@components/NewComponent'
```

### Adding a Database Migration

```bash
cd python_backend
alembic revision --autogenerate -m "Add new column"
alembic upgrade head  # Apply migration
```

---

## Performance Tips

### Frontend
- Use React.memo for expensive components
- Lazy-load routes with React.lazy()
- Limit graph size (1000+ nodes = slow rendering)
- Use virtualized lists for large datasets
- Profile with Chrome DevTools

### Backend
- Use pagination (limit 100 records)
- Add database indexes on frequent query columns
- Use connection pooling (defaults should work)
- Monitor query execution time
- Use async/await for I/O operations

### Database
- EXPLAIN/ANALYZE queries before optimization
- Monitor slow query log
- Add composite indexes on frequently joined columns
- Archive old workflow history to separate table

---

## Useful Links

- **OpenAPI Documentation**: http://localhost:8011/docs
- **Frontend Routes**: http://localhost:5173/#/dashboard
- **PostgreSQL Docs**: https://www.postgresql.org/docs/
- **Neo4j Cypher**: https://neo4j.com/docs/cypher-manual/current/
- **FastAPI Tutorial**: https://fastapi.tiangolo.com/
- **React Docs**: https://react.dev/

---

## Key Design Decisions

### Why PostgreSQL over MongoDB?
- ACID guarantees for workflow state
- Referential integrity (foreign keys)
- JSON type support for flexible schemas
- Excellent Python ORM support

### Why React over Angular/Vue?
- Modern component-based UI
- Fast development cycle
- Large graph visualization ecosystem
- Strong TypeScript support

### Why FastAPI over Django?
- Async/await native support
- Automatic OpenAPI documentation
- Faster development
- Better performance for I/O-heavy workloads

### Why Neo4j for lineage?
- Native graph traversal
- Intuitive Cypher language
- Perfect for lineage/data flow
- Production-grade performance

---

## Next Steps for Development

1. **Run the application**: Follow "Quick Start" section
2. **Explore the UI**: Visit all pages and understand workflows
3. **Read the code**: Start with `main.py` and key routers
4. **Run tests**: Ensure everything passes
5. **Review documentation**: [INSTALLATION.md](docs/INSTALLATION.md), [EXECUTION_GUIDE.md](docs/EXECUTION_GUIDE.md)
6. **Add features**: Create new routers/components following patterns
7. **Test thoroughly**: Unit tests + integration tests

---

**Document Generated**: May 26, 2026  
**For Questions**: Refer to full architecture analysis in [ARCHITECTURE_ANALYSIS.md](ARCHITECTURE_ANALYSIS.md)
