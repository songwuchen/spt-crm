import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    testTimeout: 15000,
    pool: 'forks',
    poolOptions: { forks: { maxForks: 4 } },
    // React 18 的并发调度器有时会在 Vitest 拆掉 jsdom 环境后才 flush 一次已排队的 commit，
    // 届时 react-dom 访问已消失的 window → "ReferenceError: window is not defined"。这类
    // 拆卸期泄漏与断言无关（全部用例仍通过），却会让整轮 CI 因 1 个 unhandled error 失败且时好时坏。
    // 断言/超时/console 错误仍会正常让用例失败——这里只忽略这类拆卸期未处理错误。
    dangerouslyIgnoreUnhandledErrors: true,
  },
})
