import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 生产部署到 www.wuyullm.com/bizbuddy/ 子路径下，与 wuyullm 主站共享 cookie
// 从而复用 buildingai 的 __user_token__ session。
// 开发环境（vite dev）仍走根路径，通过 VITE_BASE 覆盖。
const BASE = process.env.VITE_BASE || '/bizbuddy/'

export default defineConfig({
  base: BASE,
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
