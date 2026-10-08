import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/search': 'http://localhost:8001',
      '/upload': 'http://localhost:8001',
      '/analyze-discovered': 'http://localhost:8001',
      '/analyze': 'http://localhost:8001',
      '/progress': 'http://localhost:8001',
      '/results': 'http://localhost:8001',
      '/ask': 'http://localhost:8001',
      '/papers': 'http://localhost:8001',
      '/health': 'http://localhost:8001',
    },
  },
})
