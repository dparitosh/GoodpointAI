# GraphTrace Business User Guide

This guide is written for **business users** and **superusers/admins** who use the GraphTrace UI to configure data integrations, define mappings, and review reports.

## Access the App

- Frontend UI: http://localhost:5173
- Backend API: http://localhost:8011
- API Docs (Swagger): http://localhost:8011/docs

## Roles (Practical)

- **Business user**: views dashboards/reports, exports data, uses spreadsheet tooling.
- **Superuser/admin**: configures integrations and defines mapping + transformation rules.

## Configure Integrations (Superuser)

1. Open `http://localhost:5173/#/data-config`.
2. Configure Neo4j / OpenSearch / runtime settings as needed.
3. Verify service status indicators in the UI.

Notes:
- Persisted reports require Postgres to be reachable (configured via `DATABASE_URL` or `POSTGRES_*`). If unavailable, report endpoints return **HTTP 503**.

## Define Source → Target Mappings (Superuser)

1. Open `http://localhost:5173/#/data-mapping`.
2. Click **New Mapping**.
3. Fill:
   - **Source System ID** (example: `neo4j`)
   - **Target System ID** (example: `neo4j`)
4. Under **Field Mappings**, click **Add Field Mapping** and specify:
   - Source field
   - Transformation (optional)
   - Target field
5. Click **Save Draft** to persist changes.
6. Click **Validate** (from the mappings list) to run rule validation.
7. Click **Deploy Mapping** to mark the rule **active**.

Important:
- Mapping rules/templates are currently stored as local runtime JSON files (dev artifact) in `python_backend/`.
- The **Execute** action is intentionally fail-closed and returns **HTTP 503** unless an execution engine + connectors are configured.

## Reporting & Analytics (Business user)

1. Open `http://localhost:5173/#/reporting`.
2. Select a report to view details.
3. Use **Download JSON** / **Download CSV** where available.
4. Click **Open Spreadsheet** to inspect report payloads in a tabular way.

## Spreadsheet (Business user)

Open `http://localhost:5173/#/spreadsheet`.

Common actions:
- **Import** `.xlsx`, `.csv`, `.json`, `.xml`
- **Export** to Excel/CSV/JSON/XML
- Select a data region and generate charts

Notes:
- The backend `/api/convert` endpoint currently implements **JSON → CSV** conversion; other conversions may be handled locally in the UI or return “not yet implemented”.

## Data Export (Business user)

1. Open the **Export** page in the navigation.
2. Choose datasets and format (Excel/CSV/JSON).
3. Start export and download the generated file(s).

## Troubleshooting

- If a page shows missing data, check the backend is running and open `http://localhost:8011/docs`.
- If reports don’t load, confirm Postgres is running and reachable by the backend.
- If ports are busy, free ports 8011 and 5173 before starting services.
