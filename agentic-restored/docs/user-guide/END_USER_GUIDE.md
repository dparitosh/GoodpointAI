# End User Guide (Configuration → Workflow Execution)

This guide is for business users and admins using the GraphTrace UI.

For a broader overview, see: [BUSINESS_USER_GUIDE.md](BUSINESS_USER_GUIDE.md)

## 0) Open the app

- Frontend: http://localhost:5173

## 1) Configure the system (Admin)

1. Open the Admin Configuration Center:
   - http://localhost:5173/#/admin
2. Configure connections as needed (depending on what you use):
   - PostgreSQL (required for persisted reports)
   - Neo4j (lineage/graph queries)
   - OpenSearch (search/vector features)
3. Use any **Test Connection** / health indicators available in the UI.

## 2) Run a migration workflow (PLM Migration Wizard)

1. Open Migration:
   - http://localhost:5173/#/migration
2. Follow the 5-step wizard:
   - **Connect**: choose source + target systems
   - **Discovery**: run discovery insights
   - **Map**: create field mappings
   - **Validate**: run quality checks/transform preview
   - **Execute**: run the migration and monitor progress

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

- Backend health: http://localhost:8011/health
- API docs: http://localhost:8011/docs
- If reports return HTTP 503, verify Postgres connectivity.
- If ports are in use, free 8011 and 5173 then restart.
