// 部门选择字段(department / department_multi)。值为部门 id(单)或 id 数组(多)。
// props.pickable_scope.scope_code 可限制可选部门树。
import { useEffect, useState } from 'react'
import { TreeSelect } from 'antd'
import client from '@/api/client'
import type { ApiResponse, Department } from '@/api/types'

interface TreeNode { title: string; value: string; children?: TreeNode[] }
interface DeptCache { tree: TreeNode[]; names: Record<string, string>; ts: number }

const cacheByScope = new Map<string, DeptCache>()
const inflightByScope = new Map<string, Promise<DeptCache>>()
const TTL = 5 * 60 * 1000

function build(nodes: Department[], names: Record<string, string>): TreeNode[] {
  return nodes.map((n) => {
    names[n.id] = n.name
    return { title: n.name, value: n.id, children: n.children?.length ? build(n.children, names) : undefined }
  })
}

async function loadTree(scopeCode?: string | null): Promise<DeptCache> {
  const key = scopeCode || '__all__'
  const cached = cacheByScope.get(key)
  if (cached && Date.now() - cached.ts < TTL) return cached
  const pending = inflightByScope.get(key)
  if (pending) return pending
  const params: Record<string, string> = {}
  if (scopeCode) params.scope_code = scopeCode
  const p = client.get<unknown, ApiResponse<Department[]>>('/api/v1/lc/pickable-departments', { params })
    .then((res) => {
      const names: Record<string, string> = {}
      const tree = build((res.data as Department[]) || [], names)
      const entry = { tree, names, ts: Date.now() }
      cacheByScope.set(key, entry)
      return entry
    })
    .catch(() => ({ tree: [], names: {}, ts: Date.now() }))
    .finally(() => { inflightByScope.delete(key) })
  inflightByScope.set(key, p)
  return p
}

/** 列表/导出用：部门 id → 名称 */
export async function getDeptNameMap(): Promise<Record<string, string>> {
  const c = await loadTree()
  return { ...(c.names || {}) }
}

export default function DeptField({
  value, onChange, multi, readonly, placeholder, scopeCode,
}: {
  value: unknown
  onChange?: (v: unknown) => void
  multi?: boolean
  readonly?: boolean
  placeholder?: string
  /** 可选范围编码（department 类型） */
  scopeCode?: string | null
}) {
  const cacheKey = scopeCode || '__all__'
  const [tree, setTree] = useState<TreeNode[]>(cacheByScope.get(cacheKey)?.tree || [])
  const [names, setNames] = useState<Record<string, string>>(cacheByScope.get(cacheKey)?.names || {})
  const [loading, setLoading] = useState(!cacheByScope.get(cacheKey))

  useEffect(() => {
    let alive = true
    setLoading(true)
    loadTree(scopeCode).then((c) => {
      if (alive && c) { setTree(c.tree); setNames(c.names); setLoading(false) }
    })
    return () => { alive = false }
  }, [scopeCode])

  if (readonly) {
    const ids = multi ? (Array.isArray(value) ? value : []) : value ? [value] : []
    if (!ids.length) return <div style={{ paddingTop: 4 }}>—</div>
    return <div style={{ paddingTop: 4 }}>{(ids as string[]).map((id) => names[id] || id).join('，')}</div>
  }

  return (
    <TreeSelect
      style={{ width: '100%' }}
      treeData={tree}
      loading={loading}
      allowClear showSearch treeNodeFilterProp="title"
      multiple={!!multi}
      placeholder={placeholder || '选择部门'}
      value={(value as string | string[]) ?? (multi ? [] : undefined)}
      onChange={(v) => onChange?.(v)}
    />
  )
}
