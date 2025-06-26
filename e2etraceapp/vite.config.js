import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Proxy API requests to your Python FastAPI backend server
      '/api': 'http://localhost:8000', // Update to the port your FastAPI server runs on
    },
  },
})
