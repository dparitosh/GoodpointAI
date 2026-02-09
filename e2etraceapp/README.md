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

## Configuration

The frontend connects to the backend at `http://localhost:8011` by default. This can be configured via environment variables with the `VITE_` prefix.
