import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': new URL('./src', import.meta.url).pathname,
    },
  },
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
