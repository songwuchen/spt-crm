// 人员选择字段(person / person_multi)。值为用户 id(单)或 id 数组(多)。
// 兼容系统默认流里存的 username：options 同时挂 id 与 username，并用 keyword 补齐回显。
import { useEffect, useMemo, useState } from 'react'
import { Select, Spin } from 'antd'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface UserOpt { label: string; value: string; username?: string }
type PickableUser = { id: string; name: string; username?: string }

let cache: { opts: UserOpt[]; ts: number } | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<UserOpt[]> | null = null

function toOpts(rows: PickableUser[]): UserOpt[] {
  return (rows || []).map((u) => ({
    label: u.name || u.username || u.id,
    value: u.id,
    username: u.username || undefined,
  }))
}

async function fetchPickable(params?: Record<string, string>): Promise<UserOpt[]> {
  const res = await client.get<unknown, ApiResponse<PickableUser[]>>('/api/v1/lc/pickable-users', {
    params: params || {},
  })
  return toOpts(res.data || [])
}

function mergeOpts(base: UserOpt[], extra: UserOpt[]): UserOpt[] {
  const map = new Map(base.map((o) => [o.value, o]))
  for (const o of extra) map.set(o.value, o)
  return Array.from(map.values())
}

async function loadBaseUsers(): Promise<UserOpt[]> {
  if (cache && Date.now() - cache.ts < TTL) {
    // 无 username 的旧缓存作废（接口升级后需重拉）
    if (!cache.opts.length || cache.opts.some((o) => o.username)) return cache.opts
  }
  if (inflight) return inflight
  inflight = fetchPickable()
    .then((opts) => {
      cache = { opts, ts: Date.now() }
      return opts
    })
    .catch(() => cache?.opts || [])
    .finally(() => { inflight = null })
  return inflight
}

async function hydrateMissing(raws: string[], opts: UserOpt[]): Promise<UserOpt[]> {
  let next = opts
  for (const raw of raws) {
    if (next.some((o) => o.value === raw || o.username === raw)) continue
    try {
      // 优先 usernames/ids；旧后端不认这些参数时再用 keyword
      const isUuid = /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(raw)
      let found = await fetchPickable(isUuid ? { ids: raw } : { usernames: raw })
      if (!found.some((o) => o.value === raw || o.username === raw)) {
        found = await fetchPickable({ keyword: raw })
      }
      let hit = found.find((o) => o.value === raw || o.username === raw)
      // keyword 命中但响应无 username 时：把本次查询的工号挂到唯一结果上，供 dualOptions 回显
      if (!hit && !isUuid && found.length === 1) {
        hit = { ...found[0], username: raw }
      }
      if (!hit && !isUuid) {
        // 列表里可能已有该人（仅缺 username 字段）
        const byIdOnly = found[0]
        if (byIdOnly) hit = { ...byIdOnly, username: raw }
      }
      if (hit) {
        next = mergeOpts(next, [{ ...hit, username: hit.username || (!isUuid ? raw : hit.username) }, ...found])
        cache = { opts: next, ts: Date.now() }
      }
    } catch {
      /* ignore */
    }
  }
  return next
}

function asRawList(value: unknown, multi?: boolean): string[] {
  if (multi) {
    if (Array.isArray(value)) return value.map(String).filter(Boolean)
    if (value == null || value === '') return []
    return [String(value)]
  }
  if (value == null || value === '') return []
  return [String(value)]
}

/** id + username 双 value，同一姓名，保证存工号也能显示人名。
 *
 * 注意：下拉列表里每人只展示一条（优先 id）；仅当当前值本身是 username
 * （且尚未被 id 选项覆盖）时，才额外挂一条 username 选项用于回显。
 * 否则搜索「杨」会出现「杨丽丽」两条，看起来像脏数据。
 */
function dualOptions(opts: UserOpt[], raws: string[]): UserOpt[] {
  const out: UserOpt[] = []
  const seen = new Set<string>()
  for (const o of opts) {
    if (!seen.has(o.value)) {
      out.push({ label: o.label, value: o.value, username: o.username })
      seen.add(o.value)
    }
  }
  for (const raw of raws) {
    if (seen.has(raw)) continue
    const hit = opts.find((o) => o.username === raw || o.value === raw)
    if (hit) {
      out.unshift({ label: hit.label, value: raw, username: hit.username || raw })
      seen.add(raw)
    } else {
      out.unshift({ label: raw, value: raw })
      seen.add(raw)
    }
  }
  return out
}

/** 列表/导出用：用户 id 或工号 → 显示名 */
export async function getPersonLabelMap(ids: string[]): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts = await loadBaseUsers()
  if (raws.length) opts = await hydrateMissing(raws, opts)
  const map: Record<string, string> = {}
  for (const o of opts) {
    map[o.value] = o.label
    if (o.username) map[o.username] = o.label
  }
  return map
}

export default function PersonField({
  value, onChange, multi, readonly, placeholder,
}: {
  value: unknown
  onChange?: (v: unknown) => void
  multi?: boolean
  readonly?: boolean
  placeholder?: string
}) {
  const [opts, setOpts] = useState<UserOpt[]>(cache?.opts || [])
  const [loading, setLoading] = useState(!cache)

  useEffect(() => {
    let alive = true
    const raws = asRawList(value, multi)
    ;(async () => {
      try {
        let next = await loadBaseUsers()
        if (!alive) return
        next = await hydrateMissing(raws, next)
        if (!alive) return
        setOpts(next)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
  }, [value, multi])

  const raws = useMemo(() => asRawList(value, multi), [value, multi])
  const selectOpts = useMemo(() => dualOptions(opts, raws), [opts, raws])

  const nameOf = (raw: string) => {
    const hit = opts.find((o) => o.value === raw || o.username === raw)
      || selectOpts.find((o) => o.value === raw)
    return hit?.label || raw
  }

  if (readonly) {
    if (!raws.length) return <div style={{ paddingTop: 4 }}>—</div>
    return <div style={{ paddingTop: 4 }}>{raws.map(nameOf).join('，')}</div>
  }

  return (
    <Select
      style={{ width: '100%' }}
      mode={multi ? 'multiple' : undefined}
      showSearch
      allowClear
      loading={loading}
      placeholder={placeholder || '选择人员'}
      value={(value as string | string[]) ?? (multi ? [] : undefined)}
      options={selectOpts}
      optionFilterProp="label"
      notFoundContent={loading ? <Spin size="small" /> : '无用户'}
      onChange={(v) => onChange?.(v)}
    />
  )
}
