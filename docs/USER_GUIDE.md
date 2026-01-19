# End User Guide

This guide is for business users and admins using the GraphTrace UI.

## Access

- UI: http://localhost:5173

If the UI shows errors, confirm the backend is running:

- API: http://localhost:8011/health
- OpenAPI: http://localhost:8011/docs

## 1) Admin setup (first time)

Open Admin:

- http://localhost:5173/#/admin

Configure what you need (depending on your deployment):

- **PostgreSQL** (required for persisted reports and workflow persistence)
- **Neo4j** (optional; lineage graph)
- **OpenSearch** (optional; indexing/retrieval)

Recommended quick check (after saving settings):

- Refresh the page and ensure the UI shows the connection as healthy (if the UI provides health checks).
- If a feature fails closed (returns 503), confirm its dependency is configured and reachable.

### Local folder source (Windows)

If you use a local folder as a datasource, you must allowlist it:

- Set `GRAPH_TRACE_ALLOWED_LOCAL_ROOTS` to one or more roots separated by `;`.

This is a deliberate safety control.

## 2) Run a migration workflow

Open Migration:

- http://localhost:5173/#/migration

Follow the wizard:

1. **Connect**: choose source and target systems
2. **Discovery**: run discovery and review findings
3. **Map**: define mappings
4. **Validate**: run validation / quality checks
5. **Execute**: run the migration and monitor status

What to expect:

- Runs may materialize lineage and/or publish/index artifacts depending on your selected target and enabled integrations.
- If approvals are enabled, execution may pause until an approval token is provided.

### Approvals (if enabled)

Some actions may require approval before they run.

- Create/approve requests in the UI and provide the approval token when prompted.

## 3) Workflow Manager

Open:

- http://localhost:5173/#/workflow-manager

Use this to:

- List workflows and recent runs
- Open run details and track outcomes

Tip:

- If a run is stuck in a waiting state, check whether an approval is required.

## 4) Analytics Hub

Open:

- http://localhost:5173/#/analytics

Typical sections:

- **Query Builder**: run read-only analytics queries
- **Natural Language**: generate queries from a question
- **Quality Reports**: view scan results and export JSON/CSV

Exports:

- Use the Export actions to download JSON/CSV and share results externally.

## 5) Reporting

Open:

- http://localhost:5173/#/reporting

- Browse persisted reports
- Download/export when available

## Troubleshooting

- **503 from report endpoints**: Postgres not reachable/configured.
- **UI loads but data missing**: check backend logs for integration configuration errors.
