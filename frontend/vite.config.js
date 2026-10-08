import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/search': 'http://127.0.0.1:8001',
      '/upload': 'http://127.0.0.1:8001',
      '/analyze-discovered': 'http://127.0.0.1:8001',
      '/analyze': 'http://127.0.0.1:8001',
      '/progress': 'http://127.0.0.1:8001',
      '/results': 'http://127.0.0.1:8001',
      '/ask': 'http://127.0.0.1:8001',
      '/papers': 'http://127.0.0.1:8001',
      '/health': 'http://127.0.0.1:8001',
    },
  },
})
