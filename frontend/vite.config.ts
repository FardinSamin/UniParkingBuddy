import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxy the browser's same-origin /api requests to the local FastAPI service.
// API_PROXY_TARGET is set on the computer hosting Vite (not in the browser).
const backendTarget = process.env.API_PROXY_TARGET || 'http://127.0.0.1:5000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})
