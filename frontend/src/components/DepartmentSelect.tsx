import { useEffect, useMemo, useState } from 'react'
import { Input, TreeSelect } from 'antd'
import client from '@/api/client'
import type { ApiResponse, Department } from '@/api/types'

interface Props {
  value?: string
  /** 第二个参数为选中节点标题，便于同步写 department_name */
  onChange?: (v: string | undefined, label?: string) => void
  placeholder?: string
  disabled?: boolean
  allowClear?: boolean
  /** 已有部门名称（无 dept:view / 树未加载时用于回显，避免只显示 UUID） */
  labelHint?: string
}

interface TreeNode {
  title: string
  value: string
  children?: TreeNode[]
}

function toTreeData(nodes: Department[]): TreeNode[] {
  return nodes.map((n) => ({
    title: n.name,
    value: n.id,
    children: n.children && n.children.length > 0 ? toTreeData(n.children) : undefined,
  }))
}

function findTitle(nodes: TreeNode[], id: string): string | undefined {
  for (const n of nodes) {
    if (n.value === id) return n.title
    if (n.children?.length) {
      const hit = findTitle(n.children, id)
      if (hit) return hit
    }
  }
  return undefined
}

// Module-level cache so each page mount doesn't refetch the tree
let cached: { data: TreeNode[]; ts: number } | null = null
const TTL_MS = 5 * 60 * 1000

async function fetchDeptTree(): Promise<TreeNode[]> {
  if (cached && Date.now() - cached.ts < TTL_MS) return cached.data
  const res = await client.get<unknown, ApiResponse<Department[]>>(
    '/api/admin/v1/tenant/departments/tree',
    { headers: { 'X-Silent-Error': '1' } },
  )
  const data = toTreeData(res.data || [])
  cached = { data, ts: Date.now() }
  return data
}

export default function DepartmentSelect({
  value, onChange, placeholder = '选择部门', disabled, allowClear = true, labelHint,
}: Props) {
  const [treeData, setTreeData] = useState<TreeNode[]>(cached?.data || [])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // 只读不拉树，避免无 dept:view 时全局 toast「缺少权限」
    if (disabled) return
    let cancelled = false
    setLoading(true)
    fetchDeptTree()
      .then((data) => { if (!cancelled) setTreeData(data) })
      .catch(() => { /* 无权限等：静默，靠 labelHint 回显 */ })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [disabled])

  const displayName = (labelHint || '').trim() || (value ? findTitle(treeData, value) : undefined) || ''

  // 禁用：纯文本展示名称，绝不请求部门树
  if (disabled) {
    return <Input disabled value={displayName || '—'} />
  }

  const mergedTree = useMemo(() => {
    if (!value) return treeData
    if (findTitle(treeData, value)) return treeData
    const title = (labelHint || '').trim()
    if (!title) return treeData
    return [{ title, value }, ...treeData]
  }, [treeData, value, labelHint])

  return (
    <TreeSelect
      value={value}
      onChange={(v) => {
        const id = (v as string | undefined) || undefined
        onChange?.(id, id ? (findTitle(mergedTree, id) || labelHint) : undefined)
      }}
      treeData={mergedTree}
      placeholder={placeholder}
      allowClear={allowClear}
      loading={loading}
      treeDefaultExpandAll
      showSearch
      treeNodeFilterProp="title"
      style={{ width: '100%' }}
    />
  )
}
