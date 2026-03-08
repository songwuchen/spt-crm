import { useState, useEffect, useCallback } from 'react'
import { getCached, setCache } from '@/utils/offlineCache'

interface UseOfflineCacheOptions<T> {
  /** Unique cache key for this data */
  cacheKey: string
  /** Function that fetches fresh data from API */
  fetchFn: () => Promise<T>
  /** TTL in milliseconds, default 30 min */
  ttl?: number
  /** Whether to fetch immediately */
  immediate?: boolean
}

/**
 * Hook that provides offline-first data fetching:
 * 1. Returns cached data immediately if available
 * 2. Fetches fresh data from API in background
 * 3. Caches new data for offline access
 */
export function useOfflineCache<T>({ cacheKey, fetchFn, ttl = 30 * 60 * 1000, immediate = true }: UseOfflineCacheOptions<T>) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [isOffline, setIsOffline] = useState(!navigator.onLine)
  const [fromCache, setFromCache] = useState(false)

  useEffect(() => {
    const goOnline = () => setIsOffline(false)
    const goOffline = () => setIsOffline(true)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    return () => {
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
    }
  }, [])

  const refresh = useCallback(async () => {
    setLoading(true)
    // Try cache first
    const cached = await getCached<T>(cacheKey)
    if (cached !== null) {
      setData(cached)
      setFromCache(true)
      setLoading(false)
    }

    // Fetch fresh data
    if (navigator.onLine) {
      try {
        const fresh = await fetchFn()
        setData(fresh)
        setFromCache(false)
        await setCache(cacheKey, fresh, ttl)
      } catch {
        // If fetch fails and no cached data, keep loading state
        if (cached === null) {
          setLoading(false)
        }
      } finally {
        setLoading(false)
      }
    } else {
      setLoading(false)
    }
  }, [cacheKey, fetchFn, ttl])

  useEffect(() => {
    if (immediate) refresh()
  }, [immediate, refresh])

  return { data, loading, isOffline, fromCache, refresh }
}
