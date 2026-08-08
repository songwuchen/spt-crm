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

/** 兼容 id 字符串 / {id,name} / 数组（冒烟脚本、简道云风格对象值）。 */
function normalizeDeptIds(value: unknown, multi?: boolean): {
  ids: string[]
  nameHints: Record<string, string>
} {
  const nameHints: Record<string, string> = {}
  const one = (v: unknown): string | null => {
    if (v == null || v === '') return null
    if (typeof v === 'object' && !Array.isArray(v)) {
      const o = v as Record<string, unknown>
      const id = String(o.id || o.value || '').trim()
      const name = String(o.name || o.title || o.label || '').trim()
      if (id && name) nameHints[id] = name
      return id || null
    }
    const s = String(v).trim()
    return s && s !== '[object Object]' ? s : null
  }
  if (multi) {
    const list = Array.isArray(value) ? value : (value != null && value !== '' ? [value] : [])
    return { ids: list.map(one).filter((x): x is string => !!x), nameHints }
  }
  const id = one(value)
  return { ids: id ? [id] : [], nameHints }
}

export default function DeptField({
  value, onChange, multi, readonly, placeholder, scopeCode,
}: {
  /** Form.Item 会注入；单独使用时可省略 */
  value?: unknown
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

  const { ids: selectedIds, nameHints } = normalizeDeptIds(value, multi)
  // 对象值里自带的 name 先并入，避免只读态闪「未知部门([object Object])」
  useEffect(() => {
    if (!Object.keys(nameHints).length) return
    setNames((prev) => {
      let changed = false
      const next = { ...prev }
      for (const [k, v] of Object.entries(nameHints)) {
        if (v && next[k] !== v) { next[k] = v; changed = true }
      }
      return changed ? next : prev
    })
  }, [JSON.stringify(nameHints)])

  // 树外 id（常为简道云历史部门 MongoId）：拉名称回显，避免「未知部门(56ca…)」
  useEffect(() => {
    const missing = selectedIds.filter((id) => !names[id])
    if (!missing.length) return
    let alive = true
    client.get<unknown, ApiResponse<Record<string, string>>>('/api/v1/lc/department-labels', {
      params: { ids: missing.join(',') },
    }).then((res) => {
      if (!alive || !res.data) return
      setNames((prev) => {
        const next = { ...prev }
        let changed = false
        for (const [k, v] of Object.entries(res.data || {})) {
          if (v && next[k] !== v) { next[k] = v; changed = true }
        }
        return changed ? next : prev
      })
    }).catch(() => { /* ignore */ })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIds.join('|')])

  const treeIdSet = new Set<string>()
  ;(function collect(nodes: TreeNode[]) {
    for (const n of nodes) {
      treeIdSet.add(n.value)
      if (n.children?.length) collect(n.children)
    }
  })(tree)

  // 树中不存在的历史/外部 id：挂到树顶，标题优先用已解析名称
  const orphanNodes: TreeNode[] = selectedIds
    .filter((id) => !treeIdSet.has(id))
    .map((id) => ({
      title: names[id] || (id.length > 12 ? `未知部门(${id.slice(0, 8)}…)` : `未知部门(${id})`),
      value: id,
    }))
  const treeData = orphanNodes.length ? [...orphanNodes, ...tree] : tree

  if (readonly) {
    if (!selectedIds.length) return <div style={{ paddingTop: 4 }}>—</div>
    return (
      <div style={{ paddingTop: 4 }}>
        {selectedIds.map((id) => names[id] || (id.length > 12 ? `未知部门(${id.slice(0, 8)}…)` : id)).join('，')}
      </div>
    )
  }

  return (
    <TreeSelect
      style={{ width: '100%' }}
      treeData={treeData}
      loading={loading}
      allowClear showSearch treeNodeFilterProp="title"
      multiple={!!multi}
      placeholder={placeholder || '选择部门'}
      value={multi ? selectedIds : (selectedIds[0] ?? undefined)}
      onChange={(v) => onChange?.(v)}
    />
  )
}
