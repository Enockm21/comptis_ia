import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    headers: {
      'Cache-Control': 'no-store',
    },
    proxy: {
      '/api': 'http://localhost:8000',
      '/admin': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/reconciliation': 'http://localhost:8000',
      '/tenants': 'http://localhost:8000',
      '/ecritures': 'http://localhost:8000',
      '/plan-comptable': 'http://localhost:8000',
      '/api/categorization': 'http://localhost:8000',
      '/categorization': 'http://localhost:8000',
      '/tva': 'http://localhost:8000',
    },
  },
})
