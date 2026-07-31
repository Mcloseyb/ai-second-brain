/**
 * Vite 构建配置 — React + TypeScript
 * ---------------------------------
 * 开发: npm run dev   → 热更新 http://127.0.0.1:5173
 * 生产: npm run build → 打包到 dist/，Qt 用本地 HTTP 服务加载
 *
 * base 必须为 './'（相对路径）— Qt 通过 http://127.0.0.1:随机端口 加载 dist
 */
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

export default defineConfig({
  plugins: [react()],
  base: './',

  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },

  server: {
    port: 5173,
    host: '127.0.0.1',
    strictPort: true,
  },

  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
})
