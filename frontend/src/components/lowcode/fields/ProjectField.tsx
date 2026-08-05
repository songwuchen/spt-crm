// 商机选择字段(project)。值为商机 id；列表/只读通过名称回显。
// 审批人未必有 project:view：回显走 /lc/pickable-projects，只读不拉全量列表。
import { useEffect, useMemo, useRef, useState } from 'react'
import { Select, Spin } from 'antd'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface ProjOpt { label: string; value: string }
type ProjRow = { id: string; name?: string; project_code?: string }

let cache: { opts: ProjOpt[]; ts: number } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<ProjOpt[]> | null = null
const silent = { headers: { 'X-Silent-Error': '1' } }

function toOpts(rows: ProjRow[]): ProjOpt[] {
  return (rows || []).map((p) => ({
    label: p.name ? `${p.name}${p.project_code ? `（${p.project_code}）` : ''}` : (p.project_code || p.id),
    value: p.id,
  }))
}

async function fetchList(keyword?: string): Promise<ProjOpt[]> {
  const r = await client.get<unknown, ApiResponse<ProjRow[]>>('/api/v1/lc/pickable-projects', {
    params: { keyword: keyword || undefined },
    ...silent,
  })
  return toOpts(r.data || [])
}

async function loadBase(): Promise<ProjOpt[]> {
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

async function hydrateMissing(ids: string[], opts: ProjOpt[]): Promise<ProjOpt[]> {
  let next = opts
  const have = new Set(next.map((o) => o.value))
  const missing = ids.filter((id) => id && !have.has(id))
  if (!missing.length) return next
  try {
    const r = await client.get<unknown, ApiResponse<ProjRow[]>>('/api/v1/lc/pickable-projects', {
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

/** 列表/导出用：商机 id → 显示名 */
export async function getProjectLabelMap(ids: string[]): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts: ProjOpt[] = []
  if (raws.length) opts = await hydrateMissing(raws, [])
  else opts = await loadBase()
  const map: Record<string, string> = {}
  for (const o of opts) map[o.value] = o.label
  return map
}

export default function ProjectField({
  value, onChange, readonly, placeholder,
}: {
  value: unknown
  onChange?: (v: string | undefined) => void
  readonly?: boolean
  placeholder?: string
}) {
  const raw = value == null || value === '' ? undefined : String(value)
  const [opts, setOpts] = useState<ProjOpt[]>(cache?.opts || [])
  const [loading, setLoading] = useState(false)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    ;(async () => {
      try {
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

  const runSearch = (kw: string) => {
    setLoading(true)
    fetchList(kw.trim() || undefined)
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
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  return (
    <Select
      showSearch
      allowClear
      filterOption={false}
      style={{ width: '100%' }}
      placeholder={placeholder || '搜索商机名称 / 编号'}
      value={raw}
      options={options}
      loading={loading}
      notFoundContent={loading ? <Spin size="small" /> : '无匹配商机'}
      onSearch={(kw) => {
        if (searchTimer.current) clearTimeout(searchTimer.current)
        searchTimer.current = setTimeout(() => runSearch(kw), 250)
      }}
      onChange={(v) => onChange?.(v)}
    />
  )
}
