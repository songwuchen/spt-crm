/**
 * Service Worker for SPT-CRM mobile offline support.
 * Caches static assets and API responses for offline access.
 */

const CACHE_NAME = 'spt-crm-v1'
const API_CACHE = 'spt-crm-api-v1'

// Static assets to precache
const PRECACHE_URLS = [
  '/',
  '/index.html',
]

// API paths to cache with network-first strategy
const CACHEABLE_API_PATHS = [
  '/api/v1/customers',
  '/api/v1/service_tickets',
  '/api/v1/notifications',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name !== CACHE_NAME && name !== API_CACHE)
          .map((name) => caches.delete(name))
      )
    ).then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url)

  // Only handle GET requests
  if (event.request.method !== 'GET') return

  // API requests: network-first, fallback to cache
  if (CACHEABLE_API_PATHS.some((path) => url.pathname.startsWith(path))) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const cloned = response.clone()
            caches.open(API_CACHE).then((cache) => cache.put(event.request, cloned))
          }
          return response
        })
        .catch(() => caches.match(event.request))
    )
    return
  }

  // Static assets: cache-first
  if (url.pathname.match(/\.(js|css|png|jpg|svg|woff2?)$/)) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached
        return fetch(event.request).then((response) => {
          if (response.ok) {
            const cloned = response.clone()
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned))
          }
          return response
        })
      })
    )
    return
  }
})
