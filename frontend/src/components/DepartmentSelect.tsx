import { useEffect, useState } from 'react'
import { TreeSelect } from 'antd'
import { departmentApi } from '@/api/department'
import type { Department } from '@/api/types'

interface Props {
  value?: string
  onChange?: (v: string | undefined) => void
  placeholder?: string
  disabled?: boolean
  allowClear?: boolean
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

// Module-level cache so each page mount doesn't refetch the tree
let cached: { data: TreeNode[]; ts: number } | null = null
const TTL_MS = 5 * 60 * 1000

export default function DepartmentSelect({ value, onChange, placeholder = '选择部门', disabled, allowClear = true }: Props) {
  const [treeData, setTreeData] = useState<TreeNode[]>(cached?.data || [])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (cached && Date.now() - cached.ts < TTL_MS) return
    setLoading(true)
    departmentApi.tree()
      .then((res) => {
        const data = toTreeData(res.data || [])
        cached = { data, ts: Date.now() }
        setTreeData(data)
      })
      .catch(() => { /* silently ignore — empty select still renders */ })
      .finally(() => setLoading(false))
  }, [])

  return (
    <TreeSelect
      value={value}
      onChange={(v) => onChange?.(v)}
      treeData={treeData}
      placeholder={placeholder}
      disabled={disabled}
      allowClear={allowClear}
      loading={loading}
      treeDefaultExpandAll
      showSearch
      treeNodeFilterProp="title"
      style={{ width: '100%' }}
    />
  )
}
