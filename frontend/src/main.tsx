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
import 'material-symbols/outlined.css'
import App from './App'
import { theme } from './config/theme'
import './index.css'

dayjs.locale('zh-cn')

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={theme} renderEmpty={() => <div className="py-8 text-center text-slate-400">暂无数据</div>}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)

// Register Service Worker for offline support (mobile)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // SW registration failed, offline mode not available
    })
  })
}
