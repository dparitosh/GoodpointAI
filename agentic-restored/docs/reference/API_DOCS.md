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
