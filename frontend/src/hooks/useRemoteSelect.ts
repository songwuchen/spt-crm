import { useState, useRef, useCallback, useEffect } from 'react'

type Option = { label: string; value: string }
type FetchFn = (keyword?: string) => Promise<Option[]>

export function useRemoteSelect(
  fetchFn: FetchFn,
  opts?: { immediate?: boolean },
) {
  const [options, setOptions] = useState<Option[]>([])
  const [loading, setLoading] = useState(false)
  const loadedRef = useRef(false)
  const timerRef = useRef<ReturnType<typeof setTimeout>>()
  const fetchRef = useRef(fetchFn)
  fetchRef.current = fetchFn

  const load = useCallback(async (keyword?: string) => {
    setLoading(true)
    try {
      const list = await fetchRef.current(keyword)
      setOptions(list)
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
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
    }
  }, [])

  return { options, loading, onSearch, onDropdownVisibleChange }
}
