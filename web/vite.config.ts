import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// API chạy riêng: uvicorn app.api:app --port 8000. Dev server chuyển /api sang đó (đổi bằng VITE_API_PROXY).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: process.env.VITE_API_PROXY ?? 'http://127.0.0.1:8000', changeOrigin: true } },
  },
  test: { environment: 'node' },
})
