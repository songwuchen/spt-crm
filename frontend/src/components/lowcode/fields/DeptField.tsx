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

/** 列表/导出用：部门 id → 名称；可选补查树外 id（历史/范围外）。 */
export async function getDeptNameMap(extraIds?: string[]): Promise<Record<string, string>> {
  const c = await loadTree()
  const names = { ...(c.names || {}) }
  const missing = (extraIds || []).map((x) => String(x || '').trim()).filter((id) => id && !names[id])
  if (!missing.length) return names
  try {
    const res = await client.get<unknown, ApiResponse<Record<string, string>>>('/api/v1/lc/department-labels', {
      params: { ids: missing.join(',') },
    })
    Object.assign(names, res.data || {})
  } catch { /* ignore */ }
  return names
}

/** 兼容 id 字符串 / {id,name} / 数组（冒烟脚本、简道云风格对象值）。 */
function normalizeDeptIds(value: unknown, multi?: boolean): {
  ids: string[]
  nameHints: Record<string, string>
} {
  const nameHints: Record<string, string> = {}
  const one = (v: unknown): string | null => {
    if (v == null || v === '') return null
    // 绝不能 String(array)：会变成 "uuid1,uuid2" 整串，只读态显示成「未知部门(uuid1…)」
    if (Array.isArray(v)) return null
    if (typeof v === 'object') {
      const o = v as Record<string, unknown>
      const id = String(o.id || o.value || '').trim()
      const name = String(o.name || o.title || o.label || '').trim()
      if (id && name) nameHints[id] = name
      return id || null
    }
    const s = String(v).trim()
    return s && s !== '[object Object]' ? s : null
  }
  // 值为数组时始终按多选解析（模板曾把 offices 标成单选 department，但共同场景写入 id 数组）
  if (multi || Array.isArray(value)) {
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
  const [labelsPending, setLabelsPending] = useState(false)

  useEffect(() => {
    let alive = true
    setLoading(true)
    loadTree(scopeCode).then((c) => {
      if (!alive || !c) return
      setTree(c.tree)
      // 合并而非整表替换：避免后到的树覆盖已通过 labels/nameHints 解析的树外 id
      setNames((prev) => ({ ...c.names, ...prev }))
      setLoading(false)
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

  // 树外 id（超出 pickable_scope / 简道云历史 MongoId）：拉名称回显；并合并全量树作兜底
  const missingKey = selectedIds.filter((id) => !names[id]).join('|')
  useEffect(() => {
    if (!missingKey) {
      setLabelsPending(false)
      return
    }
    const missing = missingKey.split('|').filter(Boolean)
    let alive = true
    setLabelsPending(true)
    Promise.all([
      client.get<unknown, ApiResponse<Record<string, string>>>('/api/v1/lc/department-labels', {
        params: { ids: missing.join(',') },
      }).then((res) => res.data || {}).catch(() => ({}) as Record<string, string>),
      // 范围树可能不含已选 id：再并一份全量名称
      scopeCode ? loadTree().then((c) => c.names || {}).catch(() => ({})) : Promise.resolve({} as Record<string, string>),
    ]).then(([labels, allNames]) => {
      if (!alive) return
      setNames((prev) => {
        const next = { ...allNames, ...prev }
        let changed = false
        for (const [k, v] of Object.entries({ ...allNames, ...labels })) {
          if (v && next[k] !== v) { next[k] = v; changed = true }
        }
        return changed ? next : prev
      })
      setLabelsPending(false)
    })
    return () => { alive = false }
  }, [missingKey, scopeCode])

  const treeIdSet = new Set<string>()
  ;(function collect(nodes: TreeNode[]) {
    for (const n of nodes) {
      treeIdSet.add(n.value)
      if (n.children?.length) collect(n.children)
    }
  })(tree)

  const unknownLabel = (id: string) => (
    (loading || labelsPending)
      ? '…'
      : (id.length > 12 ? `未知部门(${id.slice(0, 8)}…)` : `未知部门(${id})`)
  )

  // 树中不存在的历史/外部 id：挂到树顶，标题优先用已解析名称
  const orphanNodes: TreeNode[] = selectedIds
    .filter((id) => !treeIdSet.has(id))
    .map((id) => ({
      title: names[id] || unknownLabel(id),
      value: id,
    }))
  const treeData = orphanNodes.length ? [...orphanNodes, ...tree] : tree

  if (readonly) {
    if (!selectedIds.length) return <div style={{ paddingTop: 4 }}>—</div>
    return (
      <div style={{ paddingTop: 4 }}>
        {selectedIds.map((id) => names[id] || unknownLabel(id)).join('，')}
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
