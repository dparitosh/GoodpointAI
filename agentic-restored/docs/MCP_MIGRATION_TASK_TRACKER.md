# MCP Migration Task Tracker (GoodpointAI)

This tracker translates the architecture in `docs/AI PLM Data Migration with MCP.txt` into actionable implementation work in this repository.

## Status snapshot (as of 2026-01-18)

The **core MCP “vertical slice” (P0)** is now **implemented** (sample-based):

- [x] Minimal Migration Runs API (`/api/migrations/runs`) with status transitions + lightweight staging
  - Backend: `python_backend/graph_api/mcp_migration_runs_router.py`
  - Test coverage: `python_backend/tests/test_mcp_migration_runs.py`
- [x] Minimal MCP Source/Target stdio servers (call backend over HTTP)
  - Backend: `python_backend/mcp_servers/source_server.py`, `python_backend/mcp_servers/target_server.py`
- [x] Wizard creates an MCP run when Discovery starts (best-effort)
  - Frontend: `e2etraceapp/src/components/migration-wizard/MigrationWizard.jsx`

And the **Neo4j staging bridge (P0.2)** is now in place:

- [x] Staged *samples* can be materialized into Neo4j
  - Backend: `POST /api/migrations/runs/{run_id}/materialize`
  - Service: `python_backend/services/mcp_staging_graph_writer.py`
  - MCP Target helper: `python_backend/mcp_servers/target_server.py` (`materialize_run` tool)

And the **publish step (OpenSearch) is now separated from lineage**:

- [x] Publish/index staged samples to OpenSearch (optional, target-specific)
  - Backend: `POST /api/migrations/runs/{run_id}/publish`
  - Notes:
    - **Neo4j remains canonical** for lineage/traceability (materialize always writes to Neo4j).
    - Publish indexes to OpenSearch **and** records publish events back into Neo4j (`MCPTargetDocument`).

Governance is now end-to-end for the first gated write action:

- [x] HITL approvals + approval gating for materialize
  - Backend: `python_backend/services/mcp_approvals.py`, `python_backend/graph_api/mcp_migration_runs_router.py`
  - Header: `X-MCP-Approval-Token`
- [x] Action-specific approval gating for publish (OpenSearch)
  - Backend: `POST /api/migrations/runs/{run_id}/publish` is gated when approvals are enabled
  - Approval request action: `publish`
- [x] Append-only audit logging for run + approvals actions
  - Backend: `python_backend/services/mcp_audit_log.py`
- [x] Frontend approvals UX integrated into Wizard Execute step (pause/retry)
  - Frontend: `e2etraceapp/src/components/migration-wizard/ApprovalsPanel.jsx`, `MigrationWizard.jsx`
  - Notes: token selection is action-scoped (`materialize` vs `publish`).

Validation snapshot (local): backend pytest + frontend lint + frontend unit tests are passing.

## Pending tasks (prioritized)

### Next 5 (recommended order)
- [ ] Full extraction beyond “count + first 5 rows” staging
  - Stream/paginate larger batches
  - Stage raw payloads safely (size limits, chunking, backpressure)
  - Materialize full batches (not just samples)

- [ ] Index staging graph summaries into OpenSearch (optional but high leverage)
  - This is distinct from “publish”: the goal here is searchable *staging summaries* / lineage metadata.
  - Create an index + mapping
  - Index `MCPStagedEntity` summary payloads
  - Enable keyword search over staged content

- [ ] Add contract tests for MCP tool servers
  - Verify tool names + payload shapes
  - Verify “no stdout logs” invariant for stdio servers

- [ ] Add an integration test for the slice
  - Create run → stage → request approval → approve → materialize (happy path)

- [ ] Add an operator-facing audit viewer (API + minimal UI)
  - List audit events for a run (`mcp_audit_event`)
  - Basic filtering (action, time range)

### Hardening / Ops (when you’re ready)
- [ ] Auth for MCP HTTP transport (when enabled)
- [ ] Origin validation + localhost binding defaults
- [ ] Optional: small embeddings microservice template for `EMBEDDINGS_URL`

However, several **prerequisites that the MCP slice will build on** are already implemented in this repo:

- [x] Admin-managed “Connection Settings” surfaced as Wizard data sources
  - Backend: `python_backend/graph_api/data_sources_router.py` (adds `conn_<id>` sources)
  - Frontend: `e2etraceapp/src/components/migration-wizard/MigrationWizard.jsx` (default filter + “Show all” toggle)
- [x] Admin Config `local_folder` sources are fully usable for Discovery sampling
  - Backend: `GET /api/data-sources/{source_id}/sample` supports `conn_<id>` for `local_folder` / `file`
  - Security: allowlisted local roots via `GRAPH_TRACE_ALLOWED_LOCAL_ROOTS` (see `python_backend/.env.example`)
- [x] Admin Config API metadata endpoint for dynamic UI/schema rendering
  - Backend: `GET /api/admin/config/meta` in `python_backend/routers/admin_config_router.py`
- [x] Connection types expanded (API / REST API / WEBAPI / OPENAPI / ODATA) + HTTP-based test flow
  - Backend: `python_backend/routers/admin_config_router.py`
  - Frontend: `e2etraceapp/src/components/admin-config-manager.jsx`
- [x] Default embeddings strategy avoids heavy local deps
  - Backend: `python_backend/services/embeddings_service.py` (uses `EMBEDDINGS_URL` with graceful fallback in callers)
- [x] OpenSearch usage consolidated behind a wrapper service
  - Backend: `python_backend/services/opensearch_service.py`

## How to use
- Treat **P0** as “must ship” to get an end-to-end MCP-based migration slice working.
- Keep tasks small (1–3 days), with explicit acceptance criteria.
- Link PRs/issues to each row as work progresses.

Quick validation (local):
- Start backend (FastAPI) and frontend (Vite)
- Open Migration Wizard → run Discovery → verify “MCP run: <id>” appears
- Verify backend endpoints:
  - `POST /api/migrations/runs`
  - `POST /api/migrations/runs/{run_id}/transition`
  - `POST /api/migrations/runs/{run_id}/stage`

## P0 — End-to-end vertical slice

### 1) MCP Servers: Source + Target (minimal)
- [x] Implement a **Source MCP Server** (stdio first)
  - Area: `agentic-restored/python_backend/` (new module)
  - Tools (minimum):
    - `list_entities`
    - `fetch_entity`
    - `sample_rows`
  - Acceptance:
    - Starts via stdio without writing logs to stdout.
    - Tools callable via MCP Inspector.

- [x] Implement a **Target MCP Server** (stdio first)
  - Tools (minimum):
    - `get_schema`
    - `upsert_entity`
    - `bulk_upsert`
  - Acceptance:
    - Schema retrieval works and is cached.

### 2) Staging graph (Neo4j) as canonical intermediate
- [x] Create “staging graph writer” service
  - Area: `agentic-restored/python_backend/services/`
  - Acceptance:
    - Can persist nodes/relationships for a sample extraction.
    - Has idempotent upsert semantics.
  - Implementation: `python_backend/services/mcp_staging_graph_writer.py` + `POST /api/migrations/runs/{run_id}/materialize`

- [x] Add basic provenance + audit nodes
  - Acceptance:
    - Each staged entity stores source system, source id, batch id, and timestamps.
  - Implementation: `(:MCPStagedEntity)-[:PROVENANCE]->(:MCPProvenance)` with run/entity/record_key and timestamps

### 2.1) Publish artifacts (OpenSearch) while preserving Neo4j lineage

- [x] Add a dedicated publish endpoint for OpenSearch targets
  - Backend: `POST /api/migrations/runs/{run_id}/publish`
  - Acceptance:
    - Only OpenSearch targets can be published (others return 409).
    - Index IDs are deterministic for traceability.
    - Publish events are written back into Neo4j (run → published doc → staged entity linkage when available).
  - Implementation:
    - OpenSearch: `python_backend/graph_api/mcp_migration_runs_router.py`
    - Neo4j lineage: `python_backend/services/mcp_staging_graph_writer.py` (`record_published_documents`)

### 3) Operator flow: Migration Wizard integration
- [x] Make Migration Wizard able to start a “migration run”
  - Frontend: `agentic-restored/e2etraceapp/src/components/migration-wizard/`
  - Backend: add `POST /api/migrations/runs` and `GET /api/migrations/runs/{id}`
  - Acceptance:
    - Run shows status transitions (created → discovery → proposal → executing → completed/failed).

## P1 — Search/Indexing consolidation (OpenSearch-first)

### 4) Prefer OpenSearch capabilities for retrieval
- [x] Use OpenSearch for semantic/vector/hybrid search where configured
  - Existing: `python_backend/services/opensearch_service.py`, `routers/conversational_search_router.py`

- [ ] Index staging graph summaries into OpenSearch
  - Acceptance:
    - Index creation + mapping for text + vectors.
    - Can search staged content by keyword.

### 5) Embeddings strategy: external service by default
- [x] Default runtime avoids heavy embedding libs; uses `EMBEDDINGS_URL` with deterministic fallback
  - See: `python_backend/services/embeddings_service.py`

- [ ] Provide a small optional embeddings microservice template
  - Acceptance:
    - Runs locally and returns embeddings for a text.

## P2 — Human-in-the-loop governance

### 6) Approval gates for write/delete
- [x] Add approval state machine to migration runs
  - Backend endpoints:
    - `GET  /api/migrations/runs/{run_id}/approvals`
    - `POST /api/migrations/runs/{run_id}/approvals` (creates request + returns token)
    - `POST /api/migrations/runs/{run_id}/approvals/{approval_id}/approve`
    - `POST /api/migrations/runs/{run_id}/approvals/{approval_id}/reject`
  - Enforcement:
    - `POST /api/migrations/runs/{run_id}/materialize` is gated when `GRAPH_TRACE_APPROVALS_REQUIRED=true`
    - Caller must provide `X-MCP-Approval-Token: <token>` header for an **approved** request (action=`materialize`).
    - `POST /api/migrations/runs/{run_id}/publish` is gated when `GRAPH_TRACE_APPROVALS_REQUIRED=true`
    - Caller must provide `X-MCP-Approval-Token: <token>` header for an **approved** request (action=`publish`).
  - Code:
    - `python_backend/services/mcp_approvals.py`
    - `python_backend/graph_api/mcp_migration_runs_router.py`
  - Acceptance:
    - Any write/bulk write can be protected behind an explicit approval token (materialize is the first gated operation).

- [x] Append-only audit log
  - Implementation:
    - `python_backend/services/mcp_audit_log.py` persists `mcp_audit_event` rows to `reports` (best-effort)
    - Events emitted from run lifecycle endpoints + approvals endpoints
  - Acceptance:
    - Every run action is recorded with timestamp/run id and optional actor metadata.

Quick validation (local):
- Create a run, then create/approve an approval request for `materialize`, then call materialize with header token.
- Enable enforcement:
  - Set `GRAPH_TRACE_APPROVALS_REQUIRED=true` in `python_backend/.env` (loaded when `GRAPH_TRACE_LOAD_DOTENV=true`).

## P3 — Hardening & Ops

### 7) Security + auth
- [ ] Auth for MCP HTTP transport (when enabled)
- [ ] Origin validation + localhost binding defaults

### 8) Testing
- [ ] Add contract tests for MCP tools
- [ ] Add integration tests for “slice” run

## Notes / pointers
- Default backend dependency install uses `agentic-restored/python_backend/requirement.txt` (intentionally small).
- Optional integrations (bigger deps) belong in `agentic-restored/python_backend/requirements_external_integrations.txt`.
