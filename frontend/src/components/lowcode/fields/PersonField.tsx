// 人员选择字段(person / person_multi)。值为用户 id(单)或 id 数组(多)。
// 兼容系统默认流里存的 username：options 同时挂 id 与 username，并用 keyword 补齐回显。
// props.pickable_scope：{ scope_code } 优先；兼容旧 { role_codes }。
// deptIds：再按部门（含下级）收窄，常与科室 offices / offices_multi 联动。
import { useEffect, useMemo, useState } from 'react'
import { Select, Spin } from 'antd'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface UserOpt { label: string; value: string; username?: string }
type PickableUser = { id: string; name: string; username?: string }

export type PickableScope = {
  scope_code?: string
  role_codes?: string[]
  filter_by_fields?: string[]
}

type CacheEntry = { opts: UserOpt[]; ts: number }
const cacheByKey = new Map<string, CacheEntry>()
const inflightByKey = new Map<string, Promise<UserOpt[]>>()
const TTL = 5 * 60 * 1000

function scopeKey(scope?: PickableScope | null, deptIds?: string[] | null): string {
  const sc = String(scope?.scope_code || '')
  const codes = [...(scope?.role_codes || [])].map(String).filter(Boolean).sort()
  const depts = [...(deptIds || [])].map(String).filter(Boolean).sort()
  return `scope:${sc}|roles:${codes.join(',')}|depts:${depts.join(',')}`
}

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

async function loadBaseUsers(scope?: PickableScope | null, deptIds?: string[] | null): Promise<UserOpt[]> {
  const key = scopeKey(scope, deptIds)
  const cached = cacheByKey.get(key)
  if (cached && Date.now() - cached.ts < TTL) {
    if (!cached.opts.length || cached.opts.some((o) => o.username)) return cached.opts
  }
  const pending = inflightByKey.get(key)
  if (pending) return pending
  const params: Record<string, string> = {}
  if (scope?.scope_code) {
    params.scope_code = String(scope.scope_code)
  } else {
    const codes = scope?.role_codes?.filter(Boolean)
    if (codes?.length) params.role_codes = codes.join(',')
  }
  const depts = (deptIds || []).map(String).filter(Boolean)
  if (depts.length) params.dept_ids = depts.join(',')
  const p = fetchPickable(params)
    .then((opts) => {
      cacheByKey.set(key, { opts, ts: Date.now() })
      return opts
    })
    .catch(() => cacheByKey.get(key)?.opts || [])
    .finally(() => { inflightByKey.delete(key) })
  inflightByKey.set(key, p)
  return p
}

async function hydrateMissing(raws: string[], opts: UserOpt[]): Promise<UserOpt[]> {
  let next = opts
  for (const raw of raws) {
    if (next.some((o) => o.value === raw || o.username === raw)) continue
    try {
      // 标准 UUID；兼容旧版宽松匹配
      const isUuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(raw)
        || /^[0-9a-f]{8}-[0-9a-f-]{20,}$/i.test(raw)
      let found = await fetchPickable(isUuid ? { ids: raw } : { usernames: raw })
      if (!found.some((o) => o.value === raw || o.username === raw)) {
        found = await fetchPickable({ keyword: raw })
      }
      let hit = found.find((o) => o.value === raw || o.username === raw)
      if (!hit && !isUuid && found.length === 1) {
        hit = { ...found[0], username: raw }
      }
      if (!hit && !isUuid) {
        const byIdOnly = found[0]
        if (byIdOnly) hit = { ...byIdOnly, username: raw }
      }
      if (hit) {
        next = mergeOpts(next, [{ ...hit, username: hit.username || (!isUuid ? raw : hit.username) }, ...found])
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
      const isMongo = /^[0-9a-f]{24}$/i.test(raw)
      const label = isMongo ? `未知人员(${raw.slice(0, 8)}…)` : raw
      out.unshift({ label, value: raw })
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

/** 从表单值按字段 id 提取部门 id（默认 offices / offices_multi） */
export function filterDeptIdsFromValues(
  values: Record<string, unknown> | undefined | null,
  fieldIds?: string[] | null,
): string[] {
  if (!values) return []
  const keys = fieldIds?.length ? fieldIds : ['offices', 'offices_multi']
  const out: string[] = []
  for (const key of keys) {
    const v = values[key]
    if (Array.isArray(v)) out.push(...v.map(String).filter(Boolean))
    else if (v != null && v !== '') out.push(String(v))
  }
  return [...new Set(out)]
}

/** @deprecated 使用 filterDeptIdsFromValues */
export function officeDeptIdsFromValues(values: Record<string, unknown> | undefined | null): string[] {
  return filterDeptIdsFromValues(values)
}

/** 是否应按科室字段收窄人选 */
export function shouldFilterByDeptFields(
  scope: PickableScope | null | undefined,
  fieldId?: string,
): boolean {
  if (!scope) return false
  if (scope.filter_by_fields?.length) return true
  const hasScope = !!(scope.scope_code || scope.role_codes?.length)
  return hasScope && (fieldId === 'design_assignees' || fieldId === 'designer')
}

export default function PersonField({
  value, onChange, multi, readonly, placeholder, pickableScope, deptIds,
}: {
  /** Form.Item 会注入；单独使用时可省略 */
  value?: unknown
  onChange?: (v: unknown) => void
  multi?: boolean
  readonly?: boolean
  placeholder?: string
  /** 对齐简道云：scope_code 优先，兼容 role_codes */
  pickableScope?: PickableScope | null
  /** 按部门（含下级）再收窄；常来自同单科室字段 */
  deptIds?: string[] | null
}) {
  const scopeKeyStr = scopeKey(pickableScope, deptIds)
  const [opts, setOpts] = useState<UserOpt[]>(() => cacheByKey.get(scopeKeyStr)?.opts || [])
  const [loading, setLoading] = useState(!cacheByKey.get(scopeKeyStr))

  useEffect(() => {
    let alive = true
    const raws = asRawList(value, multi)
    setLoading(true)
    ;(async () => {
      try {
        // 只读：不按科室收窄，始终按 id/username 回显姓名（历史单据可能跨科室）
        const loadDepts = readonly ? undefined : deptIds
        let next = await loadBaseUsers(pickableScope, loadDepts)
        if (!alive) return
        if (!readonly && deptIds?.length) {
          // 编辑：有科室过滤时，清掉范围外已选，避免「能看见但提交被拒」
          const allowed = new Set(next.map((o) => o.value))
          const inScope = raws.filter((r) => allowed.has(r) || next.some((o) => o.username === r))
          if (inScope.length !== raws.length && onChange) {
            onChange(multi ? inScope : (inScope[0] ?? undefined))
          }
          next = await hydrateMissing(inScope, next)
        } else {
          next = await hydrateMissing(raws, next)
        }
        if (!alive) return
        setOpts(next)
      } finally {
        if (alive) setLoading(false)
      }
    })()
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 随范围/科室/当前值重载
  }, [value, multi, scopeKeyStr, readonly])

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

  const hasScope = !!(pickableScope?.scope_code || pickableScope?.role_codes?.length)
  const hasDept = !!(deptIds && deptIds.length)
  let emptyHint = '无用户'
  if (hasScope && hasDept) {
    emptyHint = '该科室下暂无符合范围的人员，请先选科室或到「可选范围」维护成员'
  } else if (hasScope) {
    emptyHint = '无可选人员（请到「系统管理 → 可选范围」勾选成员）'
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
      notFoundContent={loading ? <Spin size="small" /> : emptyHint}
      onChange={(v) => onChange?.(v)}
    />
  )
}
