// 客户选择字段(customer)。值为客户 id。
import { useEffect, useMemo, useRef, useState } from 'react'
import { Select, Spin } from 'antd'
import { customerApi } from '@/api/customer'
import type { Customer } from '@/api/types'

interface COpt { label: string; value: string }

let cache: { opts: COpt[]; ts: number } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<COpt[]> | null = null

function toOpts(rows: Pick<Customer, 'id' | 'name' | 'customer_code'>[]): COpt[] {
  return (rows || []).map((c) => ({
    label: c.name ? `${c.name}${c.customer_code ? `（${c.customer_code}）` : ''}` : (c.customer_code || c.id),
    value: c.id,
  }))
}

async function fetchList(keyword?: string): Promise<COpt[]> {
  const r = await customerApi.list({ pageNo: 1, pageSize: 50, keyword: keyword || undefined })
  return toOpts(r.data?.items || [])
}

async function loadBase(): Promise<COpt[]> {
  if (cache && Date.now() - cache.ts < TTL) return cache.opts
  if (inflight) return inflight
  inflight = fetchList()
    .then((opts) => {
      cache = { opts, ts: Date.now() }
      return opts
    })
    .catch(() => cache?.opts || [])
    .finally(() => { inflight = null })
  return inflight
}

async function hydrateMissing(ids: string[], opts: COpt[]): Promise<COpt[]> {
  let next = opts
  const have = new Set(next.map((o) => o.value))
  for (const id of ids) {
    if (!id || have.has(id)) continue
    try {
      const r = await customerApi.get(id)
      const c = r.data
      if (c?.id) {
        const opt = toOpts([c])[0]
        next = [...next, opt]
        have.add(id)
        cache = { opts: next, ts: Date.now() }
      }
    } catch {
      next = [...next, { label: id, value: id }]
      have.add(id)
    }
  }
  return next
}

/** 列表/导出用：客户 id → 显示名 */
export async function getCustomerLabelMap(ids: string[]): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts = await loadBase()
  if (raws.length) opts = await hydrateMissing(raws, opts)
  const map: Record<string, string> = {}
  for (const o of opts) map[o.value] = o.label
  return map
}

export default function CustomerField({
  value, onChange, readonly, placeholder,
}: {
  value: unknown
  onChange?: (v: string | undefined) => void
  readonly?: boolean
  placeholder?: string
}) {
  const raw = value == null || value === '' ? undefined : String(value)
  const [opts, setOpts] = useState<COpt[]>(cache?.opts || [])
  const [loading, setLoading] = useState(false)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    loadBase()
      .then(async (base) => {
        const next = raw ? await hydrateMissing([raw], base) : base
        if (alive) setOpts(next)
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [raw])

  useEffect(() => () => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
  }, [])

  const options = useMemo(() => {
    if (!raw || opts.some((o) => o.value === raw)) return opts
    return [{ label: raw, value: raw }, ...opts]
  }, [opts, raw])

  if (readonly) {
    const label = options.find((o) => o.value === raw)?.label || raw || '—'
    return <span>{label}</span>
  }

  return (
    <Select
      showSearch
      allowClear
      filterOption={false}
      style={{ width: '100%' }}
      placeholder={placeholder || '搜索客户公司（可不选商机，直接选客户）'}
      value={raw}
      options={options}
      loading={loading}
      notFoundContent={loading ? <Spin size="small" /> : '无匹配客户'}
      onSearch={(kw) => {
        if (searchTimer.current) clearTimeout(searchTimer.current)
        searchTimer.current = setTimeout(() => {
          setLoading(true)
          fetchList(kw?.trim() || undefined)
            .then((found) => {
              setOpts((prev) => {
                const map = new Map(found.map((o) => [o.value, o]))
                if (raw && !map.has(raw)) {
                  const keep = prev.find((o) => o.value === raw) || { label: raw, value: raw }
                  map.set(raw, keep)
                }
                const merged = Array.from(map.values())
                cache = { opts: merged, ts: Date.now() }
                return merged
              })
            })
            .finally(() => setLoading(false))
        }, 250)
      }}
      onChange={(v) => onChange?.(v)}
    />
  )
}
