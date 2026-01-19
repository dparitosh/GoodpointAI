# End User Guide (Configuration → Workflow Execution)

This guide is for business users and admins using the GraphTrace UI.

For a broader overview, see: [BUSINESS_USER_GUIDE.md](BUSINESS_USER_GUIDE.md)

## 0) Open the app

- Frontend: http://localhost:5173

> Note: Backend ports can vary by launch script/profile. In this repo you may see FastAPI on **8011** (default) or **8008** (OpenSearch profile). If something doesn’t load, check the backend terminal output for the bound host/port.

## 1) Configure the system (Admin)

1. Open the Admin Configuration Center:
   - http://localhost:5173/#/admin
2. Configure connections as needed (depending on what you use):
   - PostgreSQL (required for persisted reports)
   - Neo4j (canonical lineage / traceability graph)
   - OpenSearch (publish/retrieval index for searchable artifacts)
3. Use any **Test Connection** / health indicators available in the UI.

### Local folder data source (Windows)

If you want to use a **local folder** as a source:

- Add a `local_folder` connection in Admin.
- Ensure the backend allowlists the folder root(s) via the environment variable:
  - `GRAPH_TRACE_ALLOWED_LOCAL_ROOTS=C:\data;D:\exports` (semicolon-separated)

This is a deliberate safety control: the backend will reject sampling outside the allowlist.

## 2) Run a migration workflow (PLM Migration Wizard)

1. Open Migration:
   - http://localhost:5173/#/migration
2. Follow the 5-step wizard (note: Execute may perform an additional OpenSearch publish step when applicable):
   - **Connect**: choose source + target systems
   - **Discovery**: run discovery insights
   - **Map**: create field mappings
   - **Validate**: run quality checks/transform preview
   - **Execute**: run the migration and monitor progress

### What “Execute” does (important)

Execution is **two-phase** when your target is OpenSearch:

1. **Materialize lineage (Neo4j)** — always runs. This writes the canonical traceability graph.
2. **Publish/index (OpenSearch)** — runs only when the selected target is OpenSearch. This indexes published documents for search, and records publish events back into Neo4j.

If approvals are enabled, these can be **separately gated** actions (`materialize` vs `publish`).

## 3) Analytics Hub

Open:
- http://localhost:5173/#/analytics

### Query Builder

- Choose a datasource (PostgreSQL / Neo4j / OpenSearch / GraphQL)
- Run read-only analytics queries (SQL is SELECT-only)

### Natural Language

- Type a question and generate a query
- Use the generated query in Query Builder if needed

### Quality Reports

- View **Data Quality Metrics** and **Profiling / Data Discovery**
- Click a scan to load detailed results

### Saved Queries

- View saved queries (GraphQL catalogue)

## 4) Reporting

Open:
- http://localhost:5173/#/reporting

- Browse report outputs
- Download JSON/CSV when available

## 5) Troubleshooting (quick)

- Backend health: http://localhost:8011/health (or http://localhost:8008/health)
- API docs: http://localhost:8011/docs (or http://localhost:8008/docs)
- If reports return HTTP 503, verify Postgres connectivity.
- If ports are in use, free 8011 and 5173 then restart.

### Common migration-run issues

- **“Waiting for approval”**: create an approval request for the required action (shown in the UI), approve it, then select the token.
- **OpenSearch publish fails**: verify OpenSearch connection settings and that the backend is running with OpenSearch enabled/configured.
