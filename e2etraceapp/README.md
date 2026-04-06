# GraphTrace Frontend (e2etraceapp)

React/Vite frontend for GraphTrace.

## Development

```powershell
# From repo root
cd e2etraceapp
npm install
npm run dev
```

Frontend runs at: http://localhost:5173

## Key Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Production build |
| `npm run lint` | Run ESLint |
| `npm test` | Run Vitest tests |

### Smoke tests (require backend)

Some tests under `e2etraceapp/tests/*smoke*.test.js` are **integration smoke tests** that expect a running backend.

- Start the backend on `http://127.0.0.1:8011` (default), then run the smoke suite with:
	- `GRAPHTRACE_SMOKE=true`
- If your backend is on a different URL/port, set:
	- `E2E_API_BASE_URL=http://127.0.0.1:8011`

## Configuration

The frontend connects to the backend at `http://localhost:8011` by default. This can be configured via environment variables with the `VITE_` prefix.
