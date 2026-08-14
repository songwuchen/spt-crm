/**
 * Service Worker for SPT-CRM mobile offline support.
 *
 * IMPORTANT:
 * - Do NOT intercept /api/* (auth headers + self-signed HTTPS break SW fetch).
 * - Do NOT cache HTML (otherwise deploys stay invisible until hard-reset).
 * - Hashed static assets may be cached; bump CACHE_NAME on behavior changes.
 */

const CACHE_NAME = 'spt-crm-static-v3'

self.addEventListener('install', (event) => {
  // Activate updated SW immediately so clients leave a broken v1/v2 behind.
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          // Drop every previous cache (including old API caches).
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name)),
      ),
    ).then(() => self.clients.claim()),
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Never touch API / WS / OpenAPI — browser handles TLS trust & Authorization.
  if (
    url.pathname.startsWith('/api/')
    || url.pathname.startsWith('/ws/')
    || url.pathname.startsWith('/openapi/')
    || url.pathname === '/health'
  ) {
    return
  }

  // Only cache immutable hashed static assets; HTML always goes to network.
  if (event.request.method !== 'GET') return
  if (!url.pathname.match(/\.(js|css|png|jpg|jpeg|svg|woff2?|ttf|eot|ico)$/)) return

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(event.request)
      if (cached) return cached
      const response = await fetch(event.request)
      if (response.ok) {
        cache.put(event.request, response.clone())
      }
      return response
    }).catch(() => fetch(event.request)),
  )
})
