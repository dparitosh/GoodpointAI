# PAGE_REQUIREMENTS_SPECIFICATIONS.md

## 1. Document Metadata
- **Purpose**: Unified requirements specification for ETL, data pipeline, migration, OpenSearch, and analytics capabilities across the graphTrace platform.  
- **Version**: 7.0 (Consolidated from multiple source documents on Nov 22–23, 2025).  
- **Owner**: Platform Engineering / Product Management  
- **Related Docs**: `ETL_Architecture_Summary.md`, `MODERNIZATION_TRACKER.md`, `HOW_TO_VIEW_UI.md`  
- **Status Legend**: ✓ Done |  In Progress | ⚙ Hardening/Debugging | ✗ Blocked |  Planned

---

## 2. Business Needs (BN-*)
- **BN-01**: Provide enterprise teams **self-service, governed data ingestion** from PLM, ERP, databases, and files.  
- **BN-02**: Enable **no-code ETL workflows** with drag-and-drop canvas + 30+ transforms (filter, join, aggregate, pivot).  
- **BN-03**: Expose **real-time graph + vector search** across structured, semi-structured, and semantic data.  
- **BN-04**: Support **advanced database migrations** with live XState-driven visualization of job state and control (pause/resume/retry).  
- **BN-05**: Deliver **embedded analytics + dashboards** for quality, lineage, cost, compliance without external BI tools.

---

## 3. Capabilities (C-*)
### 3.1 PLM XML Processing (C-PLM)
- ✓ **Upload** up to 150 MB XML batch, validation, store metadata.  
- ✓ **Parsing** with schema constraints, extract Product, Part, relationships.  
- ✓ **Transform** relational to Neo4j Cypher patterns.  
-  **Index** vector embeddings in OpenSearch for semantic search.

### 3.2 OpenSearch Integration (C-OPEN)
- ✓ **Configuration** CRUD via React form (protocol, host, port, credentials).  
- ✓ **Health** monitoring: cluster status + response time every 30 s.  
- ✓ **Index Management**: list, create, delete operations.  
- ✓ **Vector Search**: k-NN similarity with text or embedding payloads.  
-  **Analytics Indexing** (future) for aggregated logs.

### 3.3 Migration Engine & Visualizer (C-MIGRATE + C-VIS)
- ✓ **Job Orchestration**: Expose REST API to launch multi-source migration with strategies.  
- ✓ **Real-time State Streaming**: WebSocket endpoint broadcasting stage, progress, quality, errors.  
- ✓ **XState Visualization UI**: Clickable statechart with Fluent theme, keyboard accessible.  
- ✓ **Control Events**: Pause, resume, retry, cancel; backend acknowledgment before UI unlock.  
- ✓ **History Export**: Download CSV audit trail of transitions.  
- ✓ **Session Persistence**: Store job metadata in `migration_sessions` PostgreSQL table.

### 3.4 Operational Instrumentation (C-OPS)
- ✓ **Health Endpoints**: `/api/status/{service}` for each microservice with structured response.  
- ✓ **Consolidated Status UI**: Header badge aggregating service health across platform.  
- ⚙ **Threshold Monitoring**: `monitoring_thresholds.json` defines alert bands; analytics service logs breaches.  
- ✓ **Error Envelopes**: All HTTP errors use `{status, message, timestamp}` format.  
- ✓ **Correlation IDs**: `X-Trace-Id` headers propagate across services.

### 3.5 Analytics Storage & Dashboard (C-ANALYTICS)
- ✓ **Metrics Ingestion**: Collate upload counts, latencies, error rates from gateway and PLM service.  
- ✓ **API for Dashboards**: `/api/analytics/uploads` returns time-series for governance views.  
- ✓ **Migration Quality Metrics**: Track row mismatches, schema drift detection, quality scores.

### 3.6 Graph Features - ETL/XState/OpenSearch Centerpiece (C-GRAPH)
- ✓ **GraphQL Toolkit**: Schema introspection (XML/JSON), data transforms, query execution, persisted catalogue for ETL data mapping.  
- ✓ **Neo4j GraphRAG**: Hybrid semantic search combining graph relationships with vector similarity; bridges graph data to OpenSearch.  
-  **Graph Explorer UI**: Interactive visualization of Neo4j data, Cypher query execution, migration state history rendering.  
- ✓ **ETL Integration**: GraphQL transforms power migration DATA_MIGRATION phase; schema discovery in DISCOVERING phase.  
- ✓ **XState Integration**: Neo4j stores migration state transitions; Graph Explorer visualizes as interactive state graph.  
- ✓ **OpenSearch Bridge**: GraphRAG enables hybrid search (Neo4j context + OpenSearch vectors) for semantic queries.  
-  **Data Lineage**: Track data flows from source → transform → target as Neo4j relationships (future).

_See `GRAPH_FEATURES_LOW_LEVEL_REQUIREMENTS.md` for detailed implementation specifications._

---

## 4. Functional Requirements (FR-*)

### 4.1 PLM XML Processing (C-PLM)
- **FR-PLM-01**: Frontend `gp_plm_data_management.jsx` accepts drag-and-drop or file picker for `.xml`; validates locally for size/extension before POST to `/api/plm-xml/uploads`.  
- **FR-PLM-02**: Gateway (Port 8003) forwards request to PLM XML Service (Port 8005); backend validates XML schema using `lxml`; returns 400 if invalid.  
- **FR-PLM-03**: Processing Hub `gp_processing_hub.jsx` displays ETL stages: `Uploading → Parsing → Transforming → Loading → Indexing → Complete`; backend sends SSE to update UI progress.  
- **FR-PLM-04**: On completion, system generates graph nodes in Neo4j (Port 7687) with `Product`, `Part` labels and relationships `HAS_PART`, `DEPENDS_ON`.  
- **FR-PLM-05**: Vector embeddings computed via Sentence Transformers and indexed into OpenSearch (`graphtrace-vectors-plm` index).  
- **FR-PLM-06**: Error logs persisted in `migration.log` and surfaced via toast notification.

### 4.2 OpenSearch Integration (C-OPEN)
- **FR-OPEN-01**: `VectorSearchPage.jsx` contains configuration panel; user submits `protocol`, `host`, `port`, `username`, `password`; backend validates via `_cluster/health` call, stores config in environment override (not committed).  
- **FR-OPEN-02**: Index management grid displays name, document count, size; "Create Index" modal requires index name + optional mappings JSON; backend validates and returns success/failure.  
- **FR-OPEN-03**: Vector search form accepts text or raw embedding array; backend calls OpenSearch k-NN with `k=10` default, returns hits with `_score`, `_source`.  
- **FR-OPEN-04**: Backend retries failed OpenSearch operations twice with exponential backoff (1s/4s) before surfacing HTTP 502.  
- **FR-OPEN-05**: Health widget polls `/api/opensearch/health` every 30 s; color coding: green (<0.5 s latency), yellow (<1 s), red otherwise.

### 4.3 Migration Engine & Visualizer (C-MIGRATE + C-VIS)
- **FR-MIG-01**: `services.advanced_migration_engine:app` exposes `/api/migration/advanced/start` with payload containing `sources[]`, `target`, `strategy`; must persist job in `migration_sessions` (PostgreSQL).  
- **FR-MIG-02**: WebSocket endpoint `/api/ws/migration/{sessionId}` pushes `state`, `progress`, `quality`, `errors[]` payload every ≤1 s.  
- **FR-MIG-03**: `PLMMigrationStatechartVisualizer.jsx` consumes machine definition from `plmMigrationMachine.ts` and renders clickable nodes with optional navigation metadata for configuration pages.  
- **FR-MIG-04**: Control panel events (PAUSE, RESUME, RETRY, CANCEL) call `/api/migration/advanced/{sessionId}/events`; UI disables buttons until backend acknowledges.  
- **FR-MIG-05**: Visualization uses Fluent theme tokens, ensures keyboard accessibility (Tab focus, Space/Enter to trigger).  
- **FR-MIG-06**: Historical transitions accessible via `/api/migration/advanced/{sessionId}/history` for audit download (.csv).

### 4.4 Operational Instrumentation (C-OPS)
- **FR-OPS-01**: Each FastAPI router sets `timeout=30` and wraps HTTP errors in `{status, message, timestamp}` envelope.  
- **FR-OPS-02**: `monitoring_thresholds.json` defines warning/critical bands for CPU, memory, queue depth; `services.analytics_storage_service` persists breaches.  
- **FR-OPS-03**: Frontend `useServiceStatus` hook consolidates `/api/status/{service}` responses and surfaces amber/red badges across header.  
- **FR-OPS-04**: `scripts/delete_markdown.ps1` + `scripts/merge_markdown.ps1` remain as tooling references but are exempt from runtime packaging.  
- **FR-OPS-05**: Every capability table row must link to validation evidence (tests, dashboards, or log excerpts) logged in Section 9.

---

## 5. End-to-End Functions & Data Flows

### 5.1 PLM XML → Graph & Analytics Flow
1. **Upload (Frontend)**: `gp_plm_data_management.jsx` gathers files, runs client validation, issues `FormData` POST to `/api/plm-xml/uploads`.  
2. **Gateway (Port 8003)**: FastAPI router authenticates request, stores metadata, streams file to PLM XML microservice (Port 8005).  
3. **Parsing (Port 8005)**: `plm_xml_service.py` uses `lxml` to validate schema, extract entities/relationships, writes to PostgreSQL (Port 5432).  
4. **ETL (Processing Hub)**: `gp_processing_hub.jsx` displays server-reported stage; backend orchestrator maps relational data to Neo4j (Port 7687) via Cypher templates.  
5. **Indexing**: OpenSearch bulk indexing for text/vector search; embeddings computed via Sentence Transformers service.  
6. **Analytics Logging**: `services.analytics_storage_service` (Port 8006) records metrics; dashboards read via `/api/analytics/uploads`.  
7. **Notifications**: Webhook or toast summarizing results, linking to `VectorSearchPage` for verification.

### 5.2 Migration Visualization Flow
1. User opens `/plm-migration-visualizer`; component loads machine definition + subscribes to WebSocket.  
2. Upon `START`, backend creates session, broadcasts `initializing`.  
3. Each backend stage (`discovering`, `profiling`, …) pushes context payload; UI animates node, updates progress/time.  
4. Pause/Resume commands propagate via REST events; backend confirms state before UI unlocks controls.  
5. Completion transitions to double-bordered `completed` node and exposes export/report buttons.

### 5.3 OpenSearch Config & Search Flow
1. Config form submits connection details; backend verifies credentials via cluster `_cluster/health`.  
2. Index grid fetches `/api/opensearch/indexes`; create/delete operations update list optimistically with rollback on failure.  
3. Vector search form collects text or embedding; backend executes k-NN, returns hits with `_score`, `_source.metadata`.  
4. Analytics tab (future) will consume `/api/opensearch/analytics` once implemented; placeholder card displayed until flag flips.

---

## 6. API & Service Reference (Essentials Only)
| Service | Endpoint | Method | Purpose | Timeout | Status |
|---------|----------|--------|---------|---------|--------|
| Backend Gateway (8003) | `/api/plm-xml/uploads` | POST | Receive uploads, hand off to PLM service. | 30 s | ✓ |
| PLM XML Service (8005) | `/internal/plm-xml/process` | POST | Parse XML, persist data. | 60 s | ✓ |
| Migration Engine (8007) | `/api/migration/advanced/start` | POST | Launch migration job. | 45 s | ✓ |
| Migration Engine (8007) | `/api/migration/advanced/{id}/events` | POST | Control events (PAUSE/RESUME/RETRY/CANCEL). | 15 s | ✓ |
| Migration Engine (8007) | `/api/migration/advanced/{id}/history` | GET | Transition history export. | 15 s | ✓ |
| OpenSearch Router (8003) | `/api/opensearch/health` | GET | Cluster health & latency. | 5 s | ✓ |
| OpenSearch Router (8003) | `/api/opensearch/indexes` | GET/POST/DELETE | Index management. | 15 s | ✓ |
| OpenSearch Router (8003) | `/api/opensearch/search` | POST | Vector similarity query. | 15 s | ✓ |
| Analytics Storage (8006) | `/api/analytics/uploads` | GET | Metrics for governance dashboard. | 10 s | ✓ |

All services log responses using common schema `{status, message, data?, timestamp}` and propagate correlation IDs via `X-Trace-Id` header.

---

## 7. Data & Storage Requirements
- **PostgreSQL Main (Ports 5432/5433)**: Stores PLM uploads, migration sessions, task tracker tables. Requires hourly backups via `pg_basebackup`.  
- **Neo4j (Ports 7687/7474)**: Hosts derived PLM graph; enforces unique constraints on `Product.id`, `Part.id`.  
- **PostgreSQL Configuration Schema**: Configuration documents previously stored in MongoDB now live in schema `ui_config` (tables `data_sources`, `branding_tokens`, `feature_flags`) with JSONB columns; CRUD exposed only via backend services to preserve validation rules.  
- **OpenSearch 2.x (Port 9200)**: Vector + keyword indexes; uses `graphtrace-vectors-*` naming.  
- **Redis 7.x (Port 6379)**: Token + cache store for migration progress snapshots; TTL 10 minutes.  
- **Analytics Storage (PostgreSQL 15)**: Isolated schema `analytics`; tables `upload_metrics`, `service_health`, `migration_quality`.  
- **Security**: Secrets loaded from environment (`POSTGRES_PASSWORD`, `NEO4J_PASSWORD`, etc.); no secrets committed to repo.

---

## 8. Delivery Tracker & Status
| Task ID | Work Item | Owner | Linked Artifacts | Status | Evidence |
|---------|-----------|-------|------------------|--------|----------|
| T-01 | Consolidate markdown specs into this single file and remove duplicates. | Docs Team | `scripts/merge_markdown.ps1`, `scripts/delete_markdown.ps1` | ✓ Done | Git history `docs cleanup` (Nov 22). |
| T-02 | Reformat requirements grouped by needs/capabilities/features/functions. | Platform PM | This document v7.0 | ✓ Done | Peer review pending (Nov 23). |
| T-03 | Implement migration control REST endpoints + WebSocket streaming. | Backend | `services/advanced_migration_engine.py`, `migration_router.py` | ✓ Done | Tests in `tests/test_advanced_migration_features.py` (11 tests). |
| T-04 | Build PLM Migration Visualizer UI with XState + accessibility. | Frontend | `PLMMigrationVisualizerPage.jsx`, `XStateGraphVisualizer.jsx` | ✓ Done | Implemented in commit 0376bfa. |
| T-05 | Harden Analytics Storage metrics ingestion + dashboard API. | Data Ops | `services.analytics_storage_service:app`, `analytics_router.py` | ✓ Done | Tests in `tests/test_analytics_storage.py` (10 tests). |

Status Legend matches Section 3.

---

## 9. Validation & Definition of Done
- **Unit & Integration Tests**: `python_backend/tests` (pytest) must include coverage for PLM uploads, OpenSearch endpoints, migration controls; CI target ≥85% for touched modules.  
- **Frontend QA**: Playwright regression for OpenSearch pages; manual accessibility review for visualizer (keyboard + screen reader).  
- **Performance**: PLM upload pipeline end-to-end 95th percentile ≤90 seconds for 150 MB batch.  
- **Observability**: Each service exports structured logs + metrics (latency, failures) to centralized dashboard; alerting threshold defined in `monitoring_thresholds.json`.  
- **Sign-off**: Capability owner + QA lead approve via Jira tickets referenced in Task Tracker.

---

## 10. Reference Index
- **Related Specifications**: 
  - `GRAPH_FEATURES_LOW_LEVEL_REQUIREMENTS.md` - GraphQL toolkit, Graph Explorer, Neo4j GraphRAG (ETL/XState/OpenSearch centerpiece)
  - `TASK_COMPLETION_VERIFICATION.md` - T-03, T-04, T-05 implementation verification
- Frontend pages: `e2etraceapp/src/pages/gp_plm_data_management.jsx`, `e2etraceapp/src/pages/gp_processing_hub.jsx`, `e2etraceapp/src/pages/VectorSearchPage.jsx`, `e2etraceapp/src/pages/PLMMigrationVisualizerPage.jsx`.  
- Shared components: `e2etraceapp/src/components/XStateVisualizer/XStateGraphVisualizer.jsx`, `e2etraceapp/src/components/plm/PLMMigrationStatechartVisualizer.jsx`, `e2etraceapp/src/components/GraphExplorer.jsx`.  
- Backend routers: `python_backend/graph_api/opensearch_router.py`, `python_backend/graph_api/plm_xml_router.py`, `python_backend/graph_api/migration_router.py`, `python_backend/graph_api/graphql_router.py`, `python_backend/graph_api/neo4j_graphrag_router.py`, `python_backend/main.py`.  
- Services: `python_backend/services/opensearch_service.py`, `python_backend/services/plm_xml_service.py`, `python_backend/services/advanced_migration_engine.py`, `python_backend/services/analytics_storage_service.py`, `python_backend/services/graphql_service.py`, `python_backend/services/neo4j_graphrag_service.py`.  
- Configuration: `config/system_configuration.json`, `config/monitoring_thresholds.json`, `config/environments.json`.  
- Tooling & Scripts: `scripts/merge_markdown.ps1`, `scripts/delete_markdown.ps1`, `start_windows.ps1`, `deploy_windows.ps1`.  
- Tests: `python_backend/tests/test_advanced_migration_features.py`, `test_health_monitoring.py`, `test_xml_upload.py`, `test_runtime_config.py`, `test_analytics_storage.py`.

---

**Document Intent**: Provide concise, grouped requirements for ongoing delivery. Any net-new capability must extend Sections 2–8 before development begins.
