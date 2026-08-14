/**
 * Recover from stale deploy caches:
 * old index/SW referencing deleted hashed chunks →
 * "Failed to fetch dynamically imported module" / Unexpected Application Error.
 *
 * Safe to call multiple times; only one reload within 15s.
 */
const RECOVER_AT_KEY = 'spt_chunk_recover_at'

export function isChunkLoadError(err: unknown): boolean {
  const msg = String(
    (err as { message?: string })?.message
    || err
    || '',
  )
  return (
    /Failed to fetch dynamically imported module/i.test(msg)
    || /error loading dynamically imported module/i.test(msg)
    || /Loading chunk [\d]+ failed/i.test(msg)
    || /ChunkLoadError/i.test(msg)
    || /Loading CSS chunk/i.test(msg)
  )
}

export async function clearClientCaches(): Promise<void> {
  try {
    if ('serviceWorker' in navigator) {
      const regs = await navigator.serviceWorker.getRegistrations()
      await Promise.all(regs.map((r) => r.unregister()))
    }
  } catch { /* ignore */ }
  try {
    if (window.caches) {
      const keys = await caches.keys()
      await Promise.all(keys.map((k) => caches.delete(k)))
    }
  } catch { /* ignore */ }
}

/** @returns true if a recovery reload was scheduled */
export function recoverFromStaleChunks(err?: unknown): boolean {
  if (err !== undefined && !isChunkLoadError(err)) return false
  const last = Number(sessionStorage.getItem(RECOVER_AT_KEY) || 0)
  if (Date.now() - last < 15_000) return false
  sessionStorage.setItem(RECOVER_AT_KEY, String(Date.now()))
  void clearClientCaches().finally(() => {
    const u = new URL(window.location.href)
    u.searchParams.set('_nocache', String(Date.now()))
    window.location.replace(u.toString())
  })
  return true
}

/** Call after app successfully boots so a later deploy can recover again. */
export function markChunkRecoverSuccess(): void {
  try {
    const at = Number(sessionStorage.getItem(RECOVER_AT_KEY) || 0)
    // Keep the flag for a short window to avoid loops; clear after stable load.
    if (at && Date.now() - at > 5_000) {
      sessionStorage.removeItem(RECOVER_AT_KEY)
    }
    // Strip one-time cache-buster from the address bar.
    if (window.location.search.includes('_nocache=')) {
      const u = new URL(window.location.href)
      u.searchParams.delete('_nocache')
      window.history.replaceState(null, '', u.pathname + u.search + u.hash)
    }
  } catch { /* ignore */ }
}
