# GoodpointAI Architecture Diagrams & Visual Summary

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     GOODPOINTAI SYSTEM DIAGRAM                   │
└─────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────┐
│   FRONTEND LAYER (React 19 + Vite) │
│  http://localhost:5173             │
├────────────────────────────────────┤
│ ▪ Dashboard                         │
│ ▪ Migration Wizard                 │
│ ▪ Graph Explorer (Cytoscape)       │
│ ▪ Analytics (ECharts)              │
│ ▪ Rule Engine                      │
│ ▪ Lineage Viewer                   │
│ ▪ Data Quality Reports             │
│ ▪ Workflow Manager                 │
│ ▪ Conversational Search            │
│ ▪ Admin Configuration              │
└────────────────────────────────────┘
            ↓
    [Vite Dev Server]
    Proxy: /api → :8011
            ↓
┌────────────────────────────────────────────────────────────┐
│  API GATEWAY & MIDDLEWARE LAYER                             │
│  http://localhost:8011                                      │
├────────────────────────────────────────────────────────────┤
│ ▪ CORS Middleware                                           │
│ ▪ Security Middleware (JWT, API Key, Rate Limit)           │
│ ▪ Error Handlers                                            │
│ ▪ Global Request/Response Pipeline                         │
└────────────────────────────────────────────────────────────┘
            ↓
┌────────────────────────────────────────────────────────────┐
│          FASTAPI ROUTER LAYER (25+ Routers)                │
├────────────────────────────────────────────────────────────┤
│ Core Routers:                                               │
│ ├─ /api/graph              → Graph Query Operations         │
│ ├─ /api/agentic            → Agent Orchestration            │
│ ├─ /api/analytics          → KPI Analytics                  │
│ ├─ /api/migration          → Migration Workflows            │
│ ├─ /api/data-mapping       → Field Mapping                  │
│ ├─ /api/etl                → ETL Metrics                    │
│ ├─ /api/quality            → Data Quality Checks            │
│ ├─ /api/rule-engine        → Business Rules                 │
│ ├─ /api/graphql            → GraphQL API                    │
│ ├─ /api/lineage            → Data Lineage                   │
│ ├─ /api/workflow-manager   → Workflow CRUD                  │
│ ├─ /api/auth               → Authentication                 │
│ ├─ /api/opensearch         → Search Indexing                │
│ ├─ /api/azure-integration  → Azure Cloud                    │
│ ├─ /api/aws-integration    → AWS Cloud                      │
│ ├─ /api/llm-integration    → LLM Features                   │
│ └─ ... and 9+ more specialized routers                      │
└────────────────────────────────────────────────────────────┘
            ↓
┌────────────────────────────────────────────────────────────┐
│          SERVICE LAYER (Business Logic)                    │
├────────────────────────────────────────────────────────────┤
│ ▪ neo4j_graphrag_service.py        → GraphRAG              │
│ ▪ graphql_service.py               → GraphQL Execution     │
│ ▪ rule_engine.py                   → Rule Validation       │
│ ▪ opensearch_service.py            → Search Indexing       │
│ ▪ advanced_migration_engine.py     → ETL Orchestration     │
│ ▪ analytics_storage_service.py     → Analytics Metrics     │
│ ▪ admin_config_service.py          → Config Management     │
└────────────────────────────────────────────────────────────┘
            ↓
         ┌──────────────────────────────┐
         │   DATA ACCESS LAYER          │
         ├──────────────────────────────┤
         │ ▪ SQLAlchemy ORM             │
         │ ▪ Async Session Factory      │
         │ ▪ Database Adapters          │
         │ ▪ Query Builders             │
         └──────────────────────────────┘
            ↓  ↓  ↓  ↓
    ┌───────┴──┴──┴──┴─────────┐
    ↓         ↓        ↓        ↓
┌─────────┐ ┌────────┐ ┌──────┐ ┌───────┐
│PostgreSQL│ │ Neo4j │ │OpenS.│ │Oracle/│
│(Required)│ │(Graph)│ │(Opt.)│ │SQL Sr.│
│          │ │       │ │      │ │(Src.) │
│Tables:  │ │Nodes: │ │Index │ │       │
│- Workflows
│- PLM ETL  │ │- Data │ │Full  │ │       │
│- Quality  │ │- ETL  │ │Text  │ │       │
│- Reports  │ │- Edges│ │Search│ │       │
│- Rules    │ │       │ │      │ │       │
│- Config   │ │Rels:  │ │Facets│ │       │
│           │ │EXTRACTS
│           │ │FEEDS   │ │      │ │       │
│           │ │TRANSFORM
│           │ │PUBLISHES
│           │ └────────┘ └──────┘ └───────┘
└─────────┘
```

---

## Data Flow Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│               USER WORKFLOW DATA FLOW                             │
└──────────────────────────────────────────────────────────────────┘

SCENARIO: PLM Migration from Teamcenter → Neo4j

1. INITIATE MIGRATION
   ┌─────────────────────┐
   │ User clicks:        │
   │ "Start Migration"   │
   └────────┬────────────┘
            │
            ↓
   ┌─────────────────────────────────────┐
   │ POST /api/migration/plans           │
   │ {                                   │
   │   "source": "Teamcenter",          │
   │   "target": "Neo4j",               │
   │   "config": { ... }                │
   │ }                                  │
   └────────┬────────────────────────────┘
            │
            ↓
   ┌──────────────────────────────────────────────┐
   │ [migration_router.py]                        │
   │ create_migration_plan()                      │
   └────────┬─────────────────────────────────────┘
            │
            ↓
   ┌──────────────────────────────────────────────┐
   │ [workflow_models.py]                         │
   │ Create WorkflowInstance (status: DRAFT)      │
   │ Store in PostgreSQL                          │
   └────────┬─────────────────────────────────────┘
            │
            ↓
   Return workflow_id to frontend

2. EXECUTE MIGRATION
   ┌─────────────────────┐
   │ User clicks:        │
   │ "Execute"           │
   └────────┬────────────┘
            │
            ↓
   ┌─────────────────────────────────────────────────┐
   │ POST /api/migration/plans/{id}/execute          │
   └────────┬────────────────────────────────────────┘
            │
            ↓ (Enqueue async task)
   ┌──────────────────────────────────────────────────┐
   │ [advanced_migration_engine.py]                   │
   │ _execute_stage():                               │
   │                                                  │
   │ Stage 1: EXTRACT                                │
   │ ├─ Connect to Teamcenter API                    │
   │ ├─ Query parts & BOMs                           │
   │ └─ Store raw payload in plm_staged_records      │
   │                                                  │
   │ Stage 2: TRANSFORM                              │
   │ ├─ Parse XML/JSON payload                       │
   │ ├─ Extract Part → plm_parts table               │
   │ └─ Extract BOM → plm_bom_items table            │
   │                                                  │
   │ Stage 3: VALIDATE                               │
   │ ├─ Run quality rules                            │
   │ ├─ Check referential integrity                  │
   │ └─ Store issues in quality_scan_reports         │
   │                                                  │
   │ Stage 4: LOAD                                   │
   │ ├─ Create nodes in Neo4j                        │
   │ │   CREATE (p:Part {id, name, ...})             │
   │ ├─ Create edges (BOMs)                          │
   │ │   CREATE (p1)-[:CONTAINS]->(p2)               │
   │ └─ Update workflow status: COMPLETED            │
   └──────────────────────────────────────────────────┘
            │
            ↓
   ┌──────────────────────────────────────────────────┐
   │ Store execution results in PostgreSQL:           │
   │ - workflow_instances[status] = COMPLETED        │
   │ - workflow_instances[processed_records] = 5000  │
   │ - workflow_instances[quality_score] = 0.95      │
   └──────────────────────────────────────────────────┘
            │
            ↓
3. MONITOR PROGRESS
   ┌──────────────────────────────────┐
   │ Frontend polls every 2 seconds:   │
   │ GET /api/migration/plans/{id}/status
   │                                  │
   │ Response:                         │
   │ {                                │
   │   "status": "LOADING",           │
   │   "stage": "loading",            │
   │   "progress": 85,                │
   │   "processed": 4250,             │
   │   "total": 5000                  │
   │ }                                │
   └──────────────────────────────────┘

4. VISUALIZE RESULTS
   ┌────────────────────────────────────┐
   │ GET /api/graph                      │
   │ (Fetch lineage from Neo4j)          │
   │                                     │
   │ Response:                           │
   │ {                                   │
   │   "nodes": [                        │
   │     { id: "part-001",               │
   │       label: "Engine Block",        │
   │       group: "Part" },              │
   │     ...                             │
   │   ],                                │
   │   "edges": [                        │
   │     { id: "edge-1",                 │
   │       from: "part-001",             │
   │       to: "part-002",               │
   │       label: "CONTAINS" }           │
   │   ]                                 │
   │ }                                   │
   └────────────────────────────────────┘
            │
            ↓
   ┌────────────────────────────────────┐
   │ Frontend renders:                   │
   │ [Cytoscape Graph Visualization]     │
   │                                     │
   │     Engine Block                    │
   │          |                          │
   │          | CONTAINS                 │
   │          ↓                          │
   │     Transmission                    │
   │          |                          │
   │          | CONTAINS                 │
   │          ↓                          │
   │     Clutch Plate                    │
   └────────────────────────────────────┘
```

---

## Frontend Component Hierarchy

```
┌──────────────────────────────────────────┐
│  React Router (Hash-based)                │
└──────────────────────────────────────────┘
         ↓
    ┌────────────────────────────────┐
    │ <App /> (e2etrace-main.jsx)     │
    └────────┬───────────────────────┘
             ↓
    ┌────────────────────────────────┐
    │ ErrorBoundary                  │
    │  └─ Catches React errors       │
    └────────┬───────────────────────┘
             ↓
    ┌────────────────────────────────┐
    │ E2ETraceThemeProvider          │
    │  └─ Theme Context              │
    └────────┬───────────────────────┘
             ↓
    ┌────────────────────────────────┐
    │ E2ETraceLayoutProvider         │
    │  └─ Layout Context             │
    └────────┬───────────────────────┘
             ↓
    ┌────────────────────────────────┐
    │ GraphFilterProvider            │
    │  └─ Filter Context             │
    └────────┬───────────────────────┘
             ↓
    ┌────────────────────────────────┐
    │ RouterProvider                 │
    │  └─ Route Components:          │
    │     ├─ DashboardPage           │
    │     ├─ MigrationPage           │
    │     ├─ GraphExplorerPage       │
    │     ├─ AnalyticsDashboard      │
    │     ├─ RuleEnginePage          │
    │     ├─ LineagePage             │
    │     ├─ WorkflowManagerPage     │
    │     ├─ SettingsPage            │
    │     └─ ... (12 pages total)    │
    └────────┬───────────────────────┘
             ↓
    ┌────────────────────────────────┐
    │ ToastContainer                 │
    │  └─ Notifications              │
    └────────────────────────────────┘

COMPONENT COMPOSITION EXAMPLE:

    <MigrationPage>
    ├─ <MigrationWizard>
    │  ├─ <Step1_Connect>
    │  │  └─ <DataSourceSelector>
    │  ├─ <Step2_Discover>
    │  │  └─ <ProgressBar>
    │  ├─ <Step3_Map>
    │  │  └─ <MappingTable>
    │  ├─ <Step4_Validate>
    │  │  └─ <DataQualityReport>
    │  └─ <Step5_Execute>
    │     ├─ <ExecuteButton>
    │     └─ <WorkflowProgress>
    └─ <ToastNotifications>
```

---

## Backend Request Pipeline

```
┌─────────────────────────────────────────────────────────┐
│  HTTP REQUEST → FASTAPI REQUEST PIPELINE               │
└─────────────────────────────────────────────────────────┘

1. REQUEST ARRIVES
   ├─ Method: GET/POST/PUT/DELETE
   ├─ Path: /api/graph
   └─ Headers: Content-Type, Authorization

2. CORS MIDDLEWARE
   ├─ Check origin
   ├─ Expand localhost variants (127.0.0.1 ↔ localhost)
   └─ Allow or reject

3. SECURITY MIDDLEWARE
   ├─ Parse JWT token from Authorization header
   │  └─ If invalid → 401 Unauthorized
   ├─ Or validate API key from X-API-Key header
   │  └─ If invalid → 401 Unauthorized
   ├─ Attach AuthPrincipal to request.state.principal
   └─ Check rate limit
      └─ If exceeded → 429 Too Many Requests

4. DEPENDENCY INJECTION
   ├─ @Depends(get_driver) → Neo4j AsyncDriver
   ├─ @Depends(get_db) → AsyncSession (PostgreSQL)
   └─ @Depends(require_principal) → AuthPrincipal

5. ROUTE HANDLER EXECUTION
   ├─ Input validation (Pydantic models)
   │  └─ If invalid → 422 Unprocessable Entity
   ├─ Business logic (services)
   │  ├─ Query Neo4j
   │  ├─ Query PostgreSQL
   │  └─ Orchestrate agents
   └─ Response model serialization

6. ERROR HANDLING
   ├─ HTTPException
   │  └─ Return custom status + JSON
   ├─ ValidationError
   │  └─ Return 422 + error details
   └─ Unhandled Exception
      └─ Return 500 + error message

7. RESPONSE SENT
   ├─ JSON serialized Pydantic model
   ├─ Status code (200, 201, 400, 401, 404, 500)
   └─ Headers (Content-Type, Access-Control-Allow-*)

EXAMPLE: GET /api/graph

┌─────────────────────────────────────┐
│ @router.get("/graph")               │
│ async def get_graph_data_endpoint(  │
│     driver: neo4j.AsyncDriver       │
│     = Depends(get_driver)           │
│ ):                                  │
│     # Neo4j query                   │
│     session = driver.session()      │
│     result = await session.run(     │
│         "MATCH (n) OPTIONAL MATCH   │
│          (n)-[r]-(m)                │
│          RETURN n, r, m"            │
│     )                               │
│                                     │
│     # Process results               │
│     nodes, edges = process(result)  │
│                                     │
│     # Return response               │
│     return GraphDataResponse(       │
│         nodes=nodes,                │
│         edges=edges                 │
│     )                               │
└─────────────────────────────────────┘
```

---

## Database Schema Overview

```
POSTGRESQL PERSISTENCE MODEL
┌──────────────────────────────────────────────────────────┐

workflow_instances                plm_ingestion_runs
├─ id (PK)                         ├─ id (PK)
├─ name                            ├─ source_system (FK)
├─ description                     ├─ target_system (FK)
├─ source_id (FK)                  ├─ status
├─ source_type                     └─ created_at
├─ source_config (JSON)
├─ target_id (FK)            plm_staged_records
├─ target_type                     ├─ id (PK)
├─ target_config (JSON)            ├─ run_id (FK)
├─ status (ENUM)                   ├─ object_type
├─ current_stage (ENUM)            ├─ payload (JSON)
├─ progress_percentage              └─ source_object_id
├─ processed_records
├─ failed_records             plm_parts
├─ quality_score                   ├─ id (PK)
├─ created_at                      ├─ run_id (FK)
└─ ...timestamps...                ├─ part_number (UNIQUE)
                                   ├─ name
                              plm_bom_items
                                   ├─ id (PK)
                                   ├─ run_id (FK)
                                   ├─ parent_part_number
                                   ├─ child_part_number
                                   └─ quantity

data_quality_scan_reports    business_rules
├─ id (PK)                         ├─ id (PK)
├─ run_id (FK)                     ├─ name
├─ scan_type                       ├─ rule_definition (JSON)
├─ report (JSON)                   ├─ severity
├─ issues_found                    └─ created_at
└─ scan_date

encrypted_admin_config       persisted_graphql_queries
├─ id (PK)                         ├─ id (PK)
├─ key                             ├─ name (UNIQUE)
├─ value (ENCRYPTED)               ├─ query (TEXT)
├─ created_at                      ├─ variables (JSON)
└─ updated_at                      └─ tags (JSON)

NEO4J GRAPH MODEL
┌──────────────────────────────────────────────────────────┐

Nodes:
├─ :Part { id, name, number, classification, ... }
├─ :Database { id, name, type, connection_string, ... }
├─ :File { id, name, path, format, ... }
├─ :Transformation { id, name, type, ... }
├─ :API { id, name, endpoint, ... }
└─ :System { id, name, version, ... }

Relationships:
├─ (Database)-[:EXTRACTS]->(File)
│   Properties: { date, row_count, frequency }
├─ (File)-[:FEEDS]->(Transformation)
│   Properties: { sequence, format }
├─ (Transformation)-[:PUBLISHES]->(API)
│   Properties: { latency, throughput }
├─ (Part)-[:CONTAINS]->(Part)
│   Properties: { quantity, position }
├─ (Part)-[:COMPATIBLE_WITH]->(Part)
└─ (System)-[:CONNECTED_TO]->(Database)
   Properties: { connection_type, auth_method }
```

---

## Authentication & Authorization Flow

```
┌──────────────────────────────────────────────┐
│  AUTHENTICATION & AUTHORIZATION FLOW          │
└──────────────────────────────────────────────┘

SCENARIO 1: JWT LOGIN
┌─────────────────────────────────────────────┐
│ POST /api/auth/login                        │
│ {                                           │
│   "username": "admin",                      │
│   "password": "secret"                      │
│ }                                           │
└────────┬────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────┐
│ [auth_router.py] login_endpoint()           │
│                                             │
│ 1. Verify admin credentials                 │
│    └─ Check GRAPH_TRACE_ADMIN_PASSWORD    │
│       or GRAPH_TRACE_ADMIN_PASSWORD_HASH  │
│                                             │
│ 2. Create JWT token                         │
│    └─ Payload:                              │
│       {                                     │
│         "sub": "admin",                     │
│         "roles": ["admin"],                 │
│         "iat": 1234567890,                  │
│         "exp": 1234571490                   │
│       }                                     │
│                                             │
│ 3. Return token                             │
└────────┬────────────────────────────────────┘
         │
         ↓
┌──────────────────────────────────────────────────┐
│ Response:                                        │
│ {                                                │
│   "access_token": "eyJhbGciOiJIUzI1NiIs...",  │
│   "token_type": "bearer"                        │
│ }                                                │
└────────┬──────────────────────────────────────────┘
         │
         ↓
Frontend stores token in localStorage

SCENARIO 2: PROTECTED REQUEST
┌─────────────────────────────────────────────┐
│ GET /api/workflow-manager/workflows         │
│ Headers:                                    │
│   Authorization: Bearer eyJhbGciOiJIUzI1...│
└────────┬────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────┐
│ [security_middleware.py]                    │
│ enforce_api_key_if_configured()             │
│                                             │
│ 1. Extract token from header                │
│ 2. Decode JWT                               │
│ 3. Create AuthPrincipal:                    │
│    AuthPrincipal(                           │
│      subject="admin",                       │
│      roles=("admin",),                      │
│      auth_type="jwt"                        │
│    )                                        │
│ 4. Attach to request.state.principal        │
└────────┬────────────────────────────────────┘
         │
         ↓
┌─────────────────────────────────────────────┐
│ [workflow_manager_router.py]                │
│ @router.get("/workflows")                   │
│ def get_workflows(                          │
│     principal: AuthPrincipal =              │
│         Depends(require_principal)          │
│ ):                                          │
│     # Check authorization                   │
│     if "analyst" not in principal.roles:    │
│         raise HTTPException(403, "Forbidden")
│                                             │
│     # Execute query                         │
│     workflows = db.query(...).all()         │
│     return workflows                        │
└────────┬────────────────────────────────────┘
         │
         ↓
Response sent to frontend
```

---

## Agentic Orchestration Architecture

```
┌──────────────────────────────────────────────────────┐
│  AGENTIC ORCHESTRATOR FLOW                           │
└──────────────────────────────────────────────────────┘

User Action
    │
    ↓
POST /api/agentic/task
{
  "type": "DATA_ANALYSIS",
  "payload": {
    "query": "Analyze data quality of PLM imports"
  }
}
    │
    ↓
┌──────────────────────────────────────┐
│ [agentic_orchestrator.py]            │
│ AgenticOrchestrator class            │
│                                      │
│ task_queue: List[AgenticTask]        │
│ agents: Dict[AgentType, Agent]       │
│ task_results: Dict[str, Result]      │
│ chat_sessions: Dict[str, History]    │
└────────┬─────────────────────────────┘
         │
         ↓
1. INITIALIZE AGENTS
┌──────────────────────────────────────┐
│ _initialize_agents():                │
│                                      │
│ agents = {                           │
│   DATA_ANALYST: AgentDefinition(     │
│     capabilities=[               │
│       analyze_data_patterns,     │
│       generate_insights,         │
│       data_quality_assessment    │
│     ]                            │
│   ),                             │
│   ETL_ORCHESTRATOR: AgentDef..., │
│   QUERY_PLANNER: AgentDef...,    │
│   ...                            │
│ }                                │
└────────┬─────────────────────────┘
         │
         ↓
2. QUEUE & ROUTE TASK
┌───────────────────────────────────────┐
│ task_queue.append(AgenticTask(        │
│   type=TaskType.DATA_ANALYSIS,       │
│   required_capabilities=[             │
│     "analyze_data_patterns",          │
│     "data_quality_assessment"         │
│   ]                                   │
│ ))                                    │
│                                       │
│ 1. Match capabilities to agents       │
│ 2. Select best agent (by utilization) │
│ 3. Execute task                       │
│ 4. Store result                       │
└────────┬───────────────────────────────┘
         │
         ↓
3. AGENT EXECUTION
┌───────────────────────────────────────┐
│ DATA_ANALYST_AGENT:                   │
│                                       │
│ ├─ Capability: analyze_data_patterns  │
│ │  └─ Query Neo4j for node/edge dist. │
│ │                                     │
│ ├─ Capability: data_quality_check     │
│ │  └─ Query PostgreSQL for DQ reports │
│ │                                     │
│ └─ Compile results                    │
│    └─ {                               │
│      "patterns": {...},               │
│      "quality_score": 0.92,           │
│      "recommendations": [...]         │
│    }                                  │
└────────┬───────────────────────────────┘
         │
         ↓
4. RETURN RESULT
┌───────────────────────────────────────┐
│ AgenticTaskResult {                   │
│   task_id: "task_1234567890",         │
│   agent_id: "DATA_ANALYST",           │
│   agent_type: AgentType.DATA_ANALYST, │
│   success: true,                      │
│   result: { ... },                    │
│   execution_time: 2.45,               │
│   timestamp: datetime.now()           │
│ }                                     │
└────────┬───────────────────────────────┘
         │
         ↓
Frontend receives and displays results
```

---

## Deployment Architecture

```
┌──────────────────────────────────────────────────┐
│  LOCAL DEVELOPMENT DEPLOYMENT                    │
└──────────────────────────────────────────────────┘

HOST MACHINE (Windows 10/11)
├─ PowerShell / Terminal
│  ├─ Terminal 1
│  │  └─ PostgreSQL instance running
│  │     └─ localhost:5432
│  │
│  ├─ Terminal 2
│  │  └─ python -m uvicorn main:app
│  │     ├─ Host: 0.0.0.0
│  │     ├─ Port: 8011
│  │     └─ Reload: enabled
│  │
│  └─ Terminal 3
│     └─ npm run dev
│        ├─ Host: 127.0.0.1
│        ├─ Port: 5173
│        └─ Proxy: /api → :8011
│
└─ Browser
   └─ http://localhost:5173

FILE STRUCTURE ON DISK
d:\Download\GoodpointAI\
├─ agentic-restored/
│  ├─ python_backend/
│  │  ├─ .env (DATABASE_URL, NEO4J_URI, etc.)
│  │  ├─ main.py
│  │  └─ [other backend files]
│  │
│  └─ e2etraceapp/
│     ├─ .env (VITE_DEV_PROXY_TARGET)
│     ├─ package.json
│     └─ [other frontend files]
│
└─ docs/
   ├─ INSTALLATION.md
   └─ EXECUTION_GUIDE.md

ENVIRONMENT VARIABLES (.env files)
┌────────────────────────────────────┐
│ Backend (.env)                     │
├────────────────────────────────────┤
│ DATABASE_URL=                      │
│   postgresql://postgres@localhost  │
│   /graphtrace                      │
│ NEO4J_URI=neo4j://localhost:7687  │
│ NEO4J_USER=neo4j                  │
│ NEO4J_PASSWORD=***                │
│ GRAPH_TRACE_LOAD_DOTENV=true      │
│ GRAPH_TRACE_JWT_SECRET=secret     │
│ GRAPH_TRACE_AUTH_REQUIRED=false   │
│ LOG_LEVEL=INFO                    │
└────────────────────────────────────┘
```

---

## Key Technology Decision Rationale

```
┌─────────────────────────────────────────────────────┐
│  TECHNOLOGY SELECTION DECISIONS                     │
└─────────────────────────────────────────────────────┘

FRONTEND: React 19 + Vite
├─ Rationale:
│  ├─ Modern component-based UI
│  ├─ Fast HMR (Hot Module Replacement)
│  ├─ Excellent graph/visualization ecosystem
│  └─ Strong TypeScript support
└─ Alternatives considered:
   └─ Angular, Vue, Svelte (opted for React ecosystem)

BACKEND: FastAPI + Python
├─ Rationale:
│  ├─ Async/await native support
│  ├─ Automatic OpenAPI documentation
│  ├─ Pydantic validation (type-safe)
│  ├─ Rich data science ecosystem
│  └─ Rapid development
└─ Alternatives considered:
   └─ Node.js/Express (less mature data science libs)

DATABASE: PostgreSQL (Primary)
├─ Rationale:
│  ├─ ACID guarantees for workflow state
│  ├─ JSON type support (flexible schema)
│  ├─ Excellent Python ORM support (SQLAlchemy)
│  ├─ Production-grade stability
│  └─ No vendor lock-in (open source)
└─ Alternatives considered:
   └─ MongoDB (lacks referential integrity)

GRAPH DB: Neo4j
├─ Rationale:
│  ├─ Native graph traversal (lineage queries)
│  ├─ Cypher query language (intuitive)
│  ├─ Excellent Python driver
│  └─ Perfect for data lineage tracking
└─ Alternatives considered:
   └─ ArangoDB (less mature ecosystem)

STATE MANAGEMENT (Frontend): Recoil
├─ Rationale:
│  ├─ Atomic state (fine-grained)
│  ├─ Selector memoization (performance)
│  ├─ Minimal boilerplate
│  └─ Good for filter/search scenarios
└─ Alternatives considered:
   ├─ Redux (boilerplate heavy)
   └─ Zustand (less ecosystem)

GRAPH VISUALIZATION: Cytoscape
├─ Rationale:
│  ├─ Mature, production-grade library
│  ├─ Powerful layout algorithms (FCOSE, Cose-Bilkent)
│  ├─ WebGL-backed for large graphs
│  ├─ Extensible with plugins
│  └─ Active maintenance
└─ Alternatives considered:
   ├─ Vis.js (less flexible)
   └─ Sigma.js (newer, less mature)

ORM: SQLAlchemy 2.0
├─ Rationale:
│  ├─ Async support (modern Python)
│  ├─ Declarative models (clean syntax)
│  ├─ Multiple database support (adapters)
│  ├─ Mature ecosystem
│  └─ Type hints support
└─ Alternatives considered:
   ├─ Django ORM (tightly coupled to framework)
   └─ Tortoise ORM (less mature)

VALIDATION: Pydantic v2
├─ Rationale:
│  ├─ Type-safe request/response models
│  ├─ Automatic OpenAPI schema generation
│  ├─ Custom validators (hooks)
│  ├─ JSON serialization
│  └─ Performance improvements in v2
└─ Alternatives considered:
   └─ Marshmallow (verbose syntax)
```

---

## Performance Optimization Strategy

```
┌────────────────────────────────────────────────────┐
│  PERFORMANCE OPTIMIZATION LAYERS                   │
└────────────────────────────────────────────────────┘

FRONTEND
├─ Code Splitting
│  └─ Route-based lazy loading (React Router)
├─ Memoization
│  ├─ React.memo for expensive components
│  ├─ useMemo for computed values
│  └─ Recoil selectors for derived state
├─ Asset Optimization
│  ├─ Minification (Vite)
│  ├─ CSS tree-shaking
│  └─ Image compression
├─ Rendering
│  ├─ Cytoscape WebGL rendering
│  └─ Virtualized lists for large datasets

BACKEND
├─ Database Indexing
│  ├─ Composite indexes on frequently joined columns
│  ├─ B-tree indexes on foreign keys
│  └─ BRIN indexes on time-series data
├─ Connection Pooling
│  ├─ AsyncPG: min_size=10, max_size=20
│  └─ Neo4j: max_pool_size=50
├─ Query Optimization
│  ├─ Eager loading (prevent N+1 queries)
│  ├─ Query result caching
│  └─ Pagination (offset/limit)
├─ Async/Await
│  ├─ Non-blocking I/O
│  ├─ Multiple concurrent requests per worker
│  └─ Background task processing

INFRASTRUCTURE
├─ Horizontal Scaling (Future)
│  ├─ Load balancer (NGINX/HAProxy)
│  ├─ Multiple FastAPI instances
│  ├─ PostgreSQL read replicas
│  └─ Neo4j clustering (Enterprise)
├─ Caching Layer (Optional)
│  ├─ Redis for session/query cache
│  ├─ ETags for HTTP caching
│  └─ Browser cache headers
└─ Compression
   ├─ gzip response compression
   └─ WebSocket for streaming results
```

---

## Security & Compliance Model

```
┌────────────────────────────────────────────────────┐
│  SECURITY & COMPLIANCE CONTROLS                    │
└────────────────────────────────────────────────────┘

AUTHENTICATION
├─ JWT Tokens
│  ├─ Symmetric signing (HS256)
│  ├─ Configurable expiration (default 60 min)
│  └─ Refresh token strategy (future)
├─ API Keys
│  ├─ Static keys via environment
│  └─ Per-service keys (future)
└─ MFA (Optional)
   └─ OTP/TOTP (future implementation)

AUTHORIZATION
├─ Role-Based Access Control (RBAC)
│  ├─ Admin role
│  ├─ Analyst role
│  └─ Viewer role (future)
├─ Resource-Level Authorization
│  └─ Workflow owner checks
└─ Endpoint-Level Guards
   └─ @require_admin() decorator

ENCRYPTION
├─ In Transit
│  ├─ HTTPS/TLS (production)
│  └─ WSS for WebSocket (secure)
├─ At Rest
│  ├─ Database credentials encrypted
│  ├─ API keys encrypted in DB
│  └─ Custom data source passwords encrypted
└─ Configuration Store
   └─ .graphtrace.encryption_key file

DATA PROTECTION
├─ Input Validation
│  ├─ Pydantic models (type checking)
│  ├─ JSON schema validation
│  └─ SQL injection prevention (parameterized queries)
├─ Output Sanitization
│  ├─ XSS prevention (DOMPurify)
│  ├─ HTML escaping (Pydantic)
│  └─ JSON serialization
└─ CORS
   ├─ Whitelist trusted origins
   ├─ Localhost variants expansion
   └─ Credentials policy

RATE LIMITING
├─ Per-IP rate limiting
├─ Configurable threshold (requests/second)
├─ In-memory tracking (non-persistent)
└─ TTL cleanup (memory efficient)

AUDIT & LOGGING
├─ Request logging
├─ Error logging
├─ Failed authentication attempts
└─ Data access logs (future)
```

This completes the visual architecture documentation for GoodpointAI!
