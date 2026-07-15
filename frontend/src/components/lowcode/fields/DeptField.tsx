// 部门选择字段(department / department_multi)。值为部门 id(单)或 id 数组(多)。
import { useEffect, useState } from 'react'
import { TreeSelect } from 'antd'
import { departmentApi } from '@/api/department'
import type { Department } from '@/api/types'

interface TreeNode { title: string; value: string; children?: TreeNode[] }
interface DeptCache { tree: TreeNode[]; names: Record<string, string>; ts: number }

let cache: DeptCache | null = null
const TTL = 5 * 60 * 1000
let inflight: Promise<DeptCache> | null = null

function build(nodes: Department[], names: Record<string, string>): TreeNode[] {
  return nodes.map((n) => {
    names[n.id] = n.name
    return { title: n.name, value: n.id, children: n.children?.length ? build(n.children, names) : undefined }
  })
}

async function loadTree(): Promise<DeptCache> {
  if (cache && Date.now() - cache.ts < TTL) return cache
  if (inflight) return inflight
  inflight = departmentApi.tree().then((res) => {
    const names: Record<string, string> = {}
    const tree = build((res.data as Department[]) || [], names)
    cache = { tree, names, ts: Date.now() }
    inflight = null
    return cache
  }).catch(() => { inflight = null; return { tree: [], names: {}, ts: Date.now() } })
  return inflight
}

export default function DeptField({
  value, onChange, multi, readonly, placeholder,
}: {
  value: unknown
  onChange: (v: unknown) => void
  multi?: boolean
  readonly?: boolean
  placeholder?: string
}) {
  const [tree, setTree] = useState<TreeNode[]>(cache?.tree || [])
  const [names, setNames] = useState<Record<string, string>>(cache?.names || {})
  const [loading, setLoading] = useState(!cache)

  useEffect(() => {
    let alive = true
    loadTree().then((c) => { if (alive && c) { setTree(c.tree); setNames(c.names); setLoading(false) } })
    return () => { alive = false }
  }, [])

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
      onChange={(v) => onChange(v)}
    />
  )
}
