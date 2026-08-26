import { useEffect, useMemo, useState } from 'react'
import { Input, TreeSelect } from 'antd'
import client from '@/api/client'
import type { ApiResponse, Department } from '@/api/types'

const EMPTY_DEPT_VALUE = '__empty__'

interface DeptSelectBase {
  placeholder?: string
  disabled?: boolean
  allowClear?: boolean
  labelHint?: string
}

interface DeptSelectSingleProps extends DeptSelectBase {
  multiple?: false
  allowEmptyOption?: boolean
  value?: string
  onChange?: (v: string | undefined, label?: string) => void
}

interface DeptSelectMultiProps extends DeptSelectBase {
  multiple: true
  allowEmptyOption?: boolean
  value?: string[]
  onChange?: (v: string[] | undefined, label?: string[]) => void
}

type Props = DeptSelectSingleProps | DeptSelectMultiProps

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

export default function DepartmentSelect(props: Props) {
  const {
    placeholder = '选择部门', disabled, allowClear = true, labelHint,
  } = props
  const multiple = props.multiple === true
  const allowEmptyOption = props.allowEmptyOption === true
  const value = props.value
  const onChange = props.onChange
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

  const singleValue = multiple ? undefined : (value as string | undefined)
  const multiValue = multiple
    ? (Array.isArray(value) ? value : (value ? [String(value)] : []))
    : undefined

  const displayName = (labelHint || '').trim()
    || (singleValue ? findTitle(treeData, singleValue) : undefined)
    || ''

  // 禁用：纯文本展示名称，绝不请求部门树
  if (disabled) {
    if (multiple && Array.isArray(value) && value.length) {
      const names = value.map((id) => {
        if (id === EMPTY_DEPT_VALUE) return '未填写'
        return findTitle(treeData, id) || id
      })
      return <Input disabled value={names.join('，') || '—'} />
    }
    return <Input disabled value={displayName || '—'} />
  }

  const mergedTree = useMemo(() => {
    let nodes = treeData
    if (allowEmptyOption) {
      nodes = [{ title: '未填写', value: EMPTY_DEPT_VALUE }, ...nodes]
    }
    if (multiple) return nodes
    if (!singleValue) return nodes
    if (findTitle(nodes, singleValue)) return nodes
    const title = (labelHint || '').trim()
    if (!title) return nodes
    return [{ title, value: singleValue }, ...nodes]
  }, [treeData, singleValue, labelHint, multiple, allowEmptyOption])

  return (
    <TreeSelect
      value={multiple ? multiValue : singleValue}
      multiple={multiple}
      treeCheckable={multiple}
      maxTagCount={multiple ? 'responsive' : undefined}
      onChange={(v) => {
        if (multiple) {
          const ids = (Array.isArray(v) ? v : (v ? [String(v)] : [])).map(String)
          const labels = ids.map((id) => {
            if (id === EMPTY_DEPT_VALUE) return '未填写'
            return findTitle(mergedTree, id) || id
          })
          ;(onChange as DeptSelectMultiProps['onChange'])?.(ids.length ? ids : undefined, labels)
          return
        }
        const id = (v as string | undefined) || undefined
        ;(onChange as DeptSelectSingleProps['onChange'])?.(
          id, id ? (findTitle(mergedTree, id) || labelHint) : undefined,
        )
      }}
      treeData={mergedTree}
      placeholder={placeholder}
      allowClear={allowClear}
      loading={loading}
      treeDefaultExpandAll
      showSearch
      treeNodeFilterProp="title"
      variant="borderless"
      style={{ width: '100%' }}
    />
  )
}
