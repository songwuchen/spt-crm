/**
 * Offline cache layer using IndexedDB for mobile pages.
 * Caches API responses so they can be used when offline.
 */

const DB_NAME = 'spt_crm_offline'
const DB_VERSION = 1
const STORE_NAME = 'api_cache'

interface CacheEntry {
  key: string
  data: unknown
  timestamp: number
  ttl: number // in ms
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'key' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

export async function getCached<T>(key: string): Promise<T | null> {
  try {
    const db = await openDB()
    return new Promise((resolve) => {
      const tx = db.transaction(STORE_NAME, 'readonly')
      const store = tx.objectStore(STORE_NAME)
      const req = store.get(key)
      req.onsuccess = () => {
        const entry = req.result as CacheEntry | undefined
        if (!entry) { resolve(null); return }
        if (Date.now() - entry.timestamp > entry.ttl) {
          resolve(null); return
        }
        resolve(entry.data as T)
      }
      req.onerror = () => resolve(null)
    })
  } catch {
    return null
  }
}

export async function setCache(key: string, data: unknown, ttlMs = 30 * 60 * 1000): Promise<void> {
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const entry: CacheEntry = { key, data, timestamp: Date.now(), ttl: ttlMs }
    store.put(entry)
  } catch {
    // silently fail
  }
}

export async function clearCache(): Promise<void> {
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).clear()
  } catch {
    // silently fail
  }
}

export async function removeCacheByPrefix(prefix: string): Promise<void> {
  try {
    const db = await openDB()
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const req = store.getAllKeys()
    req.onsuccess = () => {
      for (const key of req.result) {
        if (String(key).startsWith(prefix)) {
          store.delete(key)
        }
      }
    }
  } catch {
    // silently fail
  }
}
