import { useState, useRef, useCallback, useEffect } from 'react'

type Option = { label: string; value: string }
type FetchFn = (keyword?: string, signal?: AbortSignal) => Promise<Option[]>

export function useRemoteSelect(
  fetchFn: FetchFn,
  opts?: { immediate?: boolean },
) {
  const [options, setOptions] = useState<Option[]>([])
  const [loading, setLoading] = useState(false)
  const loadedRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const abortRef = useRef<AbortController>()
  const fetchRef = useRef(fetchFn)
  fetchRef.current = fetchFn

  const load = useCallback(async (keyword?: string) => {
    // Cancel previous in-flight request to prevent stale data
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    try {
      const list = await fetchRef.current(keyword, controller.signal)
      if (!controller.signal.aborted) {
        setOptions(list)
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      // Silently degrade — keep previous options visible
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false)
      }
    }
  }, [])

  const onSearch = useCallback(
    (keyword: string) => {
      if (timerRef.current) clearTimeout(timerRef.current)
      timerRef.current = setTimeout(() => {
        load(keyword || undefined)
      }, 300)
    },
    [load],
  )

  const onDropdownVisibleChange = useCallback(
    (open: boolean) => {
      if (open && !loadedRef.current) {
        loadedRef.current = true
        load()
      }
    },
    [load],
  )

  useEffect(() => {
    if (opts?.immediate) {
      loadedRef.current = true
      load()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (abortRef.current) abortRef.current.abort()
    }
  }, [])

  const setInitialOption = useCallback((opt: Option) => {
    setOptions((prev) => {
      if (prev.some((o) => o.value === opt.value)) return prev
      return [opt, ...prev]
    })
  }, [])

  return { options, loading, onSearch, onDropdownVisibleChange, setInitialOption }
}
