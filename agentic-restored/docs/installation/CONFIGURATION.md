# Configuration

GraphTrace supports **DB-seeded, UI-managed configuration**.

## Recommended: configure via the UI

- Admin Configuration Center: http://localhost:5173/#/admin

Typical setup:
- Connections: PostgreSQL / Neo4j / OpenSearch
- Feature flags / system settings (if enabled)

## Encryption key (required for encrypted DB config)

GraphTrace uses an encryption key for DB-backed encrypted configuration:

- Env var: `GRAPH_TRACE_CONFIG_ENCRYPTION_KEY`
- Local dev convenience: `python_backend/.graphtrace.encryption_key` (created by `bootstrap.ps1`)

If the key is missing, features that read encrypted config may fail or behave as unconfigured.

## Seeded configuration (what gets created automatically)

During bootstrap, GraphTrace runs `python -m scripts.init_db_schema` which:
- Ensures Postgres tables exist (schema)
- Seeds default encrypted config keys (best-effort) via `scripts.seed_db_config`

You can run these manually from `python_backend/` when needed:

```powershell
python -m scripts.init_db_schema
python -m scripts.seed_db_config
```

Optional (only if you want demo fixtures / default templates):
- `python -m scripts.seed_admin_configs`
- `python -m scripts.seed_pipeline_configs`
- `python -m scripts.seed_unstructured_workflows` (can seed OpenSearch indices + Neo4j schema)

## Backend env vars (common)

- Postgres:
  - `DATABASE_URL` (preferred) OR `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- Optional tuning:
  - `GRAPH_TRACE_OLLAMA_TIMEOUT_S` (fail fast when Ollama is unavailable)
  - `GRAPH_TRACE_NEO4J_QUERY_TIMEOUT_S` (fail fast for Neo4j cypher calls)
  - `GRAPH_TRACE_QUALITY_FRESHNESS_SLA_SECONDS` (freshness SLA threshold)

## Legacy .env (optional)

You may still use `python_backend/.env` for local development, but the recommended model is UI-managed DB config.

If you do use `.env`, keep secrets there (never commit it).
