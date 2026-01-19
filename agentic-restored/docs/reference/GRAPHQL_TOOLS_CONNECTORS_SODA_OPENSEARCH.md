# GraphQL Tools: Connectors + Soda + OpenSearch

This repo includes a "GraphQL toolkit" under `/api/graphql/*`. It is **not** a full GraphQL server; it's a practical, GraphQL-like API surface.

To make agent orchestration easier, the backend also exposes **tool endpoints** under:

- `/api/graphql/tools/*`

These endpoints wrap existing backend capabilities (Admin Connection Settings, OpenSearch, Soda, and OpenSearch AD gatekeeper) behind a single, consistent surface.

## Endpoints

### List connectors (safe view)

- `GET /api/graphql/tools/connectors`
- Optional query param: `connection_type`

Returns a list of connectors without secrets.

### Get default connector (masked)

- `GET /api/graphql/tools/connectors/default/{connection_type}`

Returns the resolved connector config for that type as used by backend services.
Secrets are masked (e.g., `password="***"`).

### OpenSearch search tool

- `POST /api/graphql/tools/opensearch/search`

Body:
- `index` (string)
- `query` (object): OpenSearch Query DSL
- `connection_id` (optional): a specific connector id (must be an `opensearch` connector)

### Soda scan tool

- `POST /api/graphql/tools/soda/scan/{table_name}`

Body:
- `checks_yaml` (string)
- `data_source_name` (string, default `postgres`)

This delegates to the standard quality endpoint so results are persisted as a standard DQ report.

### OpenSearch AD gate tool

- `POST /api/graphql/tools/opensearch-ad/gate/{result_index}`

Body: optional JSON matching the existing `OpenSearchAnomalyGateRequest`.

This delegates to the standard gatekeeper implementation so results are persisted as a standard DQ report.

## Why this exists (agent orchestration)

Agents typically need:
- Discover which connectors exist (OpenSearch, Soda runner, etc.).
- Execute queries/scans consistently.
- Consume results using the same report contracts the UI already understands.

`/api/graphql/tools/*` provides that glue layer.

## Notes

- These endpoints are **safe-by-default**: they do not return secrets.
- OpenSearch operations fail-closed (503) when OpenSearch is not configured/reachable.
- Soda execution may use an external runner depending on your environment and Admin Connection Settings.
