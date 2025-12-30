# Apache (optional)

This folder contains a sample Apache HTTP Server (httpd) configuration for GraphTrace.

## What it does
- Serves the built frontend from `e2etraceapp/dist`
- Proxies `/api/*` to the backend (FastAPI/Uvicorn)

## Steps (Windows example)
1. Build the frontend:
   - `cd agentic-restored/e2etraceapp`
   - `npm run build`
2. Start the backend (production-style, no reload):
   - `cd agentic-restored/python_backend`
   - `venv\Scripts\activate`
   - `python -m uvicorn main:app --host 127.0.0.1 --port 8011`
3. Copy/edit `apache/graphtrace-httpd.conf`:
   - Update `DocumentRoot` + `<Directory>` paths to point to your actual `dist` folder
   - Ensure Apache has `mod_proxy`, `mod_proxy_http`, `mod_headers`, `mod_rewrite` enabled
4. Validate config:
   - `httpd -t -f apache\graphtrace-httpd.conf`
5. Start Apache and browse:
   - `http://localhost:8080`

## Diagnostics
- `diagnostics/windows/diagnose-apache.ps1`
