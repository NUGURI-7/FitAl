import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true, // 手机同一局域网可访问
    proxy: {
      // 开发期把后端请求转给本地 FastAPI,前端代码里只写相对路径
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true, // 语音通道 /api/voice 走 WebSocket,需转发 upgrade
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
    },
  },
})
