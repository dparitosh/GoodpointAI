# GraphTrace — User Guide

## Getting Started

After installation (see [INSTALLATION.md](./INSTALLATION.md)), start the stack:

```powershell
.\.venv\Scripts\Activate.ps1
.\graphtrace.ps1 -Start
```

Wait 10–15 seconds, then open these URLs:

| Endpoint | URL |
| :--- | :--- |
| **Web UI** | http://localhost:5173 |
| **Backend Health** | http://localhost:8011/health |
| **Swagger API Docs** | http://localhost:8011/docs |

> The UI uses hash routing — URLs look like `http://localhost:5173/#/analytics`.

---

## Navigation Structure

The top nav bar has **7 primary tab groups**. Some groups expand into sub-tabs.

| # | Primary Tab | Sub-Tabs | Routes |
| :--- | :--- | :--- | :--- |
| 1 | **Overview** | *(single page)* | `/` |
| 2 | **Search** | Conversational Search | `/search` |
| 3 | **Migration** | Migration Wizard | `/migration` |
| 4 | **Rule Engine** | Rule Engine | `/rule-engine` |
| 5 | **Insights & Reports** | Data Lineage, Analytics, DQ Dashboard, Data Discovery, Observability, Self-Healing Monitor, Reporting Hub | `/lineage`, `/analytics`, `/dq-dashboard`, `/data-discovery`, `/observability`, `/self-healing`, `/reporting-hub` |
| 6 | **Advanced Tools** | Graph Explorer, Multi-Modal Analyzer, Batch File Processor, API Docs | `/graph-explorer`, `/multimodal`, `/batch-processor`, `/api-docs` |
| 7 | **Settings** | Preferences, Admin Config | `/settings`, `/admin` |

---

## Tab 1: Overview (`/`)

Landing page with quick-action cards and system status.

| Element | Description |
| :--- | :--- |
| **Quick Action Cards** | Jump to Migration Wizard, Analytics, Graph Explorer, or Admin. |
| **System Status** | At-a-glance view of backend connectivity (Postgres, Neo4j, OpenSearch). |

---

## Tab 2: Search (`/search`)

Chat-style conversational search interface. Powered by the **Data Analyst Agent**.

| Feature | Description |
| :--- | :--- |
| **Natural Language Input** | Type a question in plain English (e.g., "How many failed workflows this week?"). |
| **Auto-Generated Query** | The agent translates your question into SQL or Cypher. Click "Show Query" to see it. |
| **Results Table** | Structured results rendered in a data table. |

---

## Tab 3: Migration Wizard (`/migration`)

Five-step data migration workflow. Powered by the **ETL Orchestrator Agent**.

| Step | Name | What You Do | What the Agent Does |
| :--- | :--- | :--- | :--- |
| 1 | **Connect** | Select a source system (e.g., Postgres PLM DB) and a target (e.g., Neo4j). | Validates connectivity to both endpoints. |
| 2 | **Schema / Discovery** | Click "Run Discovery". | Scans source DB metadata: tables, columns, types, foreign keys. Returns a schema report. |
| 3 | **Map** | Review AI-suggested field mappings. Adjust confidence thresholds. Approve or reject. | Uses embeddings to match source → target columns (e.g., `part_no` → `ComponentID`, 92% confidence). |
| 4 | **Validate** | Click "Run Validation". Review pass/fail report. | Runs SODA data quality checks: null counts, type mismatches, business rule violations. |
| 5 | **Execute** | Click "Start Migration". Monitor progress bar and log output. | Executes the ETL pipeline. Logs each batch. Pauses for human approval if configured. |

**Approvals Panel**: If a step requires human sign-off, an approval request appears. You can Approve, Reject, or copy an approval token.

---

## Tab 4: Rule Engine (`/rule-engine`)

Define data quality rules and run them against datasets.

| Feature | Description |
| :--- | :--- |
| **Rule Sets** | Create groups of validation rules (e.g., "PLM Quality Rules"). |
| **Individual Rules** | Define checks like "Email must match regex `.*@.*`" or "Cost > 0". Supports severity levels: Warning, Error, Blocker. |
| **Execution History** | Run rule sets against datasets and view pass/fail results. |
| **Quarantine** | Records that fail critical rules are quarantined for manual review. |

---

## Tab 5: Insights & Reports

This group contains **7 sub-tabs** for analytics, monitoring, and reporting.

### 5a. Data Lineage (`/lineage`)

| Element | Description |
| :--- | :--- |
| **Workflow Selector** | Pick a workflow to visualize its data flow. |
| **Lineage Graph** | Interactive ReactFlow canvas showing Source → Transformation → Target nodes. Color-coded by type. |
| **Impact Analysis** | Select a node to see all downstream consumers. |
| **Audit Trail** | View change history for the selected workflow. |

### 5b. Analytics Hub (`/analytics`)

| Tab (internal) | Description |
| :--- | :--- |
| **Query Builder** | Visual drag-and-drop query builder. Select a data source (Postgres, Neo4j, OpenSearch, SODA, GraphQL, Ollama LLM), pick entities/fields, add filters, execute. Results render in a table. |
| **Natural Language** | Type an English question. The **Data Analyst Agent** generates and executes a query. The **Visualization Agent** auto-selects the best chart type. |
| **Quality Reports** | Browse historical data quality scan results. Export as JSON or CSV. |

### 5c. DQ Dashboard (`/dq-dashboard`)

Data Quality scan dashboard. View scan results, scores, and trends across configured data sources.

### 5d. Data Discovery (`/data-discovery`)

Explore and catalog data sources. Browse schema metadata, table statistics, and column profiles.

### 5e. Observability (`/observability`)

| Element | Description |
| :--- | :--- |
| **Metric Cards** | Data Quality Score, Active Alerts, Agentic System Status. |
| **Alerts List** | Real-time alerts with severity, message, component, and timestamp. |
| **Refresh Controls** | Auto-refresh intervals: 10s / 30s / 1min / 5min. |

### 5f. Self-Healing Monitor (`/self-healing`)

| Element | Description |
| :--- | :--- |
| **Circuit Breakers** | Pipelines auto-paused due to error thresholds. |
| **Dead Letter Queue** | Failed messages queued for retry or manual intervention. |
| **Test Task** | Trigger a test task with optional failure simulation to verify self-healing. |

### 5g. Reporting Hub (`/reporting-hub`)

Browse, view, and export generated reports.

---

## Tab 6: Advanced Tools

Power-user tools for direct data exploration and document processing.

### 6a. Graph Explorer (`/graph-explorer`)

| Element | Description |
| :--- | :--- |
| **Graph Canvas** | Interactive Cytoscape-powered graph visualization. |
| **Search / Filter** | Filter by entity type, relationship type, and properties. Supports Cypher operators: `CONTAINS`, `STARTS WITH`, `=~` (regex), `IN`, `IS NULL`. |
| **Generated Cypher** | View the raw Cypher query that was executed. |
| **Workflow Scope** | Filter the graph to show only nodes related to a specific workflow. |

Clicking a workflow node navigates to `/graph-explorer/workflow/:workflowId` for a detail view.

### 6b. Multi-Modal Analyzer (`/multimodal`)

| Element | Description |
| :--- | :--- |
| **Upload Zone** | Drag-and-drop files (PDF, images, documents). |
| **Vision Model** | Select a model (e.g., `llava:latest`, `bakllava:latest`). |
| **Extraction Method** | Choose Vision LLM / OCR Only / Hybrid. |
| **Results** | Extracted structured data from the uploaded document. |

### 6c. Batch File Processor (`/batch-processor`)

Upload and process multiple files in batch. Useful for bulk ETL operations and document extraction.

### 6d. API Docs (`/api-docs`)

Embedded Swagger UI — same as http://localhost:8011/docs but accessible within the app.

---

## Tab 7: Settings

### 7a. Preferences (`/settings`)

User-level display preferences (theme, language).

### 7b. Admin Config (`/admin`)

Admin-only configuration panel with these internal tabs:

| Admin Tab | Description |
| :--- | :--- |
| **LLM Providers** | Configure connections to Ollama, Azure OpenAI, or other LLM endpoints. Test connection. |
| **Embedding Models** | Select and configure the embedding model for semantic search and field mapping. |
| **Connection Settings** | Manage data source connections (Postgres, Neo4j, OpenSearch, PLM systems). Add / Edit / Delete / Test. Supports OAuth 2.0 for Azure API Gateway. See [OAuth Configuration Guide](./OAUTH_CONFIGURATION.md). |
| **System Settings** | Core runtime settings (CORS origins, rate limits, log levels). |
| **Feature Flags** | Toggle experimental features on/off. |

> **Note:** Most runtime settings can be changed in Admin Config without restarting the backend. Changes are stored encrypted in PostgreSQL.

---

## Troubleshooting

| Problem | Solution |
| :--- | :--- |
| **UI shows blank page or raw HTML** | Backend is not running. Verify: `curl http://localhost:8011/health` |
| **503 errors on optional features** | Neo4j / OpenSearch / LLM not configured. Set them up in Admin Config (`/admin`). |
| **"Unauthorized" on API calls** | Auth is enabled. Check `GRAPH_TRACE_AUTH_REQUIRED` in `.env` and supply a valid JWT. |
| **Migration Wizard stuck on "Discovering"** | Check the multiplexer terminal for ETL Orchestrator Agent errors. |
| **PLM connection fails with OAuth** | Verify client credentials in Azure AD. See [OAuth Configuration Guide](./OAUTH_CONFIGURATION.md). |
| **Graph Explorer shows no data** | Neo4j is not configured or has no data. Configure Neo4j in Admin Config, then run a migration. |
| **Search returns "No agent available"** | Agents are not running. Restart with `.\graphtrace.ps1 -Start`. |
