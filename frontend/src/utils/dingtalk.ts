// DingTalk container detection + JSAPI 免登 (requestAuthCode).
//
// When the CRM is opened INSIDE the DingTalk client (mobile or PC), the JSAPI
// `requestAuthCode` returns a short-lived auth code silently (no scan / no
// password). The backend exchanges it for a CRM token. requestAuthCode does NOT
// require dd.config signing, so this stays lightweight.

const DINGTALK_SDK_URL = 'https://g.alicdn.com/dingding/dingtalk-jsapi/3.0.25/dingtalk.open.js'

interface DingTalkRuntime {
  ready: (cb: () => void) => void
  error: (cb: (err: unknown) => void) => void
  runtime: {
    permission: {
      requestAuthCode: (opts: {
        corpId: string
        onSuccess: (info: { code: string }) => void
        onFail: (err: unknown) => void
      }) => void
    }
  }
}

declare global {
  interface Window { dd?: DingTalkRuntime }
}

/** 是否运行在钉钉客户端容器内（UA 判定）。 */
export function isDingTalkContainer(): boolean {
  if (typeof navigator === 'undefined') return false
  return /dingtalk/i.test(navigator.userAgent)
}

let sdkPromise: Promise<DingTalkRuntime> | null = null

function loadDingTalkSdk(): Promise<DingTalkRuntime> {
  if (window.dd) return Promise.resolve(window.dd)
  if (sdkPromise) return sdkPromise
  sdkPromise = new Promise((resolve, reject) => {
    const s = document.createElement('script')
    s.src = DINGTALK_SDK_URL
    s.async = true
    s.onload = () => (window.dd ? resolve(window.dd) : reject(new Error('DingTalk SDK unavailable')))
    s.onerror = () => reject(new Error('failed to load DingTalk SDK'))
    document.head.appendChild(s)
  })
  return sdkPromise
}

/** 在钉钉容器内静默获取免登 authCode。 */
export async function getDingTalkAuthCode(corpId: string): Promise<string> {
  const dd = await loadDingTalkSdk()
  return new Promise<string>((resolve, reject) => {
    let settled = false
    const done = (fn: () => void) => { if (!settled) { settled = true; fn() } }
    dd.error((err) => done(() => reject(err)))
    dd.ready(() => {
      dd.runtime.permission.requestAuthCode({
        corpId,
        onSuccess: (info) => done(() => resolve(info.code)),
        onFail: (err) => done(() => reject(err)),
      })
    })
  })
}
