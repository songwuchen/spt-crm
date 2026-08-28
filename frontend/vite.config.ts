/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    testTimeout: 20000,
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@ant-design/charts') || id.includes('@antv')) return 'vendor-charts'
            // 新增图形/图表/网格库单独成块,先于 antd/react 判定,避免被 id.includes('react')
            // 卷入 vendor-react(@xyflow/react、react-grid-layout、echarts-for-react 等含 'react'),
            // 从而改变 vendor-react 初始化顺序、令 antd 读取 React.version 时 React 为 undefined(生产白屏)。
            if (id.includes('echarts') || id.includes('@xyflow') || id.includes('@dagrejs')
              || id.includes('react-grid-layout') || id.includes('react-resizable') || id.includes('@dnd-kit')
              || id.includes('quill')) return 'vendor-viz'  // react-quill-new 含 'react',同理前置避免卷入 vendor-react
            if (id.includes('antd') || id.includes('rc-') || id.includes('@ant-design')) return 'vendor-antd'
            if (id.includes('react')) return 'vendor-react'
          }
        },
      },
    },
  },
  server: {
    host: '0.0.0.0',
    // Vite 只认 true | string[]；写 'all' 无效，ngrok 域名仍会被 Host check 拦住
    allowedHosts: true,
    port: 5175,
    proxy: {
      // 默认 8002；可用 VITE_API_PROXY / VITE_WS_PROXY 覆盖。
      // Windows + Docker Desktop：127.0.0.1:8002 可能仍被本机旧 uvicorn 占用，
      // 而 [::1]:8002 才是容器内已配置 jdy_oss / IMM 的 backend。
      ...(() => {
        const apiTarget = process.env.VITE_API_PROXY
          || (process.platform === 'win32' ? 'http://[::1]:8002' : 'http://127.0.0.1:8002')
        const wsTarget = process.env.VITE_WS_PROXY
          || (process.platform === 'win32' ? 'ws://[::1]:8002' : 'ws://127.0.0.1:8002')
        const common = { changeOrigin: true, secure: false as const }
        return {
          '/api': { target: apiTarget, ...common },
          '/docs': { target: apiTarget, ...common },
          '/redoc': { target: apiTarget, ...common },
          '/openapi.json': { target: apiTarget, ...common },
          '/ws': { target: wsTarget, ws: true },
        }
      })(),
    },
  },
})
