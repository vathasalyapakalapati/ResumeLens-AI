import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The dev server proxies /api to FastAPI, so the browser sees one origin and
// the httpOnly auth cookies work without any CORS setup.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5180,
    strictPort: true,
    proxy: { '/api': 'http://localhost:8010' },
  },
})
