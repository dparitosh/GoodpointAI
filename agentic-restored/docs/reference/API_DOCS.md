# OpenAPI / API Docs

GraphTrace’s backend is a FastAPI service and publishes an OpenAPI schema plus interactive Swagger UI.

## Local URLs

Assuming the backend is running on `http://localhost:8011`:

### Standard FastAPI endpoints

- Swagger UI: http://localhost:8011/docs
- OpenAPI JSON: http://localhost:8011/openapi.json

### Compatibility endpoints (under `/api/*`)

Some clients/tools expect docs under `/api`:

- Swagger UI: http://localhost:8011/api/docs
- OpenAPI JSON: http://localhost:8011/api/openapi.json

## Auth notes

- If API key / auth is enabled in your environment, the docs endpoints are still allowlisted so you can open Swagger UI.
- Protected endpoints will still require authentication when you try to execute them from Swagger UI.

## Quick health + schema checks (PowerShell)

```powershell
Invoke-WebRequest http://localhost:8011/health -UseBasicParsing | Select-Object StatusCode
Invoke-WebRequest http://localhost:8011/openapi.json -UseBasicParsing | Select-Object StatusCode
```

## Notable API contracts

- Analytics Quality endpoints live under `/api/analytics/quality/*`.
- `POST /api/analytics/quality/scan` (generic scan) returns a typed payload that includes a `persisted` boolean indicating whether the scan results were successfully persisted to Postgres.
- Persisted scan reports returned from `GET /api/analytics/quality/reports` and `GET /api/analytics/quality/reports/{scan_id}` include a stable `source` label (derived from the persisted row’s `data_source`).

### MCP Migration Runs (human-in-the-loop)

These endpoints provide a lightweight run state machine and an approvals surface for “agentic” migration workflows:

- Run lifecycle + staging:
	- `POST /api/migrations/runs`
	- `GET /api/migrations/runs`
	- `GET /api/migrations/runs/{run_id}`
	- `POST /api/migrations/runs/{run_id}/transition`
	- `POST /api/migrations/runs/{run_id}/stage`
- Approvals:
	- `GET /api/migrations/runs/{run_id}/approvals`
	- `POST /api/migrations/runs/{run_id}/approvals`
	- `POST /api/migrations/runs/{run_id}/approvals/{approval_id}/approve`
	- `POST /api/migrations/runs/{run_id}/approvals/{approval_id}/reject`

If approvals are enforced (via backend configuration), callers must pass an approval token using the `X-MCP-Approval-Token` header.

### GraphQL “tools” surface

This repo also exposes helper endpoints under `/api/graphql/tools/*` (not a full GraphQL server) intended for orchestration:

- `GET /api/graphql/tools/connectors` — safe connector listing (no secrets)
- `GET /api/graphql/tools/connectors/default/{connection_type}` — masked default connector
- `POST /api/graphql/tools/opensearch/search` — agent-friendly OpenSearch search wrapper
- `POST /api/graphql/tools/soda/scan/{table_name}` — delegates to the quality Soda scan endpoint
