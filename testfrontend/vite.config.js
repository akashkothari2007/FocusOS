import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /api to backend — avoids CORS in dev. BASE_URL lives here, not in api.js.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'https://focusos-production.up.railway.app',
      '/auth': 'https://focusos-production.up.railway.app',
    },
  },
})

