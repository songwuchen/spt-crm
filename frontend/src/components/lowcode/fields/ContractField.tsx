// 合同选择字段(contract)。值为合同 id；列表/只读以图纸编号为主展示（无图纸号时回退合同号）。
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

/** 关联合同：优先显示图纸编号；无图纸号时显示合同号。 */
function contractLabel(c: ContractRow): string {
  const draw = String(c.drawing_no || '').trim()
  const no = String(c.contract_no || '').trim()
  if (draw && no && draw !== no) return `${draw}（${no}）`
  return draw || no || c.id
}

function toOpts(rows: ContractRow[]): COpt[] {
  return (rows || []).map((c) => ({ label: contractLabel(c), value: c.id }))
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

/** 列表/导出用：合同 id → 图纸编号（优先） */
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
  const searchSeq = useRef(0)

  useEffect(() => {
    let alive = true
    setLoading(true)
    ;(async () => {
      try {
        // 只读：不拉全量列表，仅按 id 回显图纸编号
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
      defaultActiveFirstOption={false}
      style={{ width: '100%' }}
      placeholder={placeholder || '按图纸编号搜索'}
      value={raw}
      options={options}
      loading={loading}
      notFoundContent={loading ? <Spin size="small" /> : '无匹配合同'}
      onSearch={(kw) => {
        if (searchTimer.current) clearTimeout(searchTimer.current)
        const q = kw.trim()
        searchTimer.current = setTimeout(() => {
          const seq = ++searchSeq.current
          setLoading(true)
          const req = q ? fetchList(q) : loadBase()
          req
            .then(async (found) => {
              if (seq !== searchSeq.current) return
              // 远程搜索结果直接替换列表（filterOption=false 时合并旧项会导致“搜了不变”）
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
        // 重新打开时若无搜索词，恢复默认列表
        if (!searchTimer.current) {
          void loadBase().then((base) => {
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
