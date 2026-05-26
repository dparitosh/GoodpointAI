# GoodpointAI Architecture Analysis

**Application**: GoodpointAI (GraphTrace) - PLM Data Migration & Lineage Platform  
**Date**: May 26, 2026  
**Architecture Type**: React + FastAPI + PostgreSQL + Neo4j (Full-Stack)

---

## Executive Summary

GoodpointAI is a sophisticated full-stack, local-first data lineage and PLM (Product Lifecycle Management) migration platform. It comprises:

- **Frontend**: Modern React 19 + Vite SPA with graph visualization (Cytoscape, ECharts, ReactFlow)
- **Backend**: Modular FastAPI microservices architecture with agentic orchestration
- **Data Persistence**: PostgreSQL (primary), Neo4j (lineage graph), OpenSearch (optional search)
- **Deployment**: Windows-first, containerizable, supports multi-database source integration

The system emphasizes **data lineage tracking**, **ETL workflow orchestration**, **quality monitoring**, and **intelligent agent-based migration** for enterprise PLM systems (Teamcenter, Windchill, etc.).

---

## 1. TECHNOLOGY STACK

### 1.1 Frontend Technology Stack

**Location**: [e2etraceapp/](e2etraceapp/)

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Runtime** | Node.js | 18+ | JavaScript runtime |
| **Framework** | React | 19.1.0 | UI framework |
| **Build Tool** | Vite | 6.3.5 | Fast module bundling |
| **Routing** | React Router DOM | 7.6.2 | Client-side routing |
| **State Management** | Recoil | 0.7.7 | Atomic state management |
| **Graph Visualization** | Cytoscape | 3.32.0 | Node/edge graph rendering |
| | Cytoscape FCOSE | 2.2.0 | Force-directed layouts |
| | Cytoscape Expand-Collapse | 4.1.1 | Collapsible graph nodes |
| | ReactFlow | 11.11.4 | Alternative flow diagram |
| **Data Visualization** | ECharts | 5.6.0 | Analytics charting |
| | ECharts-for-React | 3.0.2 | React wrapper |
| **File I/O** | read-excel-file | 6.0.1 | Excel import |
| | write-excel-file | 2.3.10 | Excel export |
| | file-saver | 2.0.5 | File download utilities |
| **Internationalization** | i18next | 25.7.3 | Multi-language support |
| | react-i18next | 16.5.0 | React i18n integration |
| **HTML Sanitization** | DOMPurify | 3.4.5 | XSS prevention |
| **Tooltips** | Tippy.js | 6.3.7 | Floating tooltips |
| **Testing** | Vitest | 4.0.13 | Unit test runner |
| | @testing-library/react | 16.3.0 | Component testing |
| **Linting** | ESLint | 9.25.0 | Code quality |

**Key Dependencies**:
```json
{
  "cytoscape": "^3.32.0",
  "cytoscape-fcose": "^2.2.0",
  "reactflow": "^11.11.4",
  "echarts": "^5.6.0",
  "recoil": "^0.7.7",
  "react-router-dom": "^7.6.2"
}
```

### 1.2 Backend Technology Stack

**Location**: [python_backend/](python_backend/)

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Runtime** | Python | 3.11+ (3.12 rec.) | Backend runtime |
| **Framework** | FastAPI | 0.115.0 | Modern async web framework |
| **ASGI Server** | Uvicorn | 0.32.0 | ASGI server with reloading |
| **Database ORM** | SQLAlchemy | 2.0.35 | Python ORM |
| **Migrations** | Alembic | 1.13.1 | Database versioning |
| **PostgreSQL Driver** | psycopg[binary] | 3.2.3 | SQLAlchemy driver |
| | asyncpg | 0.30.0 | Async Postgres driver |
| **Graph DB Driver** | neo4j | 5.25.0 | Neo4j connector |
| **Search Engine** | opensearch-py | 3.1.0 | OpenSearch client |
| **Configuration** | pydantic | 2.7.0+ | Data validation |
| | pydantic-settings | 2.6.0+ | Config management |
| | python-dotenv | 1.0.1+ | .env file loading |
| **Data Validation** | jsonschema | 4.21.1+ | JSON schema |
| **File Formats** | openpyxl | 3.1.5+ | Excel reading/writing |
| | lxml | 5.3.0+ | XML parsing |
| | xmlschema | 3.4.3+ | XML schema validation |
| | xmltodict | 0.13.0+ | XML-to-dict conversion |
| **Numeric Processing** | numpy | 1.24+ (< 2.2) | Array operations |
| **NoSQL** | pymongo | 4.10.1 | MongoDB client |
| | redis | 5.1.1 | Redis cache |
| **Data Source Adapters** | oracledb | 2.0.0+ | Oracle connectivity |
| | pyodbc | 5.0.0+ | SQL Server/ODBC |

**Core Dependencies**:
```python
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.35
alembic==1.13.1
psycopg[binary]==3.2.3
asyncpg==0.30.0
neo4j==5.25.0
opensearch-py==3.1.0
pydantic>=2.7.0
```

### 1.3 Database Stack

| Database | Version | Role |
|----------|---------|------|
| **PostgreSQL** | 14+ | Primary persistence (required) |
| **Neo4j** | 5.x | Lineage graph (optional) |
| **OpenSearch** | Latest | Full-text search (optional) |
| **Oracle/SQL Server** | Via adapters | Data source connectors |

---

## 2. FRONTEND ARCHITECTURE

### 2.1 Directory Structure

```
e2etraceapp/
├── src/
│   ├── e2etrace-main.jsx              # React root entry point
│   ├── App.jsx                         # Main app component
│   ├── e2etrace-global.css            # Global styles
│   ├── api/
│   │   └── e2etrace-api.js            # API fetch wrapper with retry logic
│   ├── components/                     # Reusable React components
│   │   ├── e2etrace-data-table.jsx    # Data grid display
│   │   ├── e2etrace-advanced-search.jsx
│   │   ├── e2etrace-graph-toolbar.jsx # Graph visualization controls
│   │   ├── migration-wizard/          # Multi-step migration UI
│   │   ├── RuleEngineManagement.jsx   # Rule engine UI
│   │   └── xstate-visualizer/         # State machine visualization
│   ├── config/
│   │   └── api-config.js              # API endpoint configuration
│   ├── contexts/                       # React context providers
│   │   ├── e2etrace-theme-context.jsx # Theme/styling
│   │   ├── e2etrace-layout-context.jsx
│   │   └── e2etrace-graph-filter-context.jsx
│   ├── hooks/                          # Custom React hooks
│   ├── pages/                          # Route page components
│   │   ├── analytics/                 # Analytics dashboard
│   │   ├── dashboard/                 # Main dashboard
│   │   ├── graph-explorer/            # Neo4j graph viewer
│   │   ├── lineage/                   # Data lineage UI
│   │   ├── migration/                 # Migration workflow
│   │   ├── rule-engine/               # Rule management
│   │   ├── search/                    # Search interface
│   │   ├── settings/                  # Application settings
│   │   └── workflow-manager/          # Workflow orchestration
│   ├── services/                       # Business logic layer
│   │   ├── neo4j-data-service.js      # Neo4j queries
│   │   ├── GraphIntegrationService.js # Graph operations
│   │   ├── etl-workflow-service.js    # ETL orchestration
│   │   ├── workflow-service.js        # Workflow management
│   │   ├── etl-engine.js              # ETL engine
│   │   └── agentic-orchestrator.js    # Agent coordination
│   ├── routes/                         # React Router definitions
│   ├── i18n/                           # Internationalization
│   └── utils/                          # Utility functions
├── public/                             # Static assets
├── vite.config.js                      # Vite build configuration
├── vitest.config.js                    # Unit test configuration
└── package.json                        # Dependencies
```

### 2.2 Key Frontend Components & Pages

| Component | Purpose | Tech Stack |
|-----------|---------|-----------|
| **GraphExplorer** | Neo4j lineage visualization | Cytoscape, ECharts |
| **MigrationPage** | ETL workflow UI | Wizard pattern, State machine |
| **AnalyticsDashboard** | KPI visualization | ECharts, React components |
| **DataTable** | Results grid display | React Table |
| **RuleEngine** | Business rule management | React forms |
| **AdvancedSearch** | Full-text search UI | Search service |
| **ConversationalSearch** | Chat-based querying | Agentic service |
| **WorkflowProgress** | Async task tracking | WebSocket/polling |

### 2.3 Frontend State Management

**Provider Hierarchy** ([e2etrace-main.jsx](e2etraceapp/src/e2etrace-main.jsx#L1)):

```
ErrorBoundary
  └─ E2ETraceThemeProvider (theme context)
      └─ E2ETraceLayoutProvider (layout context)
          └─ GraphFilterProvider (graph filters)
              └─ RouterProvider (React Router)
                  └─ ToastContainer (notifications)
```

**State Sources**:
- **Recoil atoms**: Global UI state, graph filters, selections
- **React Context**: Theme, layout, authentication
- **URL state**: React Router for page navigation (hash-based routing)
- **Local fetch**: Per-component async state

### 2.4 API Integration

**Configuration** ([config/api-config.js](e2etraceapp/src/config/)):

```javascript
const API_CONFIG = {
  API_BASE_URL: 'http://127.0.0.1:8011/api',
  API_TIMEOUT: 30000,
  API_RETRY_ATTEMPTS: 3,
  API_RETRY_DELAY: 1000,
  ENDPOINTS: {
    GRAPH: '/graph',
    ANALYTICS: '/analytics',
    MIGRATION_PLANS: '/migration/plans',
    DATA_MAPPING: '/data-mapping',
    // ... ~40+ endpoints
  }
}
```

**Fetch Strategy** ([e2etrace-api.js](e2etraceapp/src/api/)):
- Retry mechanism with exponential backoff
- Automatic error handling (non-retryable 4xx vs retryable 5xx)
- Centralized timeout configuration
- JSON content type defaults

---

## 3. BACKEND ARCHITECTURE

### 3.1 Backend Directory Structure

```
python_backend/
├── main.py                            # FastAPI app initialization & router registration
├── core/
│   ├── database.py                    # SQLAlchemy Base & session config
│   ├── config.py                      # Config constants (Neo4j, env vars)
│   ├── config_store.py                # Encrypted config persistence
│   ├── auth.py                        # JWT/API key auth & principals
│   ├── db_session.py                  # Database session factory
│   ├── postgres_config.py             # Postgres URL parsing/normalization
│   ├── lifespan.py                    # App startup/shutdown lifecycle
│   ├── security_middleware.py         # Rate limiting, API key enforcement
│   ├── error_handlers.py              # Global exception handlers
│   └── agentic_config_manager.py      # Agent configuration
├── models/                            # SQLAlchemy ORM models
│   ├── configuration_models.py        # Admin config, feature flags
│   ├── graphql_models.py              # GraphQL query persistence
│   ├── workflow_models.py             # Workflow instances
│   ├── plm_models.py                  # PLM ETL (Parts, BOMs, runs)
│   ├── quality_models.py              # Data quality reports
│   ├── report_models.py               # Reporting
│   ├── rule_engine_models.py          # Business rules
│   ├── admin_config_models.py         # Admin settings
│   └── pipeline_config_models.py      # Pipeline definitions
├── graph_api/                         # FastAPI routers (API endpoints)
│   ├── router.py                      # Primary graph query router
│   ├── models.py                      # Pydantic request/response models
│   ├── dependencies.py                # Dependency injection (Neo4j driver)
│   ├── helpers.py                     # Neo4j query helpers
│   ├── neo4j_json.py                  # JSON sanitization
│   ├── [X]_router.py                  # 25+ domain-specific routers:
│   │   ├── agentic_router.py          # Agent orchestration
│   │   ├── analytics_router.py        # Analytics endpoints
│   │   ├── auth_router.py             # Authentication
│   │   ├── data_mapping_router.py     # Data mapping
│   │   ├── etl_router.py              # ETL metrics
│   │   ├── migration_router.py        # Migration workflows
│   │   ├── neo4j_graphrag_router.py   # GraphRAG features
│   │   ├── plm_workflow_router.py     # PLM workflows
│   │   ├── reporting_services.py      # Reporting
│   │   ├── lineage_router.py          # Data lineage
│   │   ├── graphql_router.py          # GraphQL API
│   │   ├── rule_engine_router.py      # Rule management
│   │   ├── quality_router.py          # Data quality
│   │   ├── opensearch_router.py       # Search
│   │   ├── workflow_manager_router.py # Workflow orchestration
│   │   ├── azure_integration_router.py
│   │   ├── aws_integration_router.py
│   │   ├── llm_integration_router.py
│   │   └── ...and more
│   └── database_adapters/             # Multi-DB connectors
│       ├── oracle_adapter.py
│       ├── sqlserver_adapter.py
│       ├── excel_adapter.py
│       └── postgresql_adapter.py
├── routers/                           # Additional routers
│   ├── pipeline_config_router.py      # Pipeline configuration
│   ├── admin_config_router.py         # Admin configuration
│   └── conversational_search_router.py # Conversational search
├── services/                          # Business logic layer
│   ├── neo4j_graphrag_service.py      # GraphRAG with Neo4j
│   ├── graphql_service.py             # GraphQL execution
│   ├── graphql_catalogue_service.py   # Schema catalogue
│   ├── rule_engine.py                 # Rule execution
│   ├── opensearch_service.py          # Search indexing
│   ├── admin_config_service.py        # Config management
│   ├── advanced_migration_engine.py   # Advanced migrations
│   └── analytics_storage_service.py   # Analytics persistence
├── scripts/                           # Utility scripts
│   └── seed_db_config.py              # Initialize DB with defaults
├── tools/                             # Utility tools
├── fixtures/                          # Test fixtures
└── tests/                             # Pytest test suite
```

### 3.2 FastAPI Application Structure

**Main Application Entry** ([main.py](python_backend/main.py#L1-L60)):

```python
app = FastAPI(
    title="GraphTrace API",
    description="PLM Data Migration & Lineage Platform"
)

# Middleware stack (order matters)
- CORSMiddleware                       # Cross-origin requests
- SecurityMiddleware                   # API key, rate limiting
- ErrorHandlers                        # Global exception handling

# Router Registration (25+ routers)
- /api/graph                           # Core Neo4j queries
- /api/agentic                         # Agent orchestration
- /api/analytics                       # Analytics
- /api/auth                            # Authentication
- /api/data-mapping                    # Data mapping
- /api/etl                             # ETL operations
- /api/migration                       # Migrations
- /api/lineage                         # Lineage tracking
- /api/graphql                         # GraphQL API
- /api/rule-engine                     # Rules
- /api/quality                         # Data quality
- /api/opensearch                      # Search
- /api/workflow-manager                # Workflows
- /api/azure-integration                # Azure cloud
- /api/aws-integration                  # AWS cloud
- /api/llm-integration                  # LLM features
- ... and 10+ more
```

**Lifecycle Management** ([core/lifespan.py](python_backend/core/lifespan.py)):

```python
@asynccontextmanager
async def lifespan_manager(app: FastAPI):
    # Startup
    - Initialize Neo4j AsyncDriver
    - Initialize PostgreSQL connection pools
    - Load encrypted configuration
    - Start background tasks
    
    yield  # App runs
    
    # Shutdown
    - Close Neo4j driver
    - Close database connections
    - Cleanup resources
```

### 3.3 Key Router Categories

| Router | Purpose | Key Endpoints |
|--------|---------|---------------|
| **graph_router** | Core lineage | GET /api/graph, POST /api/custom-query |
| **agentic_router** | Agent coordination | POST /api/agentic/task, GET /api/agentic/status |
| **analytics_router** | KPI analytics | GET /api/analytics, GET /api/analytics/nodes |
| **migration_router** | Migration workflows | POST /api/migration/plans, POST /api/migration/execute |
| **plm_workflow_router** | PLM orchestration | POST /api/plm/workflow, GET /api/plm/status |
| **data_mapping_router** | Field mapping | POST /api/data-mapping, GET /api/data-mapping/rules |
| **rule_engine_router** | Business rules | POST /api/rules, POST /api/rules/validate |
| **quality_router** | Data quality | GET /api/quality/metrics, POST /api/quality/scan |
| **graphql_router** | GraphQL endpoint | POST /api/graphql (query execution) |
| **workflow_manager_router** | Workflow CRUD | POST /api/workflows, GET /api/workflows/:id |
| **opensearch_router** | Search indexing | POST /api/search/index, GET /api/search/query |
| **auth_router** | Authentication | POST /api/auth/login, POST /api/auth/token |

### 3.4 Authentication & Authorization

**Location**: [core/auth.py](python_backend/core/auth.py)

**Authentication Methods**:
1. **JWT Tokens** (default)
   - Issued via `/api/auth/login`
   - Validated on each protected endpoint
   - Configurable expiration (default 60 min)

2. **API Keys**
   - Static keys via environment variable
   - Header: `X-API-Key`

3. **Admin Credentials**
   - Username/password for initial setup
   - Support for bcrypt-hashed passwords (production)
   - Plain-text fallback (dev only, non-production)

**Authorization**:
- Role-based access control (RBAC)
- Roles stored in JWT payload
- Example: `require_admin()` checks for "admin" role

```python
@dataclass(frozen=True)
class AuthPrincipal:
    subject: str           # User ID
    roles: tuple[str, ...]  # ["admin", "analyst"]
    auth_type: str         # "jwt" | "api_key"
```

### 3.5 Security Middleware

**Location**: [core/security_middleware.py](python_backend/core/security_middleware.py)

**Features**:
- **In-Memory Rate Limiter**: Configurable requests/window
- **API Key Enforcement**: Optional global or per-endpoint
- **CORS Configuration**: Dynamic origin expansion for localhost variants
- **Request Validation**: Validates JWT on entry

**Middleware Stack**:
```
Request → CORS → RateLimiter → APIKeyAuth → Router → Response
```

---

## 4. DATA LAYER ARCHITECTURE

### 4.1 Database Persistence Model

**PostgreSQL** (Primary, Required)

Role:
- Application state persistence
- Configuration storage (encrypted)
- Workflow history & execution logs
- ETL run metadata
- Report generation

**Key Tables**:

| Table | Purpose | Module |
|-------|---------|--------|
| `workflow_instances` | ETL workflow definitions & state | [workflow_models.py](python_backend/models/workflow_models.py) |
| `plm_ingestion_runs` | PLM ETL run metadata | [plm_models.py](python_backend/models/plm_models.py) |
| `plm_staged_records` | Raw PLM payloads | [plm_models.py](python_backend/models/plm_models.py) |
| `plm_parts` | Extracted part master data | [plm_models.py](python_backend/models/plm_models.py) |
| `plm_bom_items` | Bill of materials relationships | [plm_models.py](python_backend/models/plm_models.py) |
| `data_quality_scan_reports` | DQ scan results | [quality_models.py](python_backend/models/quality_models.py) |
| `persisted_graphql_queries` | Saved GraphQL queries | [graphql_models.py](python_backend/models/graphql_models.py) |
| `schema_cache` | Introspected schema cache | [graphql_models.py](python_backend/models/graphql_models.py) |
| `business_rules` | Rule engine rules | [rule_engine_models.py](python_backend/models/rule_engine_models.py) |
| `encrypted_admin_config` | Encrypted configuration | [configuration_models.py](python_backend/models/configuration_models.py) |

**SQLAlchemy ORM**:
```python
from sqlalchemy.orm import declarative_base
Base = declarative_base()  # [core/database.py](python_backend/core/database.py)

# All models inherit Base
class WorkflowInstance(Base):
    __tablename__ = "workflow_instances"
    # Columns...
```

**Connection Management**:
```python
DATABASE_URL = "postgresql://user:pass@localhost:5432/graphtrace"

# SQLAlchemy session factory
SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[Session, None]:
    async with SessionLocal() as session:
        yield session
```

### 4.2 Neo4j Graph Database

**Role**: Data lineage & graph structure

**Used For**:
- **Nodes**: Data entities (files, tables, APIs, transformations)
- **Relationships**: Data flow (EXTRACTS, FEEDS, TRANSFORMS, PUBLISHES)
- **Properties**: Entity metadata (name, type, source system)

**Key Query Endpoints**:
- `GET /api/graph` → Default lineage graph
- `POST /api/custom-query` → Cypher query execution
- `GET /api/lineage` → Lineage-specific queries

**Driver Setup** ([core/config.py](python_backend/core/config.py)):

```python
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

driver = neo4j.AsyncDriver(
    uri=NEO4J_URI,
    auth=(NEO4J_USER, NEO4J_PASSWORD),
    max_pool_size=50,
    connection_acquisition_timeout=30.0
)
```

**Example Lineage Query** ([graph_api/router.py](python_backend/graph_api/router.py#L20)):

```cypher
MATCH (n) 
OPTIONAL MATCH (n)-[r]-(m) 
RETURN n, r, m
```

**Response Format** (Pydantic):
```python
class NodeModel(BaseModel):
    id: str
    label: str
    group: str
    properties: Dict[str, Any]
    title: str

class EdgeModel(BaseModel):
    id: str
    from_node: str  # from
    to_node: str    # to
    label: str
    properties: Dict[str, Any]

class GraphDataResponse(BaseModel):
    nodes: List[NodeModel]
    edges: List[EdgeModel]
    rawRecords: List[RawRecordModel]
```

### 4.3 OpenSearch Integration (Optional)

**Role**: Full-text search & indexing

**Service**: [services/opensearch_service.py](python_backend/services/opensearch_service.py)

**Router**: [graph_api/opensearch_router.py](python_backend/graph_api/opensearch_router.py)

**Features**:
- Index PLM data for search
- Aggregations and faceted search
- Integration with quality reports

---

## 5. INTEGRATION POINTS & DATA FLOW

### 5.1 Frontend-to-Backend Integration

**HTTP Request Flow**:

```
React Component
    ↓
[e2etrace-api.js] (fetch wrapper)
    ↓
[e2etrace-api.js#e2etraceFetchWithRetry] (retry logic)
    ↓
{API_BASE_URL}/api/{endpoint}
    ↓
FastAPI Router (HTTP 1.1 / WebSocket)
    ↓
[core/security_middleware.py] (auth, rate limit)
    ↓
Route Handler
    ↓
Service Layer / Database Query
    ↓
Response (JSON)
    ↓
React State Update
```

**Example: Migration Workflow**

```javascript
// Frontend initiates
POST /api/migration/plans { name, source, target }

// Backend processes
├─ [migration_router.py#create_migration_plan]
├─ Store in WorkflowInstance table
├─ Trigger agentic orchestration
└─ Return plan ID

// Frontend polls progress
GET /api/migration/plans/{planId}/status

// Returns execution state
```

### 5.2 Backend Orchestration Flow

**Agentic Orchestration** ([graph_api/agentic_router.py](python_backend/graph_api/agentic_router.py)):

```
User Request → /api/agentic/task
    ↓
[AgenticOrchestrator] creates task
    ↓
Route to agent type:
├─ DataAnalystAgent      → Analyze patterns
├─ ETLOrchestratorAgent → Coordinate pipelines
├─ QueryPlannerAgent    → Optimize queries
├─ VisualizationAgent   → Render graphs
├─ QualityMonitorAgent  → DQ checks
└─ ChatCoordinator      → Chat processing
    ↓
Execute capabilities
    ↓
Store result in task_results dict
    ↓
Return AgenticTaskResult
```

**Agent Definitions**:
```python
class AgentType(str, Enum):
    DATA_ANALYST = "data_analyst"
    ETL_ORCHESTRATOR = "etl_orchestrator"
    QUERY_PLANNER = "query_planner"
    VISUALIZATION_AGENT = "visualization_agent"
    QUALITY_MONITOR = "quality_monitor"
    CHAT_COORDINATOR = "chat_coordinator"
```

### 5.3 PLM ETL Pipeline

**Flow**: PLM System → Python Backend → PostgreSQL + Neo4j

```
User initiates migration
    ↓
[migration_router.py#execute_migration]
    ↓
[advanced_migration_engine.py#execute_pipeline]
    ↓
Stage 1: Extract
    ├─ Connect to source system (Teamcenter, Windchill, etc.)
    ├─ Query PLM API or file system
    └─ Store raw payload in plm_staged_records
    ↓
Stage 2: Transform
    ├─ Parse and normalize payload
    ├─ Extract Part → plm_parts
    ├─ Extract BOM → plm_bom_items
    └─ Store reference metadata in plm_ingestion_runs
    ↓
Stage 3: Validate
    ├─ Run quality rules
    ├─ Check business constraints
    └─ Report issues in data_quality_scan_reports
    ↓
Stage 4: Load
    ├─ Write canonical form to target (Neo4j/OpenSearch)
    └─ Update workflow_instances status
    ↓
Stage 5: Lineage
    └─ Create nodes/edges in Neo4j for data flow tracking
```

**Database Adapters** ([graph_api/database_adapters/](python_backend/graph_api/database_adapters/)):

| Adapter | Source System | Location |
|---------|--------------|----------|
| Oracle | Oracle DB | [oracle_adapter.py](python_backend/graph_api/database_adapters/oracle_adapter.py) |
| SQL Server | SQL Server DB | [sqlserver_adapter.py](python_backend/graph_api/database_adapters/sqlserver_adapter.py) |
| Excel | Excel files | [excel_adapter.py](python_backend/graph_api/database_adapters/excel_adapter.py) |
| PostgreSQL | PostgreSQL DB | [postgresql_adapter.py](python_backend/graph_api/database_adapters/postgresql_adapter.py) |

### 5.4 Data Quality Workflow

```
[quality_router.py#scan_data]
    ↓
Load quality rules from rule_engine_models
    ↓
Execute Soda framework checks
    ├─ Row count validations
    ├─ Column validations
    ├─ Uniqueness checks
    ├─ Referential integrity
    └─ Custom SQL rules
    ↓
Store results in data_quality_scan_reports
    ↓
Classify issues (critical, warning, info)
    ↓
Trigger notifications if critical
    ↓
[quality_router.py#get_quality_metrics] returns summary
```

### 5.5 Analytics & Reporting

**Analytics Service**: [services/analytics_storage_service.py](python_backend/services/analytics_storage_service.py)

**Flow**:
```
[analytics_router.py#get_data_analytics]
    ↓
Query Neo4j for graph statistics
    ├─ Node counts by type
    ├─ Relationship density
    ├─ Path depths
    └─ Component analysis
    ↓
Query PostgreSQL for historical metrics
    ├─ Workflow success rates
    ├─ Data quality trends
    ├─ ETL performance
    └─ Cost per record
    ↓
Aggregate and transform
    ↓
Return JSON to frontend
    ↓
Frontend renders ECharts visualizations
```

---

## 6. SECURITY ARCHITECTURE

### 6.1 Authentication Mechanisms

**Environment Variables** ([core/auth.py](python_backend/core/auth.py#L1-L50)):

```python
# JWT Configuration
GRAPH_TRACE_JWT_SECRET       # JWT signing key
GRAPH_TRACE_JWT_ALGORITHM    # Default: HS256

# Admin Credentials
GRAPH_TRACE_ADMIN_USERNAME   # Default: "admin"
GRAPH_TRACE_ADMIN_PASSWORD   # Plain-text (dev only)
GRAPH_TRACE_ADMIN_PASSWORD_HASH  # bcrypt hash (production)

# Auth Enforcement
GRAPH_TRACE_AUTH_REQUIRED    # Enable/disable auth globally
GRAPH_TRACE_API_KEY          # Static API key alternative

# Production Detection
ENVIRONMENT / GRAPH_TRACE_ENVIRONMENT  # "production" or "dev"
```

### 6.2 API Key & Rate Limiting

**Rate Limiter** ([core/security_middleware.py](python_backend/core/security_middleware.py)):

```python
class InMemoryRateLimiter:
    - Tracks requests per client IP
    - Configurable requests/second
    - Automatic TTL cleanup
    - Returns 429 on limit exceeded
```

### 6.3 Encryption at Rest (Optional)

**Encrypted Config Storage** ([core/config_store.py](python_backend/core/config_store.py)):

```python
# Encryption key file
.graphtrace.encryption_key

# Encrypted fields in DB
- Database credentials
- API keys
- OAuth tokens
- Custom data source credentials
```

### 6.4 CORS Policy

**Dynamic Localhost Expansion** ([main.py](python_backend/main.py#L200-L220)):

```python
# Expands localhost variants to prevent CORS failures
http://localhost:5173
http://127.0.0.1:5173
http://[::1]:5173

# Can be overridden via config
GRAPH_TRACE_CORS_ORIGINS=http://prod-ui.example.com
```

---

## 7. KEY FEATURES & COMPONENTS

### 7.1 Core Feature Modules

| Feature | Router | Service | Purpose |
|---------|--------|---------|---------|
| **Graph Lineage** | graph_router | - | Display data flow relationships |
| **PLM Migration** | migration_router | advanced_migration_engine.py | Execute PLM workflows |
| **Data Mapping** | data_mapping_router | - | Field-level mapping definitions |
| **Rule Engine** | rule_engine_router | rule_engine.py | Business rule validation |
| **Data Quality** | quality_router | - | DQ scanning & reporting |
| **Analytics** | analytics_router | analytics_storage_service.py | KPI dashboards |
| **Reporting** | reports_router | - | Report generation & export |
| **GraphQL** | graphql_router | graphql_service.py | Alternative query interface |
| **Workflow Mgmt** | workflow_manager_router | - | Workflow CRUD & status tracking |
| **Agentic Orchestration** | agentic_router | - | Multi-agent task coordination |
| **Chat/Search** | conversational_search_router | - | Conversational data queries |
| **Integration** | azure_integration_router, aws_integration_router, llm_integration_router | - | Cloud & LLM connectors |

### 7.2 Configuration & State

**Admin Configuration** ([routers/admin_config_router.py](python_backend/routers/admin_config_router.py)):

```python
# Configurable via UI
{
  "deployment": {
    "auto_deploy": true,
    "deployment_strategy": "progressive",
    "install_types": ["all"],
    "verification_level": "comprehensive"
  },
  "security": {
    "encryption": {
      "encrypt_at_rest": false,
      "encrypt_in_transit": true
    },
    "access_control": {
      "enable_rbac": false,
      "require_mfa": false
    }
  },
  "agentic_orchestration": {
    "enabled": true,
    "orchestration_mode": "intelligent"
  }
}
```

### 7.3 Workflow State Machine

**States** ([models/workflow_models.py](python_backend/models/workflow_models.py)):

```python
class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    CONFIGURED = "configured"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkflowStage(str, Enum):
    IDLE = "idle"
    EXTRACTING = "extracting"
    TRANSFORMING = "transforming"
    VALIDATING = "validating"
    LOADING = "loading"
    FINALIZING = "finalizing"
```

---

## 8. DEPLOYMENT & EXECUTION

### 8.1 Local Development Execution

**Startup Sequence**:

1. **PostgreSQL**: 
   - Must be running on configured port (default 5432)
   - Create database: `CREATE DATABASE graphtrace;`

2. **Backend**:
   ```powershell
   cd agentic-restored/python_backend
   python -m uvicorn main:app --host 0.0.0.0 --port 8011 --reload
   ```
   - Loads `.env` if `GRAPH_TRACE_LOAD_DOTENV=true`
   - Health endpoint: `http://localhost:8011/health`
   - OpenAPI docs: `http://localhost:8011/docs`

3. **Frontend**:
   ```powershell
   cd agentic-restored/e2etraceapp
   npm install
   npm run dev -- --host 127.0.0.1 --port 5173
   ```
   - Dev proxy: requests to `/api` → `http://127.0.0.1:8011`
   - Opens: `http://localhost:5173`

### 8.2 Available Tasks

**VS Code Workspace Tasks** (`.vscode/tasks.json`):

```
Start Backend Server
Start Frontend Development Server
Start Backend Server (Postgres)
Start Backend Server (OpenSearch)
Start Backend Server (Auth Required)
Start Backend Server (No Reload)
Start Full Stack (Frontend + Backend)
Frontend: Lint
Frontend: Test (Vitest run)
Backend: Test (Pytest)
MCP: Start Inspector
```

### 8.3 Typical User Workflows

**Migration Workflow**:
```
1. Dashboard → http://localhost:5173/#/dashboard
2. Start Migration → http://localhost:5173/#/migration
3. Connect to Source (Oracle, Teamcenter, etc.)
4. Discover Data Entities
5. Map Fields
6. Validate Quality
7. Execute Migration
8. Monitor Progress (WebSocket/polling)
9. Review Analytics → http://localhost:5173/#/analytics
10. Export Reports
```

**GraphQL Query**:
```
POST http://localhost:8011/api/graphql
{
  "query": "query { nodes { id, label, properties } }"
}
```

**Data Quality Scan**:
```
POST http://localhost:8011/api/quality/scan
{
  "source_id": "teamcenter",
  "rules": ["row_count", "uniqueness"]
}
```

---

## 9. TESTING & QUALITY

### 9.1 Frontend Testing

**Framework**: Vitest + React Testing Library

**Test Locations**: [e2etraceapp/tests/](e2etraceapp/tests/)

**Coverage**:
- Component unit tests
- Integration tests for services
- Mock API responses

**Commands**:
```bash
npm test                    # Watch mode
npm test -- --run          # Single run
npm run lint               # ESLint
```

### 9.2 Backend Testing

**Framework**: Pytest

**Test Locations**: [python_backend/tests/](python_backend/tests/)

**Test Files**:
- `test_integration_neo4j_xstate.py` - Workflow + graph integration
- `test_plm_etl_soda_gate_fail_closed.py` - PLM ETL + quality gates
- `test_integration_opensearch_graphrag.py` - Search integration
- `test_quality_report_normalization.py` - Data quality
- `test_postgres_url_detection.py` - Database config
- `test_cors_and_system_config_db.py` - Security + config

**Commands**:
```bash
pytest                     # All tests
pytest -v                  # Verbose
pytest tests/test_*.py::TestClass::test_method  # Specific test
```

---

## 10. ARCHITECTURAL PATTERNS

### 10.1 Design Patterns Used

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Dependency Injection** | [graph_api/dependencies.py](python_backend/graph_api/dependencies.py) | Neo4j driver injection |
| **Context Providers** | [e2etraceapp/src/contexts/](e2etraceapp/src/contexts/) | Theme, layout, filters |
| **Service Layer** | [python_backend/services/](python_backend/services/) | Business logic isolation |
| **Repository Pattern** | ORM models + db_session | Database abstraction |
| **Factory Pattern** | SessionLocal, driver factory | Connection pooling |
| **Observer Pattern** | React hooks, Recoil atoms | State subscriptions |
| **Adapter Pattern** | database_adapters/ | Multi-source connectivity |
| **State Machine** | xstate visualizer | Workflow orchestration |
| **Middleware Chain** | security_middleware | Request pipeline |

### 10.2 Error Handling

**Global Exception Handlers** ([core/error_handlers.py](python_backend/core/error_handlers.py)):

```python
- http_exception_handler      # HTTPException → JSON
- validation_exception_handler # RequestValidationError → 422
- unhandled_exception_handler # Generic exception → 500
```

**Frontend Error Boundaries** ([components/ErrorBoundary.jsx](e2etraceapp/src/components/)):

```jsx
<ErrorBoundary>
  {children}
</ErrorBoundary>
```

---

## 11. PERFORMANCE CHARACTERISTICS

### 11.1 Frontend Performance Optimization

- **Lazy Loading**: Route-based code splitting via React Router
- **Memoization**: React.memo for expensive components
- **State Optimization**: Recoil selectors for computed state
- **Graph Rendering**: Cytoscape with FCOSE for 1000+ nodes
- **Virtualization**: Data table with windowing for large datasets

### 11.2 Backend Performance Tuning

**Neo4j Driver Pool** ([core/config.py](python_backend/core/config.py)):
```python
max_pool_size=50
connection_acquisition_timeout=30.0
connection_timeout=10.0
max_connection_lifetime=3600.0
```

**Database Indexes** ([models/](python_backend/models/)):
- Composite indexes on workflow_instances(source_id, target_id)
- Single indexes on status, timestamps
- Full-text search indexes in OpenSearch

**Async/Await**: All I/O is non-blocking (asyncpg, aiofiles)

---

## 12. EXTERNAL INTEGRATIONS

### 12.1 Cloud Platforms

**Azure Integration** ([graph_api/azure_integration_router.py](python_backend/graph_api/)):
- Authenticate with Azure AD
- Query Azure Data Factory pipelines
- Upload results to Azure Blob Storage

**AWS Integration** ([graph_api/aws_integration_router.py](python_backend/graph_api/)):
- EC2 instance management
- S3 file operations
- Glue job orchestration

### 12.2 PLM Systems

**Adapters** ([graph_api/database_adapters/](python_backend/graph_api/database_adapters/)):
- Teamcenter (REST API)
- Windchill (SOAP API)
- Catia (proprietary format)
- Oracle PLM

### 12.3 LLM Integration

**Router**: [graph_api/llm_integration_router.py](python_backend/graph_api/)

**Supports**:
- OpenAI GPT models
- Local Ollama
- Azure OpenAI
- Custom endpoints

---

## 13. SCALABILITY & LIMITATIONS

### 13.1 Current Constraints

- **Single PostgreSQL instance** (no sharding)
- **Neo4j** scales to ~billions of nodes (optional)
- **OpenSearch** optional; enables horizontal scaling
- **Frontend** SPA (single large bundle for 1000+ nodes can be slow)
- **Rate limiting**: In-memory (loses state on restart)

### 13.2 Horizontal Scaling Opportunities

1. **Postgres replication**: Primary-replica setup
2. **Neo4j cluster**: Enterprise feature
3. **API gateway**: Load-balanced FastAPI instances
4. **S3 backend**: Off-load file storage
5. **Message queue**: Kafka/RabbitMQ for async workflows

---

## 14. CODE ORGANIZATION SUMMARY

### Frontend Directory Structure
```
e2etraceapp/
├── src/
│   ├── api/               # API wrapper & retry logic
│   ├── components/        # 30+ reusable components
│   ├── contexts/          # 3 context providers
│   ├── pages/             # 12 pages/routes
│   ├── services/          # 8 service modules
│   ├── hooks/             # Custom React hooks
│   ├── config/            # Configuration constants
│   ├── utils/             # Utility functions
│   └── styles/            # Global & component CSS
```

### Backend Directory Structure
```
python_backend/
├── core/                  # 11 core modules
├── models/                # 9 Pydantic + SQLAlchemy models
├── graph_api/             # 25+ routers
├── routers/               # 3 additional routers
├── services/              # 8 business services
├── scripts/               # Setup & seed scripts
├── tests/                 # 15+ pytest files
└── tools/                 # Utility tools
```

---

## 15. CRITICAL FILES REFERENCE

### Frontend Critical Files
- [e2etraceapp/package.json](e2etraceapp/package.json) - Dependencies
- [e2etraceapp/vite.config.js](e2etraceapp/vite.config.js) - Build config
- [e2etraceapp/src/e2etrace-main.jsx](e2etraceapp/src/e2etrace-main.jsx) - App entry
- [e2etraceapp/src/api/e2etrace-api.js](e2etraceapp/src/api/e2etrace-api.js) - API wrapper
- [e2etraceapp/src/config/api-config.js](e2etraceapp/src/config/) - API config

### Backend Critical Files
- [python_backend/main.py](python_backend/main.py) - App entry
- [python_backend/core/database.py](python_backend/core/database.py) - ORM base
- [python_backend/core/config.py](python_backend/core/config.py) - Configuration
- [python_backend/core/auth.py](python_backend/core/auth.py) - Authentication
- [python_backend/requirements.txt](python_backend/requirements.txt) - Dependencies
- [python_backend/agentic_config.json](python_backend/agentic_config.json) - Agentic config

### Database & Documentation
- [docs/INSTALLATION.md](docs/INSTALLATION.md) - Setup guide
- [docs/EXECUTION_GUIDE.md](docs/EXECUTION_GUIDE.md) - Runbook
- [python_backend/.env.example](python_backend/.env.example) - Environment template

---

## CONCLUSION

**GoodpointAI** is an enterprise-grade, modular full-stack application that combines:

✅ **Modern Frontend**: React 19 + Vite with advanced graph/data visualization  
✅ **Scalable Backend**: FastAPI with async I/O and 25+ microservices  
✅ **Robust Data Layer**: PostgreSQL + Neo4j + optional OpenSearch  
✅ **Security-First**: JWT/API-key auth, rate limiting, encrypted config  
✅ **Extensible Architecture**: Database adapters, cloud integrations, LLM support  
✅ **Enterprise Features**: Workflow orchestration, data quality, lineage tracking, agentic AI  

The codebase demonstrates clean separation of concerns, comprehensive error handling, and production-ready patterns suitable for PLM migration and data governance at scale.
