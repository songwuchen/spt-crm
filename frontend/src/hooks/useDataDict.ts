import { useState, useEffect } from 'react'
import { settingsApi } from '@/api/settings'

interface DictItem {
  dict_code: string
  dict_label: string
  color?: string
}

const cache: Record<string, { data: DictItem[]; ts: number }> = {}
const CACHE_TTL = 5 * 60 * 1000 // 5 minutes

/**
 * Load data dictionary options for a given dict_type.
 * Returns { label, value } array for direct use in Ant Design Select.
 * Falls back to provided defaults if API returns empty.
 */
export function useDataDict(
  dictType: string,
  fallback?: { label: string; value: string }[],
) {
  const [options, setOptions] = useState<{ label: string; value: string }[]>(fallback || [])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const cached = cache[dictType]
    if (cached && Date.now() - cached.ts < CACHE_TTL) {
      const opts = cached.data.map((d) => ({ label: d.dict_label, value: d.dict_code || d.dict_label }))
      setOptions(opts.length > 0 ? opts : fallback || [])
      return
    }

    setLoading(true)
    settingsApi.listDataDict(dictType)
      .then((r: any) => {
        const items: DictItem[] = (r.data || []).filter((d: any) => d.enabled)
        cache[dictType] = { data: items, ts: Date.now() }
        const opts = items.map((d) => ({ label: d.dict_label, value: d.dict_code || d.dict_label }))
        setOptions(opts.length > 0 ? opts : fallback || [])
      })
      .catch(() => {
        setOptions(fallback || [])
      })
      .finally(() => setLoading(false))
  }, [dictType])

  return { options, loading }
}
