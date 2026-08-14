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

// Service Worker：仅移动端域名注册（离线回落用 network-first，见 public/sw.js）。
// PC / IP：注销遗留 SW 并清缓存，避免旧版本卡住。
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    const zone = currentZone()
    if (zone === 'mobile') {
      navigator.serviceWorker.register('/sw.js', { updateViaCache: 'none' })
        .then((reg) => {
          // 每次打开主动检查新 SW，缩短发版后旧 worker 存活时间
          void reg.update()
        })
        .catch(() => {})
      return
    }
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
