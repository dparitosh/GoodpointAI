# Reference Recipe (Enhanced): Postgres + Neo4j + OpenSearch + Agents + Spark(openCypher)

This is a repo-aligned enhancement of the original “reference recipe” (the ChatGPT share). It keeps the same structure (sections 1–10), but updates it for:

- **No mock/sample/demo** behavior anywhere.
- **Fail-closed** integration policy: if a dependency is not configured, API returns **HTTP 503** and the UI shows **N/A**.
- **Single Postgres** as the system-of-record for ETL + quality + governance.
- **Neo4j derived from Postgres**, not a parallel truth store.
- **OpenSearch** for retrieval/search only (not transactional state), with **`opensearch-py==3.3.1`** pinned.
- **Upgrade-ready scale path** for graph builds using **Apache Spark + openCypher**.

## 1. First Principle: Separate Reasoning from Truth

Agents reason about actions; they do not define truth.

| Layer | What it does | What must be deterministic | Where it lives |
|---|---|---|---|
| Truth / determinism | correctness, audit | always | Postgres + deterministic validators |
| Structure / impact | relationships + blast radius | derived from truth | Neo4j (derived) |
| Search / recall | retrieval + similarity | optional | OpenSearch |
| Reasoning / planning | orchestration decisions | constrained by truth | Agentic AI |

Rule: **agents MUST NOT fabricate data**, substitute sample data, or “pretend integrations are healthy”.

## 2. Canonical Data Stores (Non-negotiable)

### PostgreSQL — system of record

Postgres is the authoritative store for:

- ETL run tracking and audit
- staging payloads
- canonical PLM tables (parts, BOM, etc.)
- persisted quality rules and results
- (future) agent decisions + human approvals

Fail-closed: if Postgres isn’t configured (`DATABASE_URL` missing/not Postgres), endpoints that require it return **503**.

### Neo4j — digital thread graph (derived)

Neo4j is not the truth store. Neo4j is a derived substrate for:

- dependency/impact analysis
- relationship traversal (BOM, revisions, documents, ECO/ECR)
- graph constraints and graph-oriented validation

Operating modes:

- **Best-effort** (optional): requests still succeed, graph emission is skipped if Neo4j is unavailable.
- **Strict** (required): graph-backed endpoints return **503** if Neo4j is not configured/healthy.

### OpenSearch — retrieval only

Use OpenSearch for:

- text search over PLM/CAD metadata
- recall of past failures/fixes
- retrieval for agent memory

Do not put transactional ETL state here.

Hard requirement: client pinned to **`opensearch-py==3.3.1`**.

Fail-closed: OpenSearch-backed endpoints return **503** if OpenSearch is not configured/healthy.

## 3. Python: The Orchestration Spine

FastAPI is the control plane:

- creates runs and persists run state
- stages payloads
- triggers deterministic transforms and validations
- persists results so the UI renders real status
- optionally coordinates derived writes to Neo4j/OpenSearch

Invariant: **UI renders from persisted truth (Postgres)** or shows **N/A**. Never “demo dashboards”.

## Repo Implementation Notes (What Exists Today)

This repo contains a mix of **DB-backed** and **file-backed** features. The intent is still aligned with the “fail-closed / no fabricated data” policy.

### Data Mapping

- **CRUD + validation**: implemented under `python_backend/graph_api/data_mapping_router.py` (`/api/data-mapping/*`).
- **Storage**: currently **local JSON files** created at runtime (dev artifact):
	- `python_backend/mapping_rules.json`
	- `python_backend/mapping_templates.json`
- **Execution**: `/api/data-mapping/rules/{id}/execute` returns **HTTP 503** until source/target connectors and an execution engine are configured (intentional fail-closed).

### Reporting + Spreadsheet

- **Persisted reports**: implemented under `python_backend/graph_api/reports_router.py` (`/api/reports/*`) and stored in Postgres (`reports` table).
- **Fail-closed**: if the configured DB is unreachable, report endpoints return **HTTP 503** with a clear error.
- **Spreadsheet UX**: `e2etraceapp` provides import/export and charting. The backend includes `/api/convert` but only implements **JSON → CSV** currently; other conversions return “not yet implemented”.

## 4. Data Quality Stack — The Correct Way to Combine Them

### Current repo reality

- “SODA-style” exists in UI/docs; **Soda Core (Postgres) is now integrated as an optional, fail-closed endpoint**.
- There is an analytics quality router that runs deterministic file/folder parse checks.
- The PLM ETL happy-path persists rules/results in Postgres (`dq_rules`, `dq_results`).

### Target state (optional) — Soda Core as a gate on Postgres tables

When you integrate Soda Core for Postgres:

- install Soda’s Postgres integration (commonly `soda-core-postgres`)
- run checks against **real Postgres tables only**
- persist outcomes into Postgres (same results table), so UI never depends on transient scan output

Fail-closed:

- if Postgres missing: **503**
- if Soda missing and endpoint contract is “Soda scan”: **503**

## 5. CAD & Geometry: Keep It Offline and Deterministic

Do not ask agents to read CAD binaries.

Preferred model:

- extract deterministic geometry features out-of-band (CAD tooling)
- store extracted metadata in Postgres
- validate in Postgres (and optionally in Neo4j for graph-integrity semantics)

## 6. Agentic AI: Where It Actually Adds Value

Agents SHOULD:

- decide which checks to run (from configuration)
- interpret failures, propose remediation
- decide retry vs halt
- request human approvals

Agents MUST NOT:

- invent data
- bypass deterministic gates
- mask missing integrations

## 7. How Neo4j + Quality + Agents Work Together

Pattern:

- Postgres validation fails (truth)
- Neo4j explains impact radius (derived structure)
- agent explains remediation options (reasoning)

## 8. OpenSearch: Agent Memory & UX Boost

Use OpenSearch for retrieval of:

- run summaries
- historical failures and fixes
- searchable metadata

Fail-closed: if OpenSearch isn’t configured, OpenSearch endpoints return **503** and UI shows N/A.

## 9. Recommended Minimal Stack (Opinionated)

Keep:

- Python (FastAPI control plane)
- Postgres (truth)
- Neo4j (derived graph)
- OpenSearch (optional retrieval)

Add for scale (graph builds):

- Apache Spark jobs reading Postgres and writing derived Neo4j graphs

## 10. One-Sentence “Right Recipe”

Use Python to orchestrate deterministic truth in Postgres, derive structure in Neo4j, enable retrieval in OpenSearch, and scale graph builds via Spark (openCypher), while agents reason only about actions—not truth.

## Spark + openCypher (explicit implementation pointer)

There are two valid ways to get “Spark + Cypher”:

1) **Neo4j Spark Connector (recommended at scale):** Spark sends Cypher; Neo4j executes Cypher.
2) **Neo4j Python driver (good for small/medium syncs):** Spark computes DataFrames; the job uses Bolt + `MERGE` to write a derived graph.

This repo includes a minimal Spark runner under `agentic-restored/spark_jobs/` that reads Postgres `plm_parts` / `plm_bom_items` for a `run_id` and writes a derived graph into Neo4j.
