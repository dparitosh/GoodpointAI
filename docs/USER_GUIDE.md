# End User Guide

## Getting Started

| Endpoint | URL |
| :--- | :--- |
| **Web UI** | [http://localhost:5173](http://localhost:5173) |
| **Backend Health** | [http://localhost:8011/health](http://localhost:8011/health) |
| **API Docs (Swagger)** | [http://localhost:8011/docs](http://localhost:8011/docs) |

---

## Navigation Bar

The top nav bar is organized into **7 primary tab groups**. Each group may contain sub-tabs.

---

### Tab 1: Overview (`/`)
**Purpose**: Landing page and home dashboard.

| Element | Description |
| :--- | :--- |
| Quick Action Cards | Jump to Migration Wizard, Analytics, Graph Explorer, or Admin. |
| System Status | At-a-glance view of backend connectivity. |

---

### Tab 2: Search (`/search`)
**Purpose**: Ask questions about your data in plain English.

| Sub-Tab | Description |
| :--- | :--- |
| **Search** (default) | Chat-style interface. Type a question (e.g., "How many failed workflows this week?"). The **Data Analyst Agent** translates it to SQL/Cypher and returns results. Click "Show Query" to see the generated SQL. |
| **Configuration** | Manage search pipelines, index settings, and embedding model selection. Admin-level controls for tuning search behavior. |

---

### Tab 3: Migration (`/migration`)
**Purpose**: The primary data migration workflow. Powered by the **ETL Orchestrator Agent**.

This is a **5-step wizard**:

| Step | Name | What You Do | What the Agent Does |
| :--- | :--- | :--- | :--- |
| 1 | **Connect** | Select a Source system (e.g., Postgres PLM DB) and a Target system (e.g., Neo4j). | Validates connectivity to both endpoints. |
| 2 | **Schema / Discovery** | Click "Run Discovery". | Agent scans source DB metadata: tables, columns, types, foreign keys. Returns a structured schema report. |
| 3 | **Map** | Review AI-suggested field mappings. Adjust confidence thresholds. Approve or reject mappings. | Agent uses embeddings to match source columns to target properties (e.g., `part_no` -> `ComponentID`, 92% confidence). |
| 4 | **Validate** | Click "Run Validation". Review the report of pass/fail checks. | Agent runs SODA data quality checks: null counts, type mismatches, business rule violations. |
| 5 | **Execute** | Click "Start Migration". Monitor the progress bar and log output. | Agent executes the ETL pipeline. Logs each batch. Pauses for human approval if configured. |

**Approvals Panel**: If a step requires human sign-off, an approval request appears. You can Approve, Reject, or copy an approval token.

---

### Tab 4: Workflows / Rule Engine (`/rule-engine`)
**Purpose**: Define data quality rules and monitor workflow runs.

| Sub-Feature | Description |
| :--- | :--- |
| **Rule Sets** | Create groups of validation rules (e.g., "PLM Quality Rules"). |
| **Individual Rules** | Define checks like "Email must match regex `.*@.*`" or "Cost > 0". Supports severity levels (Warning, Error, Blocker). |
| **Execution History** | Run rule sets against datasets and view pass/fail results. |
| **Quarantine** | Records that fail critical rules are quarantined for manual review. |

---

### Tab 5: Insights (`/analytics` group)
**Purpose**: Deep-dive reporting and visual analysis. Contains multiple sub-pages:

#### Sub-Tab 5a: Analytics Hub (`/analytics`)

| Internal Tab | Description |
| :--- | :--- |
| **Query Builder** | Visual drag-and-drop query builder. Select a data source (Postgres, Neo4j, OpenSearch, SODA, GraphQL, Ollama LLM), pick entities and fields, add filters, and execute. Results render in a table. |
| **Natural Language** | Type an English question. The **Data Analyst Agent** generates and executes a query. The **Visualization Agent** auto-selects the best chart type for the returned data. |
| **Quality Reports** | Browse historical data quality scan results. Export reports as JSON or CSV. |

#### Sub-Tab 5b: Data Lineage (`/lineage`)

| Element | Description |
| :--- | :--- |
| **Workflow Selector** | Pick a workflow to visualize its data flow. |
| **Lineage Graph** | Interactive ReactFlow canvas showing Source -> Transformation -> Target nodes. Color-coded by type. |
| **Impact Analysis Tab** | Select a node to see all downstream consumers. |
| **Audit Trail Tab** | View change history for the selected workflow. |

#### Sub-Tab 5c: Reporting (`/reporting`)

| Element | Description |
| :--- | :--- |
| Report browser | View and export generated reports. |

#### Sub-Tab 5d: Observability (`/observability`)

| Element | Description |
| :--- | :--- |
| **Metric Cards** | Data Quality Score, Active Alerts, Agentic System Status. |
| **Alerts List** | Real-time alerts with severity, message, component, and timestamp. |
| **Refresh Controls** | Auto-refresh every 10s / 30s / 1min / 5min. |

#### Sub-Tab 5e: Self-Healing Monitor (`/self-healing`)

| Element | Description |
| :--- | :--- |
| **Circuit Breakers** | Pipelines that have been auto-paused due to error thresholds. |
| **Dead Letter Queue** | Failed messages queued for retry or manual intervention. |
| **Test Task** | Trigger a test task with optional failure simulation to verify self-healing behavior. |

---

### Tab 6: Advanced (`/graph-explorer` group)
**Purpose**: Lower-level tools for power users.

#### Sub-Tab 6a: Graph Explorer (`/graph-explorer`)

| Element | Description |
| :--- | :--- |
| **Graph Canvas** | Interactive Cytoscape-powered graph visualization. |
| **Search** | Filter by entity type, relationship type, and properties. Supports Cypher operators (`CONTAINS`, `STARTS WITH`, `=~` regex, `IN`, `IS NULL`). |
| **Generated Cypher** | View the raw Cypher query that was executed. |
| **Workflow Scope** | Filter the graph to show only nodes related to a specific workflow. |

#### Sub-Tab 6b: Multi-Modal Analyzer (`/multimodal`)

| Element | Description |
| :--- | :--- |
| **Upload Zone** | Drag-and-drop files (PDF, images, documents). |
| **Vision Model** | Select a model (e.g., `llava:latest`, `bakllava:latest`). |
| **Extraction Method** | Choose Vision LLM / OCR Only / Hybrid. |
| **Results** | Extracted structured data from the uploaded document. |

#### Sub-Tab 6c: API Docs (`/api-docs`)

| Element | Description |
| :--- | :--- |
| **Swagger UI** | Embedded interactive API documentation from the backend. |

---

### Tab 7: Settings (`/settings` group)
**Purpose**: Application configuration and administration.

#### Sub-Tab 7a: Preferences (`/settings`)
User-level display preferences (theme, language).

#### Sub-Tab 7b: Admin (`/settings/admin`)
Admin-only configuration panel with internal tabs:

| Admin Tab | Description |
| :--- | :--- |
| **LLM Providers** | Configure connections to Ollama, Azure OpenAI, or other LLM endpoints. Test connection. |
| **Embedding Models** | Select and configure the embedding model used for semantic search and mapping. |
| **Connection Settings** | Manage data source connections (Postgres, Neo4j, OpenSearch, PLM systems). Add/Edit/Delete/Test. Supports OAuth 2.0 for Azure API Gateway. See [OAuth Configuration Guide](./OAUTH_CONFIGURATION.md). |
| **System Settings** | Core runtime settings (CORS origins, rate limits, log levels). |
| **Feature Flags** | Toggle experimental features on/off. |

---

## Common Troubleshooting

| Problem | Solution |
| :--- | :--- |
| UI shows raw HTML instead of data | Backend is not running. Check `http://localhost:8011/health`. |
| 503 errors on optional features | Neo4j/OpenSearch/LLM not configured. Set them up in Admin tab. |
| "Unauthorized" on API calls | Enable auth is on. Check `GRAPH_TRACE_AUTH_REQUIRED` and supply JWT. |
| Migration Wizard stuck on "Discovering" | Check the ETL Orchestrator Agent terminal window for errors. |
| PLM connection fails with OAuth | Verify client credentials in Azure AD. See [OAuth Troubleshooting](./OAUTH_CONFIGURATION.md#troubleshooting). |
