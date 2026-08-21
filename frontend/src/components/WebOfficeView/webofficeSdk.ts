/** 阿里云 WebOffice JS-SDK（仅 doc/ppt 等 IMM 预览时动态加载）。 */

const SDK_URL = 'https://g.alicdn.com/IMM/office-js/1.1.19/aliyun-web-office-sdk.min.js'

export interface WebOfficeInstance {
  setToken: (v: { token: string; timeout?: number }) => void
  destroy?: () => void
}

export interface WebOfficeSdk {
  config: (opts: {
    mount: HTMLElement
    url: string
    refreshToken?: () => Promise<{ token: string; timeout: number }> | { token: string; timeout: number }
  }) => WebOfficeInstance
}

declare global {
  interface Window { aliyun?: WebOfficeSdk }
}

let pending: Promise<WebOfficeSdk> | null = null

export function loadWebOfficeSdk(): Promise<WebOfficeSdk> {
  if (window.aliyun?.config) return Promise.resolve(window.aliyun)
  if (!pending) {
    pending = new Promise<WebOfficeSdk>((resolve, reject) => {
      const s = document.createElement('script')
      s.src = SDK_URL
      s.async = true
      s.onload = () => {
        if (window.aliyun?.config) resolve(window.aliyun)
        else reject(new Error('在线预览组件加载异常'))
      }
      s.onerror = () => { pending = null; reject(new Error('在线预览组件加载失败，请检查网络')) }
      document.head.appendChild(s)
    })
  }
  return pending
}
