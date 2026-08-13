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

/** code=仅编号（列表「项目号」列）；preferCode=编号·名称（表单选择）；default=名称（编号） */
export type ProjectLabelMode = 'default' | 'preferCode' | 'code'

function projectLabel(p: ProjRow, mode: ProjectLabelMode = 'default'): string {
  const code = String(p.project_code || '').trim()
  const name = String(p.name || '').trim()
  if (mode === 'code') return code || name || p.id
  if (mode === 'preferCode') {
    if (code && name && code !== name) return `${code} · ${name}`
    return code || name || p.id
  }
  if (name && code && name !== code) return `${name}（${code}）`
  return name || code || p.id
}

function toOpts(rows: ProjRow[], mode: ProjectLabelMode = 'default'): ProjOpt[] {
  return (rows || []).map((p) => ({
    label: projectLabel(p, mode),
    value: p.id,
  }))
}

async function fetchList(keyword?: string, mode: ProjectLabelMode = 'default'): Promise<ProjOpt[]> {
  const r = await client.get<unknown, ApiResponse<ProjRow[]>>('/api/v1/lc/pickable-projects', {
    params: { keyword: keyword || undefined },
    ...silent,
  })
  return toOpts(r.data || [], mode)
}

async function loadBase(mode: ProjectLabelMode = 'default'): Promise<ProjOpt[]> {
  // 默认展示缓存与 preferCode/code 分开
  if (mode === 'default' && cache && Date.now() - cache.ts < TTL) return cache.opts
  if (mode === 'default' && inflight) return inflight
  const req = fetchList(undefined, mode)
  if (mode === 'default') {
    inflight = req
      .then((opts) => {
        cache = { opts, ts: Date.now() }
        return opts
      })
      .catch(() => cache?.opts || [])
      .finally(() => { inflight = null })
    return inflight
  }
  return req.catch(() => [])
}

async function hydrateMissing(
  ids: string[], opts: ProjOpt[], mode: ProjectLabelMode = 'default',
): Promise<ProjOpt[]> {
  let next = opts
  const have = new Set(next.map((o) => o.value))
  const missing = ids.filter((id) => id && !have.has(id))
  if (!missing.length) return next
  try {
    const r = await client.get<unknown, ApiResponse<ProjRow[]>>('/api/v1/lc/pickable-projects', {
      params: { ids: missing.join(',') },
      ...silent,
    })
    const found = toOpts(r.data || [], mode)
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
    if (mode === 'default') cache = { opts: next, ts: Date.now() }
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

/** 安装图选商机后带出业务员/公司名称/事项 */
export async function fetchInstallNoticeProjectFill(
  projectId: string,
): Promise<Record<string, unknown>> {
  const r = await client.get<unknown, ApiResponse<{ fill?: Record<string, unknown> }>>(
    `/api/v1/lc/pickable-projects/${encodeURIComponent(projectId)}/install-notice-fill`,
    { ...silent },
  )
  return (r.data?.fill && typeof r.data.fill === 'object') ? r.data.fill : {}
}

export const INSTALL_NOTICE_PROJECT_FILL_CLEAR = ['sales_person', 'customer_name', 'matter']

/** 列表/导出用：商机 id → 显示名。mode=code 时仅编号（安装图列表「项目号」列） */
export async function getProjectLabelMap(
  ids: string[],
  mode: ProjectLabelMode = 'default',
): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts: ProjOpt[] = []
  if (raws.length) opts = await hydrateMissing(raws, [], mode)
  else opts = await loadBase(mode)
  const map: Record<string, string> = {}
  for (const o of opts) map[o.value] = o.label
  return map
}

export default function ProjectField({
  value, onChange, readonly, placeholder, preferCode,
}: {
  value: unknown
  onChange?: (v: string | undefined) => void
  readonly?: boolean
  placeholder?: string
  /** 优先展示商机编号（安装图「项目号选择」） */
  preferCode?: boolean
}) {
  const labelMode: ProjectLabelMode = preferCode ? 'preferCode' : 'default'
  const raw = value == null || value === '' ? undefined : String(value)
  const [opts, setOpts] = useState<ProjOpt[]>((labelMode === 'default' && cache?.opts) || [])
  const [loading, setLoading] = useState(false)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    let alive = true
    setLoading(true)
    ;(async () => {
      try {
        if (readonly) {
          const next = raw ? await hydrateMissing([raw], [], labelMode) : []
          if (alive) setOpts(next)
          return
        }
        const base = await loadBase(labelMode)
        const next = raw ? await hydrateMissing([raw], base, labelMode) : base
        if (alive) setOpts(next)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
  }, [raw, readonly, labelMode])

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
    fetchList(kw.trim() || undefined, labelMode)
      .then((found) => {
        setOpts((prev) => {
          const map = new Map(found.map((o) => [o.value, o]))
          if (raw && !map.has(raw)) {
            const keep = prev.find((o) => o.value === raw) || { label: raw, value: raw }
            map.set(raw, keep)
          }
          const merged = Array.from(map.values())
          if (labelMode === 'default') cache = { opts: merged, ts: Date.now() }
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
      placeholder={placeholder || (preferCode ? '搜索商机编号 / 名称' : '搜索商机名称 / 编号')}
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
