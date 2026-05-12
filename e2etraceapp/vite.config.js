import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Default to the repo's standard backend dev port.
  // Override locally with e.g. `VITE_DEV_PROXY_TARGET=http://127.0.0.1:8011` when using a different port.
  // Note: keep the dev-server proxy target independent from `VITE_API_BASE_URL` to avoid accidental misroutes.
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || 'http://127.0.0.1:8011'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
        '@config': path.resolve(__dirname, './src/config'),
        '@components': path.resolve(__dirname, './src/components'),
        '@services': path.resolve(__dirname, './src/services'),
        '@pages': path.resolve(__dirname, './src/pages'),
      },
    },
    server: {
      proxy: {
        // Shared error handler — returns 503 when the backend is unreachable so
        // the browser sees "Service Unavailable" instead of a generic 500.
        // Proxy API requests to your Python FastAPI Neo4j backend server
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          configure: (proxy) => {
            proxy.on('error', (err, _req, res) => {
              console.warn('Backend proxy error (API):', err.code || err.message);
              if (res && !res.headersSent) {
                res.writeHead(503, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ detail: 'Backend unavailable', error: err.code }));
              }
            });
          },
        },
        // Proxy health check endpoint
        '/health': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          configure: (proxy) => {
            proxy.on('error', (err, _req, res) => {
              console.warn('Backend proxy error (health):', err.code || err.message);
              if (res && !res.headersSent) {
                res.writeHead(503, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ status: 'unhealthy', detail: 'Backend unavailable', error: err.code }));
              }
            });
          },
        },
        // Proxy Swagger UI and OpenAPI docs
        '/docs': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
        '/openapi.json': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
        // Proxy pipeline-config endpoints (backend prefix /config)
        '/config': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
        },
      },
    },
  }
})
