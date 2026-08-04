// 商机选择字段(project)。值为商机 id；列表/只读通过 getProjectLabelMap 解析名称。
import { useEffect, useMemo, useState } from 'react'
import { Select, Spin } from 'antd'
import { projectApi } from '@/api/project'

interface ProjOpt { label: string; value: string }

let cache: { opts: ProjOpt[]; ts: number } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<ProjOpt[]> | null = null

function toOpts(rows: { id: string; name?: string; project_code?: string }[]): ProjOpt[] {
  return (rows || []).map((p) => ({
    label: p.name ? `${p.name}${p.project_code ? `（${p.project_code}）` : ''}` : (p.project_code || p.id),
    value: p.id,
  }))
}

async function fetchList(keyword?: string): Promise<ProjOpt[]> {
  const r = await projectApi.list({ pageNo: 1, pageSize: 50, keyword: keyword || undefined })
  return toOpts(r.data?.items || [])
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
  for (const id of ids) {
    if (!id || have.has(id)) continue
    try {
      const r = await projectApi.get(id)
      const p = r.data
      if (p?.id) {
        const opt = toOpts([p])[0]
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

/** 列表/导出用：商机 id → 显示名 */
export async function getProjectLabelMap(ids: string[]): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts = await loadBase()
  if (raws.length) opts = await hydrateMissing(raws, opts)
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
      placeholder={placeholder || '搜索商机名称 / 编号'}
      value={raw}
      options={options}
      loading={loading}
      notFoundContent={loading ? <Spin size="small" /> : null}
      onSearch={(kw) => {
        setLoading(true)
        fetchList(kw)
          .then((found) => setOpts((prev) => {
            const map = new Map(prev.map((o) => [o.value, o]))
            for (const o of found) map.set(o.value, o)
            const merged = Array.from(map.values())
            cache = { opts: merged, ts: Date.now() }
            return merged
          }))
          .finally(() => setLoading(false))
      }}
      onChange={(v) => onChange?.(v)}
    />
  )
}
