// 合同选择字段(contract)。值为合同 id；列表/只读通过 getContractLabelMap 解析合同号。
// 审批人未必有 contract:view：回显走 /lc/pickable-contracts，只读不拉全量列表。
import { useEffect, useMemo, useRef, useState } from 'react'
import { Select, Spin } from 'antd'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface COpt { label: string; value: string }
type ContractRow = { id: string; contract_no?: string | null; drawing_no?: string | null }

let cache: { opts: COpt[]; ts: number } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<COpt[]> | null = null
const silent = { headers: { 'X-Silent-Error': '1' } }

function toOpts(rows: ContractRow[]): COpt[] {
  return (rows || []).map((c) => {
    const no = c.contract_no || c.id
    const draw = c.drawing_no ? ` · 图纸 ${c.drawing_no}` : ''
    return { label: `${no}${draw}`, value: c.id }
  })
}

async function fetchList(keyword?: string): Promise<COpt[]> {
  const r = await client.get<unknown, ApiResponse<ContractRow[]>>('/api/v1/lc/pickable-contracts', {
    params: { keyword: keyword || undefined },
    ...silent,
  })
  return toOpts(r.data || [])
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
  const missing = ids.filter((id) => id && !have.has(id))
  if (!missing.length) return next
  try {
    const r = await client.get<unknown, ApiResponse<ContractRow[]>>('/api/v1/lc/pickable-contracts', {
      params: { ids: missing.join(',') },
      ...silent,
    })
    const found = toOpts(r.data || [])
    for (const o of found) {
      if (!have.has(o.value)) {
        next = [...next, o]
        have.add(o.value)
      }
    }
    for (const id of missing) {
      if (!have.has(id)) {
        next = [...next, { label: id, value: id }]
        have.add(id)
      }
    }
    cache = { opts: next, ts: Date.now() }
  } catch {
    for (const id of missing) {
      if (!have.has(id)) {
        next = [...next, { label: id, value: id }]
        have.add(id)
      }
    }
  }
  return next
}

/** 列表/导出用：合同 id → 合同号 */
export async function getContractLabelMap(ids: string[]): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts: COpt[] = []
  if (raws.length) opts = await hydrateMissing(raws, [])
  else opts = await loadBase()
  const map: Record<string, string> = {}
  for (const o of opts) map[o.value] = o.label
  return map
}

export default function ContractField({
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
    ;(async () => {
      try {
        // 只读：不拉全量列表，仅按 id 回显合同号
        if (readonly) {
          const next = raw ? await hydrateMissing([raw], []) : []
          if (alive) setOpts(next)
          return
        }
        const base = await loadBase()
        const next = raw ? await hydrateMissing([raw], base) : base
        if (alive) setOpts(next)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
  }, [raw, readonly])

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
      placeholder={placeholder || '搜索合同号 / 图纸编号'}
      value={raw}
      options={options}
      loading={loading}
      notFoundContent={loading ? <Spin size="small" /> : null}
      onSearch={(kw) => {
        if (searchTimer.current) clearTimeout(searchTimer.current)
        searchTimer.current = setTimeout(() => {
          setLoading(true)
          fetchList(kw)
            .then((found) => setOpts((prev) => {
              const map = new Map(prev.map((o) => [o.value, o]))
              for (const o of found) map.set(o.value, o)
              const merged = Array.from(map.values())
              cache = { opts: merged, ts: Date.now() }
              return merged
            }))
            .catch(() => {})
            .finally(() => setLoading(false))
        }, 250)
      }}
      onChange={(v) => onChange?.(v)}
    />
  )
}
