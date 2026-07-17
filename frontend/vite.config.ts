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
    port: 5175,
    proxy: {
      // 后端地址可用 VITE_API_PROXY 覆盖（如指向远端环境联调）
      '/api': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8002',
        changeOrigin: true,
        secure: false,
      },
      '/docs': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8002',
        changeOrigin: true,
        secure: false,
      },
      '/redoc': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8002',
        changeOrigin: true,
        secure: false,
      },
      '/openapi.json': {
        target: process.env.VITE_API_PROXY || 'http://localhost:8002',
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: process.env.VITE_WS_PROXY || 'ws://localhost:8002',
        ws: true,
      },
    },
  },
})
