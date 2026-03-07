import { useSearchParams } from 'react-router-dom'
import { useCallback } from 'react'

/**
 * Hook to sync filter state with URL search params.
 * Returns [value, setter] similar to useState but persisted in URL.
 */
export function useUrlParam(key: string, defaultValue = ''): [string, (v: string) => void] {
  const [params, setParams] = useSearchParams()
  const value = params.get(key) || defaultValue

  const setValue = useCallback((v: string) => {
    setParams((prev) => {
      const next = new URLSearchParams(prev)
      if (v && v !== defaultValue) {
        next.set(key, v)
      } else {
        next.delete(key)
      }
      return next
    }, { replace: true })
  }, [key, defaultValue, setParams])

  return [value, setValue]
}

export function useUrlNumber(key: string, defaultValue = 1): [number, (v: number) => void] {
  const [str, setStr] = useUrlParam(key, String(defaultValue))
  const value = parseInt(str, 10) || defaultValue
  const setValue = useCallback((v: number) => setStr(String(v)), [setStr])
  return [value, setValue]
}
