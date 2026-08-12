// 技术协议评审选择字段。值为评审 id；选中后可由父组件带出流水号。
import { useEffect, useMemo, useRef, useState } from 'react'
import { Select, Spin } from 'antd'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface TOpt { label: string; value: string }
type TarRow = {
  id: string
  review_code?: string | null
  company_name?: string | null
  project_title?: string | null
  applicant_name?: string | null
  department_name?: string | null
}

let cache: { opts: TOpt[]; ts: number; filterKey: string } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<TOpt[]> | null = null
let inflightKey = ''
const silent = { headers: { 'X-Silent-Error': '1' } }

function tarLabel(r: TarRow): string {
  const code = String(r.review_code || '').trim()
  const company = String(r.company_name || '').trim()
  const project = String(r.project_title || '').trim()
  const parts = [code, company, project].filter(Boolean)
  return parts.length ? parts.join(' · ') : r.id
}

function toOpts(rows: TarRow[]): TOpt[] {
  return (rows || []).map((r) => ({ label: tarLabel(r), value: r.id }))
}

function filterKeyOf(applicantId?: string | null, departmentId?: string | null): string {
  return `${applicantId || ''}|${departmentId || ''}`
}

async function fetchList(
  keyword?: string,
  applicantId?: string | null,
  departmentId?: string | null,
): Promise<TOpt[]> {
  const r = await client.get<unknown, ApiResponse<TarRow[]>>('/api/v1/lc/pickable-tech-agreement-reviews', {
    params: {
      keyword: keyword || undefined,
      applicant_id: applicantId || undefined,
      department_id: departmentId || undefined,
    },
    ...silent,
  })
  return toOpts(r.data || [])
}

async function loadBase(applicantId?: string | null, departmentId?: string | null): Promise<TOpt[]> {
  const filterKey = filterKeyOf(applicantId, departmentId)
  if (cache && cache.filterKey === filterKey && Date.now() - cache.ts < TTL) return cache.opts
  if (inflight && inflightKey === filterKey) return inflight
  inflightKey = filterKey
  inflight = fetchList(undefined, applicantId, departmentId)
    .then((opts) => {
      cache = { opts, ts: Date.now(), filterKey }
      return opts
    })
    .catch(() => (cache?.filterKey === filterKey ? cache.opts : []) || [])
    .finally(() => { inflight = null })
  return inflight
}

async function hydrateMissing(ids: string[], opts: TOpt[]): Promise<TOpt[]> {
  let next = opts
  const have = new Set(next.map((o) => o.value))
  const missing = ids.filter((id) => id && !have.has(id))
  if (!missing.length) return next
  try {
    const r = await client.get<unknown, ApiResponse<TarRow[]>>('/api/v1/lc/pickable-tech-agreement-reviews', {
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

/** 生产卡选技术协议评审带出流水号 */
export async function fetchProdCardTarFill(reviewId: string): Promise<Record<string, unknown>> {
  const r = await client.get<unknown, ApiResponse<{ fill?: Record<string, unknown> }>>(
    `/api/v1/lc/pickable-tech-agreement-reviews/${encodeURIComponent(reviewId)}/prod-card-fill`,
    { ...silent },
  )
  return (r.data?.fill && typeof r.data.fill === 'object') ? r.data.fill : {}
}

export const PROD_CARD_TAR_FILL_CLEAR = ['contract_tech_review_sn']

function personIdOf(raw: unknown): string | undefined {
  if (raw == null || raw === '') return undefined
  if (Array.isArray(raw)) {
    const first = raw[0]
    if (first == null || first === '') return undefined
    if (typeof first === 'object' && first !== null && 'id' in first) {
      return String((first as { id: unknown }).id)
    }
    return String(first)
  }
  if (typeof raw === 'object' && raw !== null && 'id' in raw) {
    return String((raw as { id: unknown }).id)
  }
  return String(raw)
}

function deptIdOf(raw: unknown): string | undefined {
  if (raw == null || raw === '') return undefined
  if (Array.isArray(raw)) {
    const first = raw[0]
    if (first == null || first === '') return undefined
    return String(first)
  }
  return String(raw)
}

export function resolveTarFilterIds(
  allValues: Record<string, unknown>,
  submitterField?: string,
  departmentField?: string,
): { applicantId?: string; departmentId?: string } {
  return {
    applicantId: submitterField ? personIdOf(allValues[submitterField]) : undefined,
    departmentId: departmentField ? deptIdOf(allValues[departmentField]) : undefined,
  }
}

export default function TechAgreementReviewField({
  value, onChange, readonly, placeholder, applicantId, departmentId,
}: {
  value: unknown
  onChange?: (v: string | undefined) => void
  readonly?: boolean
  placeholder?: string
  applicantId?: string | null
  departmentId?: string | null
}) {
  const raw = value == null || value === '' ? undefined : String(value)
  const appId = applicantId || undefined
  const dept = departmentId || undefined
  const [opts, setOpts] = useState<TOpt[]>([])
  const [loading, setLoading] = useState(false)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const searchSeq = useRef(0)

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
        const base = await loadBase(appId, dept)
        const next = raw ? await hydrateMissing([raw], base) : base
        if (alive) setOpts(next)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
  }, [raw, readonly, appId, dept])

  const options = useMemo(() => {
    if (!raw || opts.some((o) => o.value === raw)) return opts
    return [{ label: raw, value: raw }, ...opts]
  }, [opts, raw])

  if (readonly) {
    const label = options.find((o) => o.value === raw)?.label || raw || '—'
    return <span>{label}</span>
  }

  const filtered = !!(appId || dept)
  return (
    <Select
      showSearch
      allowClear
      filterOption={false}
      defaultActiveFirstOption={false}
      style={{ width: '100%' }}
      placeholder={placeholder || (filtered ? '按流水号/公司/项目搜索（本提交人或本部门）' : '按流水号/公司/项目搜索')}
      value={raw}
      options={options}
      loading={loading}
      notFoundContent={loading ? <Spin size="small" /> : (filtered ? '无匹配技术协议评审' : '无匹配记录')}
      onSearch={(kw) => {
        if (searchTimer.current) clearTimeout(searchTimer.current)
        const q = kw.trim()
        searchTimer.current = setTimeout(() => {
          const seq = ++searchSeq.current
          setLoading(true)
          const req = q ? fetchList(q, appId, dept) : loadBase(appId, dept)
          req
            .then(async (found) => {
              if (seq !== searchSeq.current) return
              let next = found
              if (raw && !next.some((o) => o.value === raw)) {
                next = await hydrateMissing([raw], next)
              }
              if (seq !== searchSeq.current) return
              setOpts(next)
            })
            .catch(() => {})
            .finally(() => {
              if (seq === searchSeq.current) setLoading(false)
            })
        }, 250)
      }}
      onDropdownVisibleChange={(open) => {
        if (!open) return
        if (!searchTimer.current) {
          void loadBase(appId, dept).then((base) => {
            setOpts((prev) => {
              if (raw && !base.some((o) => o.value === raw)) {
                const cur = prev.find((o) => o.value === raw)
                return cur ? [cur, ...base] : base
              }
              return base
            })
          })
        }
      }}
      onChange={(v) => onChange?.(v)}
    />
  )
}
