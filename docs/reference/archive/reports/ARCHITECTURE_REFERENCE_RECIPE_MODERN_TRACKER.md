# ARCHITECTURE_REFERENCE_RECIPE_MODERN.md — Implementation Tracker (Agents + Events + Actions)

**Purpose**: actionable tasks that tie the architecture recipe to the *interactive stateflow* (XState machines) so implementation stays deterministic + auditable.

**Status values**: `Open` | `In Progress` | `Blocked` | `Done` | `Needs Verification`

**Owner values**:
- `FE` = frontend (XState + UI)
- `BE` = backend (FastAPI + services + persistence)
- `FE+BE` = requires coordinated UI + API work

---

## 0) Recently fixed (delta review)

| Item | Outcome | Where |
|---|---|---|
| Soda Core Postgres scan (fail-closed) | Added `/api/analytics/quality/soda/scan/{table_name}`; returns 503 if Soda missing; persists report | `python_backend/graph_api/quality_router.py` |
| Soda external dependency | Added optional `soda-core-postgres` to external integrations requirements | `python_backend/requirements_external_integrations.txt` |
| Fail-closed test | Added unit test asserting 503 when Soda unavailable | `python_backend/tests/test_soda_quality_fail_closed.py` |
| Recipe doc accuracy | Updated recipe to reflect Soda integration exists | `ARCHITECTURE_REFERENCE_RECIPE_MODERN.md` |
| Run-scoped Soda quality gate | Added `/api/plm/etl/runs/{run_id}/dq/soda/scan/{schema.table}` + persisted `dq_gate_results` | `python_backend/graph_api/plm_etl_router.py`, `python_backend/models/quality_models.py` |

---

## Next 10 (execution order)

| Priority | ID | Why now | Owner |
|---|---|---|---|
| P0 | ORCH-002 | Enforces fail-closed + removes silent demo paths across all flows | FE+BE |
| P0 | ORCH-003 | Makes the orchestrator actually call real backend jobs and track IDs | FE |
| P0 | ETL-001 | Creates canonical `run_id` to anchor everything else | FE |
| P0 | ETL-003 | Staging is required to make transforms/validations real | FE |
| P0 | ETL-004 | Transform writes canonical Postgres truth (no client-side truth) | FE |
| P0 | ETL-006 | UI reads results from persisted truth (no simulated dashboards) | FE |
| P1 | ETL-I-002 | Produces derived Neo4j graph from Postgres via Spark sync endpoint | FE |
| P1 | ETL-I-003 | Adds job log tail polling so sync is observable and debuggable | FE |
| P1 | DQ-003 | Aligns DQ scanning with “Postgres truth” (no filesystem fallback in core path) | BE |
| P1 | OS-001 | Ensures retrieval layer is safe: 503 when unconfigured + UI shows N/A | BE |

---

## Recipe coverage checklist (sections 1–10)

| Recipe section | Target outcome | Primary tracker IDs | Current status |
|---|---|---|---|
| §1 Separate reasoning from truth | Agents only decide actions; truth is deterministic + persisted | ORCH-I-001, ORCH-005 | Open |
| §2 Canonical stores | Postgres truth; Neo4j derived; OpenSearch retrieval | ETL-I-001, NEO-003, OS-001 | Needs Verification |
| §3 Orchestration spine | UI drives real backend execution; UI renders persisted truth | ORCH-003, ETL-001..ETL-006 | Open |
| §4 Data quality (Soda optional) | Soda scans Postgres tables only; fail-closed; persisted reports | DQ-002 | Done |
| §5 CAD offline deterministic | No agent reads CAD binaries; store extracted metadata in Postgres | (future) | Open |
| §6 Agentic AI value boundaries | Agents propose/remediate; must not fabricate/bypass gates | ORCH-002 | Open |
| §7 Neo4j + quality + agents | Postgres validation fails; Neo4j explains impact; agent suggests fixes | NEO-001, NEO-002 | Open |
| §8 OpenSearch memory | Retrieval endpoints fail-closed; store searchable summaries | OS-001, OS-002 | Needs Verification |
| §9 Minimal stack | Keep control-plane simple; add Spark for scale | ETL-I-002, ETL-I-003 | Needs Verification |
| §10 One-sentence recipe | Enforced by implementation (no demo data, fail-closed) | ORCH-002, ETL-I-001 | Open |

---

## 1) Central Orchestrator Stateflow (Multi-Agent Workflow)

**Source of truth (interactive stateflow)**: `e2etraceapp/src/services/agentic-orchestrator.js`

**Backend APIs this stateflow should drive (recipe-aligned)**:
- PLM ETL truth (Postgres): `POST /api/plm/etl/runs` → `POST /api/plm/etl/runs/{run_id}/stage` → `POST /api/plm/etl/runs/{run_id}/transform` → `POST /api/plm/etl/runs/{run_id}/validate` → `GET /api/plm/etl/runs/{run_id}/results`
- Derived graph sync (Spark→Neo4j): `POST /api/plm/etl/runs/{run_id}/sync/neo4j` and `GET /api/plm/etl/sync/neo4j/jobs/{job_id}`
- Data quality (Soda): `POST /api/analytics/quality/soda/scan/{schema.table}`

### 1.1 State → Event → Action task map

| ID | Agent / Actor | State | Event | Action (code) | Expected deterministic side-effect | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|---|
| ORCH-001 | UI Orchestrator | `idle` → `initializing` | `INIT_AGENTS` | `initializeAgents` | Agent roster is explicit and deterministic | FE+BE | Roster rendered in UI; optional POST to backend audit endpoint returns 201 | `e2etraceapp/src/services/agentic-orchestrator.js`, `python_backend/graph_api/*` (new audit endpoint if adopted) | Open |
| ORCH-002 | UI Orchestrator | `ready` → `routing` | `PROCESS_TASK` | `routeTaskToAgent` | Task intent persisted; dependency gates are fail-closed | FE+BE | Missing deps yield 503 (API) and UI shows N/A; no silent fallbacks | `e2etraceapp/src/services/agentic-orchestrator.js`, `python_backend/core/*`, `python_backend/graph_api/*` | Open |
| ORCH-003 | UI Orchestrator | `routing` → `executing` | `AGENT_ASSIGNED` | `executeAgentTask` | Real backend job invoked; IDs captured | FE | UI captures and displays `run_id`/`scan_id`/`job_id`; stores them in state for polling | `e2etraceapp/src/services/agentic-orchestrator.js`, UI page(s) invoking ETL/DQ/Spark endpoints | Open |
| ORCH-004 | UI Orchestrator | `executing` → `collaborating` | `REQUIRES_COLLABORATION` | `orchestrateCollaboration` | Subtasks created deterministically | FE | Subtasks are explicit items with IDs; transitions recorded in event log | `e2etraceapp/src/services/agentic-orchestrator.js` | Open |
| ORCH-005 | UI Orchestrator | `executing` → `aggregating` | `TASK_COMPLETED` | `aggregateResults` | Aggregation reads persisted truth only | FE+BE | UI renders from DB-backed endpoints; no computed “demo” results | UI page(s), `python_backend/graph_api/plm_etl_router.py`, `python_backend/graph_api/quality_router.py` | Open |
| ORCH-006 | UI Orchestrator | `chat_processing` → `ready` | `CHAT_RESPONSE_READY` | `processChatMessage` | Chat persisted if used for approvals | FE+BE | If approvals are enabled, chat is stored server-side with trace IDs | UI chat components, backend audit/approval router (if adopted) | Open |
| ORCH-007 | UI Orchestrator | `monitoring` → `ready` | `MONITORING_COMPLETE` | `monitorSystemHealth` | Dependency health surfaced | FE+BE | Dedicated endpoint(s) return health; UI shows N/A when unavailable | UI health widget, backend health endpoints | Open |
| ORCH-008 | UI Orchestrator | `error` | `RETRY` / `RESET` | `handleError` | Errors persisted and retry policy deterministic | FE+BE | Error objects include cause + action; retry doesn’t bypass gates | UI orchestrator, backend error/audit persistence (if adopted) | Open |

**Acceptance criteria for ORCH layer** (minimum):
- For any task that claims to run ETL/DQ/graph sync, the UI must display IDs returned by backend and render progress from persisted truth.
- No “random scores”, “simulated success”, or demo-only fallbacks when Postgres is required.

### 1.2 Integration tasks (to align with recipe)

| ID | Topic | Task | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|
| ORCH-I-001 | Truth vs reasoning | Add backend endpoint(s) to record orchestrator decisions separately from truth data (audit trail) | BE | POST writes decision record; GET lists by run_id; no secrets persisted | `python_backend/graph_api/*` (new router), `python_backend/models/*` | Open |
| ORCH-I-002 | Fail-closed | Standardize 503 dependency responses and UI N/A rendering for orchestrator-driven pages | FE+BE | Missing Postgres/Neo4j/OpenSearch yields 503; UI renders N/A without crashing | UI pages + existing dependency checks | Open |

---

## 2) Agentic ETL Orchestration Stateflow (Pipeline)

**Source of truth (interactive stateflow)**: `e2etraceapp/src/services/agentic-etl-orchestrator.js`

### 2.1 State → Event → Action task map

| ID | Agent / Actor | State | Event | Action (code) | Expected deterministic side-effect | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|---|
| ETL-001 | ETL Orchestrator | `idle` → `analyzing` | `START_PIPELINE` | `initializePipeline` | Create persisted run in Postgres (`run_id`) | FE | Calls `POST /api/plm/etl/runs` and stores `run_id` in context | `e2etraceapp/src/services/agentic-etl-orchestrator.js`, UI pipeline page | Open |
| ETL-002 | Analyzer Agent | `analyzing` | `ANALYSIS_COMPLETE` | `deployAnalysisAgent` / `storeAnalysis` | Analysis results persisted and traceable | FE+BE | Analysis summary saved server-side and linked to `run_id` (no demo/sample) | UI orchestrator + backend (new table/router if adopted) | Open |
| ETL-003 | Extractor Agent | `orchestrating` | `EXTRACTION_COMPLETE` | `processExtractionResults` | Staged payloads persisted | FE | Calls `POST /api/plm/etl/runs/{run_id}/stage` with extracted records | UI pipeline page(s) | Open |
| ETL-004 | Transformer Agent | `transforming` | `TRANSFORMATION_COMPLETE` | `processTransformationResults` | Canonical tables written | FE | Calls `POST /api/plm/etl/runs/{run_id}/transform` with explicit mappings | UI pipeline page(s) | Open |
| ETL-005 | Loader Agent | `loading` | `LOADING_COMPLETE` | `processLoadingResults` | Run status reflects truth | BE | Backend updates `plm_ingestion_runs.status` deterministically | `python_backend/graph_api/plm_etl_router.py`, `python_backend/models/plm_models.py` | Open |
| ETL-006 | Monitor Agent | `monitoring` | `MONITORING_COMPLETE` | `finalizeResults` | UI reads results from DB | FE | UI polls `GET /api/plm/etl/runs/{run_id}/results` and renders | UI pipeline page(s) | Open |
| ETL-007 | Monitor Agent | `monitoring` → `transforming` | `QUALITY_ISSUE` | `handleQualityIssue` | DQ scans run and persist | FE+BE | Triggers `POST /api/plm/etl/runs/{run_id}/dq/soda/scan/{schema.table}` (or `POST /api/analytics/quality/soda/scan/{schema.table}`); renders persisted report | UI + `python_backend/graph_api/plm_etl_router.py`, `python_backend/graph_api/quality_router.py` | Needs Verification |
| ETL-008 | ETL Orchestrator | `completed` | `RESET` | `cleanup` | Only UI state cleared | FE | Reset does not delete DB history; user can reopen run | UI orchestrator | Open |

### 2.2 Recipe alignment tasks

| ID | Topic | Task | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|
| ETL-I-001 | Postgres truth | Replace any in-browser ETL “truth” writes with backend-run + Postgres persistence | FE | UI never treats client-side data as canonical; always uses backend IDs | UI pipeline pages/services | Open |
| ETL-I-002 | Neo4j derived | After successful Postgres run, invoke `POST /api/plm/etl/runs/{run_id}/sync/neo4j` | FE | Button/action triggers sync; handles 409 (nothing to sync) and 503 (missing deps) | UI pipeline pages | Needs Verification |
| ETL-I-003 | Spark observability | Ensure `job_id` + `GET /api/plm/etl/sync/neo4j/jobs/{job_id}` log tail is surfaced in UI | FE | UI can poll and display latest log tail and completion | UI pipeline pages | Needs Verification |
| ETL-I-004 | OpenSearch retrieval | Index summaries/metadata into OpenSearch (optional) with strict 503 on OpenSearch endpoints | BE | Index endpoint exists; search endpoint returns 503 when unconfigured | `python_backend/services/opensearch_service.py`, `python_backend/graph_api/opensearch_router.py` | Open |

---

## 3) Self-Healing Orchestration Stateflow

**Source of truth (interactive stateflow)**: `e2etraceapp/src/machines/selfHealingMachine.js`

### 3.1 State → Event → Action task map

| ID | Agent / Actor | State | Event | Action/Guard | Recipe expectation | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|---|
| SH-001 | Self-healing controller | `idle` → `executing` | `START` | entry `logExecution`, `trackLineage` | Emit lineage events; store to Postgres and derive graph in Neo4j | FE+BE | State transitions recorded; lineage events persisted and queryable | `e2etraceapp/src/machines/selfHealingMachine.js`, backend lineage router/service | Open |
| SH-002 | Self-healing controller | `executing` → `validating` | `SUCCESS` | — | Deterministic validation gates (no agent bypass) | FE+BE | Validation uses Postgres-backed checks; failures are explicit | UI + backend validation endpoints | Open |
| SH-003 | Self-healing controller | `executing` → `retrying` | `ERROR` | `canRetry` | Retry policy deterministic; persist retry history | FE+BE | Retry attempts persisted; backoff visible in event log | UI + backend audit store (if adopted) | Open |
| SH-004 | Self-healing controller | `executing` → `circuit_open` | `ERROR` | `shouldTripCircuitBreaker` | Persist circuit breaker state; surface in UI | FE+BE | Circuit state persisted; UI displays open/half-open timers | UI + backend audit store (if adopted) | Open |
| SH-005 | Self-healing controller | any | `SEND_TO_DLQ` | — | DLQ records persisted; never dropped silently | BE | DLQ record written with payload hash + reason; retriable | backend audit/DLQ storage (new) | Open |

---

## 4) PLM Systems Integration Stateflow

**Source of truth (interactive stateflow)**: `e2etraceapp/src/machines/plmSystemsIntegrationMachine.js`

| ID | State | Event | Action (invoke) | Backend endpoint dependency | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|
| PLM-001 | `checkingHealth` | `CHECK_HEALTH` | `GET /api/plm/systems/health` | Real health for each connector | BE | Returns per-system status with fail-closed semantics (no fake green) | `python_backend/graph_api/plm_systems_integration_router.py` | Needs Verification |
| PLM-002 | `querying.*` | `QUERY_OBJECTS` | `/api/plm/{system}/query` | Query must be real or explicitly 501 | BE | Each system either implements real query or returns 501 with clear guidance | `python_backend/graph_api/plm_systems_integration_router.py` | Needs Verification |
| PLM-003 | `fetchingBOM` | `GET_BOM` | `/api/plm/teamcenter/bom/{partId}` | BOM retrieval end-to-end | BE | Returns deterministic BOM payload (no mock) or 501 | `python_backend/graph_api/plm_systems_integration_router.py` | Needs Verification |

---

## 5) Visualizer + Graph-as-UI (XState Visualizer)

**Reference docs**: `XSTATE_VISUALIZER_COMPLETION.md`, `WORLD_CLASS_XSTATE_VISUALIZER_REPORT.md`

| ID | Feature | Current note in report | Task | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|
| VIS-001 | Swimlane orchestration view | Partially implemented | Add lane layout to show multi-actor machines (Orchestrator/ETL/Self-heal) | FE | Lane layout renders clearly; no new theme primitives; works with current graph data | `e2etraceapp/src/components/xstate-visualizer/*` | Open |
| VIS-002 | History scrubber timeline | Foundation ready | Bind to persisted run history / event log (not simulated) | FE+BE | Timeline reads from persisted backend history endpoint; supports replay/inspect | UI visualizer + backend history endpoint (if adopted) | Open |

---

## 6) Data Quality (Recipe §4)

| ID | Task | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|
| DQ-001 | Keep deterministic SQL-rule scans as baseline truth gate | BE | Scan is deterministic; persists report; no random/demo data paths | `python_backend/graph_api/quality_router.py` | Needs Verification |
| DQ-002 | Soda scan for Postgres tables only (fail-closed 503 when missing): `POST /api/analytics/quality/soda/scan/{schema.table}` | BE | Endpoint persists scan report; missing Soda => 503; test coverage present | `python_backend/graph_api/quality_router.py`, `python_backend/tests/test_soda_quality_fail_closed.py` | Done |
| DQ-003 | Decide policy: remove filesystem fallback from quality scan endpoint (architecture says Postgres truth) | BE | Either remove fallback or isolate behind separate endpoint; update docs accordingly | `python_backend/graph_api/quality_router.py`, `ARCHITECTURE_REFERENCE_RECIPE_MODERN.md` | Open |

---

## 7) Neo4j Derived Graph + State Transition Graph

**Backend reference**: `python_backend/tests/test_integration_neo4j_xstate.py` (currently stubbed)

| ID | Task | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|
| NEO-001 | Persist migration state transitions to Neo4j (real driver, not stub) | BE | On each state transition, write `(from)-[:TRANSITIONED_TO {event, ts}]->(to)`; failures are best-effort unless endpoint is strict | `python_backend/services/*`, `python_backend/graph_api/*` | Open |
| NEO-002 | Provide Cypher-backed endpoint to fetch a session’s state path for visualizer | BE | `GET` returns nodes/edges ready for visualizer; 503 if strict-mode and Neo4j missing | `python_backend/graph_api/*` (new endpoint), `python_backend/services/*` | Open |
| NEO-003 | Ensure graph build is derived from Postgres and can be rebuilt (Spark job path) | BE | Spark job reads Postgres by run_id and rebuilds Neo4j; orchestration endpoint exists and is observable | `spark_jobs/*`, `python_backend/graph_api/plm_etl_router.py` | Needs Verification |

---

## 8) OpenSearch Retrieval (Recipe §8)

| ID | Task | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|
| OS-001 | Keep OpenSearch endpoints fail-closed 503 when unconfigured | BE | All OpenSearch-backed endpoints return 503 when missing; UI shows N/A | `python_backend/services/opensearch_service.py`, `python_backend/graph_api/opensearch_router.py` | Needs Verification |
| OS-002 | Index run summaries + historical failures for agent recall | BE | Indexer persists minimal summaries and supports query/filtering | `python_backend/services/opensearch_service.py`, `python_backend/graph_api/opensearch_router.py` | Open |

---

## 11) Integration Connectors Stateflows (LLM/OData/FileSystem/AWS/Azure)

These machines exist in the interactive stateflow and should follow the same architecture principles:
- No fabricated “healthy” states
- Fail-closed at the API boundary where required (503 when integration is not configured)
- UI shows N/A (not demo data)

### 11.1 LLM Integration

**Source of truth (interactive stateflow)**: `e2etraceapp/src/machines/llmIntegrationMachine.js`

| ID | State | Event | Action (invoke) | Backend dependency | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|
| LLM-001 | `checkingHealth` | `CHECK_HEALTH` | `GET /api/llm/health` | Must not fabricate “healthy” when unconfigured | BE | Returns `status=unconfigured` (200) when no provider configured; returns `healthy` when configured; no mock models | `python_backend/graph_api/*` (llm router), `python_backend/services/*` | Verified |
| LLM-002 | `sending` | `SEND_MESSAGE` | `POST /api/llm/{provider}/chat` | Must not return mock responses | BE | When unconfigured => 503; when configured => real provider call and persisted audit (optional) | backend llm router/service | Needs Verification |
| LLM-003 | `embedding` | `GET_EMBEDDING` | `POST /api/llm/{provider}/embedding` | Needed by GraphRAG/semantic features | BE | Missing embeddings provider => 503; response shape stable | backend llm router/service | Needs Verification |

### 11.2 OData Integration

**Source of truth (interactive stateflow)**: `e2etraceapp/src/machines/odataIntegrationMachine.js`

| ID | State | Event | Action (invoke) | Backend dependency | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|
| ODATA-001 | `checkingHealth` | `CHECK_HEALTH` | `GET /api/odata/health` | OData adapter must not claim configured when unconfigured | BE | Returns `status=unconfigured` (200) when no URL configured; no “always healthy” | `python_backend/graph_api/*` (odata router), `python_backend/services/*` | Verified |
| ODATA-002 | `connecting` | `CONNECT` | `POST /api/odata/connect` | Stores connection profile securely (no secrets in DB logs) | BE | Validates URL/auth; returns 400 on bad input; 503 if adapter missing | backend odata router/service | Open |
| ODATA-003 | `queryingEntities` | `QUERY_ENTITIES` | `POST /api/odata/query` | Deterministic results; pagination | BE | Enforces pagination; returns deterministic errors | backend odata router/service | Open |

### 11.3 File System Integration

**Source of truth (interactive stateflow)**: `e2etraceapp/src/machines/fileSystemIntegrationMachine.js`

| ID | State | Event | Action (invoke) | Backend dependency | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|
| FS-001 | `checkingHealth` | `CHECK_HEALTH` | `GET /api/filesystem/health` | Backend must reflect real file subsystem | BE | Returns `healthy`/`degraded` based on real directory existence + writability; no mock “always healthy” | `python_backend/graph_api/*` (filesystem router) | Verified |
| FS-002 | `uploading` | `UPLOAD_FILE` | `POST /api/filesystem/upload` | Upload path must be controlled + validated | BE | Enforces allowlist extensions/size; stores metadata; no arbitrary path traversal | backend filesystem router/service | Needs Verification |
| FS-003 | `parsing*` | `PARSE_XML/JSON/CSV` | `POST /api/filesystem/{type}/parse` | Parser must be deterministic | BE | Parsing results persisted to Postgres when used for ETL; UI doesn’t treat parsed data as truth | backend filesystem router + PLM ETL router | Open |
| FS-004 | `watching` | `START_WATCH` | `POST /api/filesystem/watch/start` | No demo “watch started” without watchdog | BE | Explicitly returns 501 (not implemented) until a real watcher exists | `python_backend/graph_api/filesystem_integration_router.py` | Verified |

**Local filesystem datasource test (Windows)**

- Script: `python_backend/smoke-filesystem-datasource.ps1`
- Run (PowerShell):
	- `./smoke-filesystem-datasource.ps1 -BaseUrl http://127.0.0.1:8011 -DataSourcePath "C:\\path\\to\\folder"`
- Notes:
	- The filesystem API accepts absolute paths for listing.
	- The quality scan filesystem fallback runs via `POST /api/analytics/quality/scan/{table_name}` with body `{ "data_source": "<absolute path>" }` and requires Postgres reachable (for persistence).
	- Verified end-to-end against a real Windows folder path (scan persisted; report retrievable via `GET /api/analytics/quality/reports/{scan_id}`).
	- Windows quirk: `netstat -ano | findstr :<port>` returns process exit code `1` when there are no matches (i.e., the port is not in use). Use `Select-String` if you want PowerShell-native behavior.

### 11.4 AWS Integration

**Source of truth (interactive stateflow)**: `e2etraceapp/src/machines/awsIntegrationMachine.js`

| ID | State | Event | Action (invoke) | Backend dependency | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|
| AWS-001 | `checkingHealth` | `CHECK_HEALTH` | `GET /api/aws/health` | Must reflect actual AWS creds/config | BE | Returns `status=unconfigured` (200) when credentials missing; does not pretend services are connected | backend aws router/service | Verified |
| AWS-002 | `uploadingToS3` | `S3_UPLOAD` | `POST /api/aws/s3/upload` | Uses real S3 SDK; validates bucket/key | BE | Explicit failure modes; no demo objects | backend aws router/service | Open |

### 11.5 Azure Integration

**Source of truth (interactive stateflow)**: `e2etraceapp/src/machines/azureIntegrationMachine.js`

| ID | State | Event | Action (invoke) | Backend dependency | Owner | Definition of Done | Files to touch | Status |
|---|---|---|---|---|---|---|---|---|
| AZ-001 | `connecting` | `CONNECT` | `GET /api/azure/health` | Must reflect real Azure creds/config | BE | Returns `status=unconfigured` (200) when no services configured; no fake "connected" | backend azure router/service | Verified |
| AZ-002 | `connected.uploadingBlob` | `UPLOAD_BLOB` | `POST /api/azure/blob/upload` | Uses real SDK; validates container | BE | Upload errors are explicit; no demo writes | backend azure router/service | Open |

