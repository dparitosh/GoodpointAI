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
        // Proxy API requests to your Python FastAPI Neo4j backend server
        '/api': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
          ws: true,
          configure: (proxy) => {
            proxy.on('error', (err) => {
              console.log('proxy error', err);
            });
            proxy.on('proxyReq', (_proxyReq, req) => {
              console.log('Sending Request to the Target:', req.method, req.url);
            });
            proxy.on('proxyRes', (proxyRes, req) => {
              console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
            });
          },
        },
        // Proxy health check endpoint
        '/health': {
          target: proxyTarget,
          changeOrigin: true,
          secure: false,
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
      },
    },
  }
})
