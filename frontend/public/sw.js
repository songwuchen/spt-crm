/**
 * Service Worker for SPT-CRM mobile.
 *
 * 发版白屏根因（已踩过多次）：cache-first 命中旧 hash 资源，或旧 HTML/SW
 * 指向已删除 chunk。策略改为：
 * - HTML / 导航：永不拦截（浏览器直连，配合 nginx no-store）
 * - 静态资源：network-first，只有离线才回落缓存
 * - 激活时清空一切旧 Cache Storage
 * - 404/非 2xx 绝不入库
 *
 * 改行为时务必 bump CACHE_NAME。
 */

const CACHE_NAME = 'spt-crm-static-v4'

self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.map((name) => caches.delete(name))),
    ).then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return

  // API / WS / OpenAPI / health：绝不碰（鉴权头 + TLS）
  if (
    url.pathname.startsWith('/api/')
    || url.pathname.startsWith('/ws/')
    || url.pathname.startsWith('/openapi/')
    || url.pathname === '/health'
    || url.pathname === '/sw.js'
  ) {
    return
  }

  // 导航 / HTML：交给浏览器 + nginx no-store，SW 不得缓存
  const accept = req.headers.get('accept') || ''
  if (req.mode === 'navigate' || accept.includes('text/html')) {
    return
  }

  // 仅处理带扩展名的静态资源
  if (!url.pathname.match(/\.(js|css|png|jpg|jpeg|svg|woff2?|ttf|eot|ico|webp)$/)) {
    return
  }

  event.respondWith((async () => {
    try {
      const fresh = await fetch(req)
      if (fresh && fresh.ok) {
        const cache = await caches.open(CACHE_NAME)
        cache.put(req, fresh.clone()).catch(() => {})
      }
      return fresh
    } catch {
      const cached = await caches.match(req)
      if (cached) return cached
      throw new Error('offline and not cached: ' + url.pathname)
    }
  })())
})
