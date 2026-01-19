# End User Guide (UI / UX reference)

This guide is for end users and admins using the **GoodPoint AgenticAI** (GraphTrace) web UI.

The content below is derived from the actual UI routes and components in:

- Frontend routes: `agentic-restored/e2etraceapp/src/routes/index.jsx`
- Main layout/nav: `agentic-restored/e2etraceapp/src/layouts/e2etrace-root-layout.jsx`

## Access & basics

- UI (Vite dev): http://localhost:5173
- Backend health: http://localhost:8011/health
- API docs (Swagger): http://localhost:8011/docs

### Navigation model (what the UI looks like)

All pages share the same top chrome (layout `E2ETraceRootLayout`):

- **Header top bar**: GoodPoint logo + product title
- **Workflow progress**: compact indicator (`WorkflowProgress`) showing current flow context
- **Theme toggle**: switch **Light/Dark**
- **Primary navigation tabs**: Overview / Search / Migration / Workflows / Insights / Advanced / Settings
- **Secondary tabs**: context-sensitive shortcuts within the active primary group
- **Breadcrumbs**: shown on most pages (the home page is intentionally “full-bleed” and omits the breadcrumb strip)

If you ever get “lost”, the URL hash shows the current route, e.g. `/#/migration`.

## 1) Overview (Landing) — `/#/`

Route: `/` → `LandingPage`.

Use this page as the “home base”:

- It’s designed as a full-width landing/overview (no padded card wrapper)
- Use the top navigation to jump into the main experiences (Migration, Analytics, Graph, Admin)

## 2) Conversational Search — `/#/search`

Route: `/search` → `ConversationalSearchPage`.

The page has **two local tabs**:

- **Search** (default): renders `ConversationalSearchUI`
- **Configuration**: renders `PipelineConfigManager` (controls search/index/pipeline configuration)

UI elements you’ll use:

- A tab strip under the page header (Search / Configuration)
- Chat-style search interaction (Search tab)
- Configuration controls for pipelines (Configuration tab)

What it searches (as stated in the UI): PostgreSQL, Neo4j Graph, and OpenSearch.

## 3) Migration Wizard — `/#/migration`

Route: `/migration` → `MigrationPage` → `MigrationWizard`.

This is the primary end-user workflow. The wizard is explicitly described as a **5-step flow**:

1. **Connect**
2. **Discovery**
3. **Map**
4. **Validate**
5. **Execute**

### 3.1 Connect step (select systems)

What you do here:

- Choose a **source system** and **target system** for the migration
- Confirm that the necessary connections/configuration exist (often managed in Admin)

Expected outcome:

- The wizard is “ready” to run discovery using the selected source/target context

### 3.2 Discovery step (inspect what’s available)

What you do here:

- Run discovery against the selected source
- Review discovered entities/objects and readiness indicators

Expected outcome:

- A set of discovered entities that will later be mapped/validated

### 3.3 Map step (define mappings)

What you do here:

- Define how source entities/fields map to target entities/fields
- Capture mapping rules and any transformations required

Expected outcome:

- A mapping configuration used for validation and execution

### 3.4 Validate step (quality/consistency checks)

What you do here:

- Run validation checks before you execute
- Review validation results (errors/warnings) and fix mapping or inputs as needed

Expected outcome:

- Confidence that execution will succeed and produce expected outputs

### 3.5 Execute step (run & monitor)

What you do here:

- Trigger the migration execution
- Monitor progress/status and any emitted messages or results

Expected outcome:

- A completed workflow run (or a paused run awaiting approvals)

### 3.6 Approvals panel (human-in-the-loop)

The Migration Wizard integrates an approvals UI: `ApprovalsPanel`.

Typical actions you will see in the approvals area:

- View a list of **approval requests**
- **Create request** (when the workflow needs an explicit human decision)
- **Approve / Reject**
- **Copy token** / **Use token** (when a token must be provided to continue execution)

If execution pauses waiting for approval, create/approve the request and supply the token when prompted.

## 4) Workflow Management — `/#/workflow-manager`

Route: `/workflow-manager` → `WorkflowManagerPage`.

This page is a practical “operations view” for runs stored in Postgres.

### 4.1 Filters (top of the page)

The filter row includes:

- **Search** text box (placeholder: “name, id, description”) — press **Enter** or click **Apply**
- **Status** dropdown: `draft`, `configured`, `running`, `paused`, `completed`, `failed`, `archived`
- **Source type** text box (example placeholder: `postgres`)
- **Target type** text box (example placeholder: `neo4j`)
- Buttons: **Apply** and **Clear**

### 4.2 Table + pagination

Below the filters you’ll see:

- A summary bar (Showing / Total / Page / Page size)
- **Page size** selector: 10 / 25 / 50 / 100
- Pagination buttons: **Prev** / **Next**
- A **Refresh** button in the header to reload data

Behind the scenes this page calls `GET /api/workflows` and reads `X-Total-Count` for pagination.

### 4.3 Open a workflow

When you open a workflow from the list, you’ll navigate to:

- `/#/workflow/:workflowId` → `WorkflowDetailPage`

There is also a nested detail route under Graph Explorer:

- `/#/graph-explorer/workflow/:workflowId`

## 5) Analytics Hub — `/#/analytics`

Route: `/analytics` → `EnterpriseAnalyticsHub`.

### Deep links (tabs)

Analytics supports a `?tab=` query parameter and keeps it in sync with the UI.

Common deep links:

- Query Builder (default): `/#/analytics?tab=query-builder`
- Natural Language: `/#/analytics?tab=natural-language`
- Quality Reports: `/#/analytics?tab=quality-reports`

### 5.1 Query Builder tab

Use this to run read-only analytics queries (UI is a structured query builder).

Expected elements:

- A dataset/table selector and column selection
- A run/execute action
- Results table/grid

### 5.2 Natural Language tab

Use this to ask a question and have the system translate it into a query.

Expected elements:

- A natural-language prompt input
- A run action
- Rendered response + metadata

Note: provider availability depends on your Admin configuration (LLM providers / embedding models).

### 5.3 Quality Reports tab

Use this to view and export data quality scan results.

Expected elements:

- A list of quality scans/reports
- A details panel for a selected report
- Export actions (JSON/CSV)

Persistence behavior:

- When Postgres is configured, exports/scans can be persisted (the backend reports a `persisted` flag and a `source` label).

## 6) Data Lineage Visualizer — `/#/lineage`

Route: `/lineage` → `LineageVisualizerPage`.

This page combines Postgres workflows with (optional) Neo4j lineage.

Key UI elements:

- **Workflow dropdown** + **name search** field to find workflows
- A connectivity indicator derived from `/health` (Postgres/Neo4j)
- Tab strip with views such as **Lineage**, **Impact Analysis**, and **Audit Trail**
- Graph canvas powered by ReactFlow, including:
	- **MiniMap**
	- **Controls** (zoom/pan)
	- **Background** grid

Common actions:

- **Load lineage graph** for the selected workflow
- **Trace record lineage** by entering a record id, direction (both/upstream/downstream), and max depth

## 7) Graph Explorer — `/#/graph-explorer`

Route: `/graph-explorer` → `GraphExplorerPage`.

This page is an interactive Neo4j/graph view with both simple and advanced search.

### 7.1 Basic controls

Expect to find:

- Graph rendering (Cytoscape-based)
- Entity/relationship filters
- Limit control (defaults to 100)

### 7.2 Advanced search (Cypher-style)

The advanced search UI builds a Cypher `WHERE` clause from conditions.

Operators available in the UI include:

- `=` / `<>`
- `CONTAINS` / `STARTS WITH` / `ENDS WITH`
- `=~` (regex)
- `>` / `>=` / `<` / `<=`
- `IN`
- `IS NULL` / `IS NOT NULL`

The page can also show the **generated Cypher** for transparency.

### 7.3 Workflow filter

Graph Explorer can load a list of workflows from `GET /api/workflows` and lets you scope exploration to a workflow.

## 8) Observability & Monitoring — `/#/observability`

Route: `/observability` → `ObservabilityDashboard`.

Key UI elements:

- Refresh interval dropdown (10s / 30s / 1min / 5min)
- **Refresh Now** button
- Metric cards for:
	- Data Quality Score
	- Data Issues
	- Active Alerts
	- Agentic System status (when available)
- Alerts list showing severity icon, message, component, and timestamp

Backend endpoints used include:

- `/api/monitoring/alerts`
- `/api/monitoring/data-quality`
- `/api/agentic/system/status` (best-effort)

## 9) Self-Healing Monitor — `/#/self-healing`

Route: `/self-healing` → `SelfHealingMonitorPage`.

This is a real-time monitor for self-healing orchestration.

Key UI elements/actions:

- A WebSocket connection to: `/api/self-healing/ws/monitor`
- Panels for circuit breakers and dead-letter queue (DLQ)
- Actions to execute test tasks (with optional failure simulation)

## 10) Multi-Modal Analyzer — `/#/multimodal`

Route: `/multimodal` → `MultiModalAnalyzerPage`.

Use this page to upload documents and run vision-based extraction.

Key UI elements:

- Drag-and-drop upload zone + file picker
- Configuration panel:
	- Vision model selector (e.g. `llava:latest`, `bakllava:latest`)
	- Extraction method radio buttons (Vision LLM / OCR Only / Hybrid)
	- “Enable OCR Fallback” checkbox
	- Temperature slider

Backend endpoints used include:

- `GET /api/multimodal/supported-formats`
- `POST /api/multimodal/analyze-file` (multipart upload)

## 11) Rule Engine — `/#/rule-engine`

Route: `/rule-engine` → `RuleEngineManagement`.

Use this page to manage data quality / ETL rules.

Key UI elements (as implemented):

- Tab navigation across rule engine modes (rule sets, rules, execution/results, quarantine, etc. — depending on active state)
- Rule sets table with actions:
	- View rules
	- Execute rules
	- Edit
	- Delete
- Hierarchical rule viewing (parent/child rules)
- Status/severity/level badges to help triage outcomes

## 12) Settings & Admin — `/#/settings` and `/#/admin`

Routes:

- `/settings` → `E2ETracePropertyPalette`
- `/admin` and `/settings/admin` → `AdminSettingsPage` → `AdminConfigManager`

### 12.1 Admin configuration tabs

The Admin Config Manager has these top-level tabs:

- **LLM Providers**
- **Embedding Models**
- **Connection Settings (Data Sources)**
- **System Settings**
- **Feature Flags**

Common actions:

- Add/edit/delete configuration items
- **Test connection** actions for connections/providers
- View basic **health** data (loaded from `/api/admin/config/health`)

## 13) API Docs — `/#/api-docs`

Route: `/api-docs` → `OpenApiDocsPage`.

This page embeds the backend Swagger UI:

- IFrame: `/api/docs`
- Direct OpenAPI JSON: `/api/openapi.json`

## Troubleshooting

- **UI shows HTML instead of data**: the backend might not be running (Vite can serve an HTML fallback). Verify `http://localhost:8011/health`.
- **503 errors**: many optional integrations fail closed when not configured (Neo4j/OpenSearch/LLM/Cloud connectors). Configure in Admin and retry.
- **Local file datasource blocked**: set `GRAPH_TRACE_ALLOWED_LOCAL_ROOTS` (semicolon-delimited) to allowlist import roots.
