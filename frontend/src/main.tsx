import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'
import '@fontsource/inter/300.css'
import '@fontsource/inter/400.css'
import '@fontsource/inter/500.css'
import '@fontsource/inter/600.css'
import '@fontsource/inter/700.css'
import '@fontsource/inter/800.css'
import '@fontsource/inter/900.css'
import App from './App'
import { theme } from './config/theme'
import { currentZone } from './config/zone'
import { markChunkRecoverSuccess, recoverFromStaleChunks, isChunkLoadError } from './utils/chunkRecover'
import './index.css'

dayjs.locale('zh-cn')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={theme} renderEmpty={() => <div className="py-8 text-center text-slate-400">暂无数据</div>}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)

// App boot succeeded — allow a future deploy to auto-recover again.
markChunkRecoverSuccess()

// Catch late chunk failures (lazy routes) that bubble as unhandled rejections
window.addEventListener('unhandledrejection', (e) => {
  if (isChunkLoadError(e.reason) && recoverFromStaleChunks(e.reason)) {
    e.preventDefault()
  }
})

// Service Worker：仅移动端域名做离线缓存。
// PC 域名（wm.*）若启用 SW，在自签证书下会劫持 /api 请求并 cache-first 旧 JS，
// 表现为「钉钉登录成功 → 网络异常 → 退回登录页」。
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const zone = currentZone()
    if (zone === 'mobile') {
      navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' }).catch(() => {})
      return
    }
    // web / platform / IP：注销遗留 SW 并清缓存，避免旧版本卡住
    navigator.serviceWorker.getRegistrations().then((regs) => {
      regs.forEach((r) => { void r.unregister() })
    }).catch(() => {})
    if (window.caches) {
      caches.keys().then((keys) => {
        keys.forEach((k) => { void caches.delete(k) })
      }).catch(() => {})
    }
  })
}
