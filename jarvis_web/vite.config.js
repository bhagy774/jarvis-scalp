import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/ws': { target: 'ws://127.0.0.1:7788', ws: true },
      '/chat': { target: 'http://127.0.0.1:7788' },
      '/api': { target: 'http://127.0.0.1:7788' },
    },
  },
})
