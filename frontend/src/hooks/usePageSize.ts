import { useState, useCallback } from 'react'

const PREFIX = 'spt_pageSize_'
const DEFAULT_PAGE_SIZE = 20

export function usePageSize(key: string): [number, (size: number) => void] {
  const storageKey = `${PREFIX}${key}`

  const [pageSize, setPageSizeState] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(storageKey)
      if (stored) {
        const parsed = parseInt(stored, 10)
        if (!isNaN(parsed) && parsed > 0) return parsed
      }
    } catch {
      // ignore
    }
    return DEFAULT_PAGE_SIZE
  })

  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size)
    try {
      localStorage.setItem(storageKey, String(size))
    } catch {
      // ignore
    }
  }, [storageKey])

  return [pageSize, setPageSize]
}
