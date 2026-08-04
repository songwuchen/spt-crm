// 合同选择字段(contract)。值为合同 id；列表/只读通过 getContractLabelMap 解析合同号。
import { useEffect, useMemo, useState } from 'react'
import { Select, Spin } from 'antd'
import { contractApi } from '@/api/contract'
import type { ContractItem } from '@/api/types'

interface COpt { label: string; value: string }

let cache: { opts: COpt[]; ts: number } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<COpt[]> | null = null

function toOpts(rows: Pick<ContractItem, 'id' | 'contract_no' | 'drawing_no'>[]): COpt[] {
  return (rows || []).map((c) => {
    const no = c.contract_no || c.id
    const draw = c.drawing_no ? ` · 图纸 ${c.drawing_no}` : ''
    return { label: `${no}${draw}`, value: c.id }
  })
}

async function fetchList(keyword?: string): Promise<COpt[]> {
  const r = await contractApi.list({ pageNo: 1, pageSize: 50, keyword: keyword || undefined })
  const items = (r.data as { items?: ContractItem[] } | undefined)?.items
    || (Array.isArray(r.data) ? r.data as ContractItem[] : [])
  return toOpts(items || [])
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
      const r = await contractApi.get(id)
      const c = r.data
      if (c?.id) {
        const opt = toOpts([c])[0]
        next = [...next, opt]
        have.add(id)
        cache = { opts: next, ts: Date.now() }
      }
    } catch {
      // 兼容历史手填合同号：当作展示文案
      next = [...next, { label: id, value: id }]
      have.add(id)
    }
  }
  return next
}

/** 列表/导出用：合同 id → 合同号 */
export async function getContractLabelMap(ids: string[]): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts = await loadBase()
  if (raws.length) opts = await hydrateMissing(raws, opts)
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
      placeholder={placeholder || '搜索合同号 / 图纸编号'}
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
