import { useState, useEffect, useMemo } from 'react'
import { Tree, Button, Modal, Form, Input, InputNumber, message, Table, Switch, Select, TreeSelect, Tag, Popconfirm, Tooltip, Empty } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { departmentApi, deptRoleRuleApi } from '@/api/department'
import type { DeptRoleRule } from '@/api/department'
import { roleApi } from '@/api/user'
import type { Department, Role } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'

// 命中的关键词高亮显示，便于在大组织树里一眼定位。
// 用 localeCompare 逐位比对而不是在 toLowerCase() 后的串上取下标——'İ'.toLowerCase()
// 长度会变，拿小写串的下标去切原串会整体错位。
function matchIndex(name: string, kw: string): number {
  for (let i = 0; i + kw.length <= name.length; i++) {
    if (name.slice(i, i + kw.length).toLowerCase() === kw) return i
  }
  return -1
}

function highlight(name: string, kw: string) {
  if (!kw) return name
  const idx = matchIndex(name, kw)
  if (idx < 0) return name
  return (
    <>
      {name.slice(0, idx)}
      <span className="bg-amber-200/70 text-amber-900 rounded px-0.5">{name.slice(idx, idx + kw.length)}</span>
      {name.slice(idx + kw.length)}
    </>
  )
}

function toTreeData(departments: Department[], kw = ''): any[] {
  return departments.map((d) => ({
    key: d.id,
    title: (
      <span className="text-sm font-medium text-slate-700">{highlight(d.name, kw)}</span>
    ),
    data: d,
    children: d.children?.length ? toTreeData(d.children, kw) : [],
  }))
}

// 保留命中节点及其祖先链；节点自身命中时整棵子树都保留，方便继续往下点。
function filterDeptTree(departments: Department[], kw: string): Department[] {
  const result: Department[] = []
  for (const d of departments) {
    const selfMatch = d.name.toLowerCase().includes(kw)
    const matchedChildren = d.children?.length ? filterDeptTree(d.children, kw) : []
    if (selfMatch) {
      result.push(d)
    } else if (matchedChildren.length > 0) {
      result.push({ ...d, children: matchedChildren })
    }
  }
  return result
}

function collectKeys(departments: Department[]): string[] {
  return departments.flatMap((d) => [d.id, ...(d.children?.length ? collectKeys(d.children) : [])])
}

export default function DepartmentPage() {
  usePageTitle('部门管理')
  const [tree, setTree] = useState<Department[]>([])
  const [modal, setModal] = useState(false)
  const [editing, setEditing] = useState<Department | null>(null)
  const [parentId, setParentId] = useState<string | undefined>()
  const [selectedDept, setSelectedDept] = useState<Department | null>(null)
  const [search, setSearch] = useState('')
  const [expandedKeys, setExpandedKeys] = useState<React.Key[]>([])
  const [form] = Form.useForm()

  const fetchTree = async () => {
    const res = await departmentApi.tree()
    setTree(res.data)
  }

  const kw = search.trim().toLowerCase()
  const shownTree = useMemo(() => (kw ? filterDeptTree(tree, kw) : tree), [tree, kw])

  // 当前可见的树一变（首次加载、搜索词变化）就整体展开，
  // 否则命中的子部门还藏在折叠的父节点里。只依赖 shownTree，避免和上面的过滤重复计算。
  useEffect(() => { setExpandedKeys(collectKeys(shownTree)) }, [shownTree])

  useEffect(() => { fetchTree() }, [])

  const openCreate = (pId?: string) => {
    setEditing(null)
    setParentId(pId)
    form.resetFields()
    setModal(true)
  }

  const openEdit = (dept: Department) => {
    setEditing(dept)
    setParentId(dept.parent_id || undefined)
    form.setFieldsValue({ name: dept.name, sort_order: dept.sort_order })
    setModal(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    if (editing) {
      await departmentApi.update(editing.id, values)
      message.success('部门已更新')
    } else {
      await departmentApi.create({ ...values, parent_id: parentId })
      message.success('部门已创建')
    }
    setModal(false)
    fetchTree()
  }

  const handleDelete = (dept: Department) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除部门「${dept.name}」？`,
      okType: 'danger',
      onOk: async () => {
        await departmentApi.delete(dept.id)
        message.success('部门已删除')
        setSelectedDept(null)
        fetchTree()
      },
    })
  }

  const countNodes = (depts: Department[]): number =>
    depts.reduce((acc, d) => acc + 1 + (d.children ? countNodes(d.children) : 0), 0)

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">部门管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理组织架构和部门层级</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />}
          onClick={() => openCreate()}
          className="shadow-lg shadow-primary/20 font-bold">
          新建顶级部门
        </Button>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Department Tree */}
        <div className="col-span-5">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">account_tree</span>
                <h3 className="text-sm font-bold text-slate-900">组织架构</h3>
              </div>
              <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-sm font-bold">
                {kw ? `${countNodes(shownTree)} / ${countNodes(tree)}` : countNodes(tree)} 个部门
              </span>
            </div>
            <div className="px-4 pt-4">
              <Input
                placeholder="搜索部门名称..."
                prefix={<SearchOutlined className="text-slate-400" />}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                allowClear
                style={{ background: '#f1f5f9', borderColor: 'transparent' }}
                className="rounded-lg"
              />
            </div>
            <div className="p-4">
              {tree.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <span className="material-symbols-outlined text-4xl text-slate-200 mb-3">account_tree</span>
                  <p className="text-sm text-slate-400">暂无部门数据</p>
                  <p className="text-sm text-slate-300 mt-1">点击上方按钮创建第一个部门</p>
                </div>
              ) : shownTree.length === 0 ? (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`没有匹配「${search}」的部门`} />
              ) : (
                <Tree
                  treeData={toTreeData(shownTree, kw)}
                  expandedKeys={expandedKeys}
                  onExpand={setExpandedKeys}
                  showIcon
                  blockNode
                  onSelect={(_, info) => {
                    setSelectedDept((info.node as any).data)
                  }}
                  selectedKeys={selectedDept ? [selectedDept.id] : []}
                  className="[&_.ant-tree-node-content-wrapper]:rounded-lg [&_.ant-tree-node-selected]:!bg-primary/5"
                />
              )}
            </div>
          </div>
        </div>

        {/* Department Detail */}
        <div className="col-span-7">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-2">
              <span className="material-symbols-outlined text-slate-400">info</span>
              <h3 className="text-sm font-bold text-slate-900">
                {selectedDept ? selectedDept.name : '部门详情'}
              </h3>
            </div>

            {selectedDept ? (
              <div className="p-5">
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                    <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">部门名称</div>
                    <div className="text-sm font-semibold text-slate-700">{selectedDept.name}</div>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                    <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">排序权重</div>
                    <div className="text-sm font-semibold text-slate-700">{selectedDept.sort_order}</div>
                  </div>
                  <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 col-span-2">
                    <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">物化路径</div>
                    <div className="text-sm font-mono text-slate-500">{selectedDept.path}</div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <Button onClick={() => openCreate(selectedDept.id)}>
                    <span className="material-symbols-outlined text-sm mr-1">add</span>
                    添加子部门
                  </Button>
                  <Button onClick={() => openEdit(selectedDept)}>
                    <span className="material-symbols-outlined text-sm mr-1">edit</span>
                    编辑
                  </Button>
                  <Button danger onClick={() => handleDelete(selectedDept)}>
                    <span className="material-symbols-outlined text-sm mr-1">delete</span>
                    删除
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <span className="material-symbols-outlined text-5xl text-slate-200 mb-3">touch_app</span>
                <p className="text-sm text-slate-400">请从左侧选择部门</p>
                <p className="text-sm text-slate-300 mt-1">选择部门后可查看详情和管理操作</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 部门 → 角色 自动分配规则 */}
      <div className="mt-6">
        <DeptRoleRulesSection tree={tree} />
      </div>

      <Modal title={editing ? '编辑部门' : '新建部门'} open={modal} onOk={handleSubmit} onCancel={() => setModal(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="部门名称" rules={[{ required: true }]}>
            <Input placeholder="请输入部门名称" />
          </Form.Item>
          <Form.Item name="sort_order" label="排序权重" initialValue={0}>
            <InputNumber min={0} className="w-full" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

// 把部门树转成 AntD TreeSelect 数据
function toTreeSelectData(departments: Department[]): any[] {
  return departments.map((d) => ({
    value: d.id,
    title: d.name,
    children: d.children?.length ? toTreeSelectData(d.children) : undefined,
  }))
}

function DeptRoleRulesSection({ tree }: { tree: Department[] }) {
  const { hasPermission } = usePermission()
  // 规则的读/写分别需要 role:view / role:manage；本页路由仅由 dept:view 守卫，
  // 因此在组件内自行按权限渲染，避免无 role 权限的用户触发 403。
  const canView = hasPermission('role:view')
  const canManage = hasPermission('role:manage')

  const [rules, setRules] = useState<DeptRoleRule[]>([])
  const [roles, setRoles] = useState<Role[]>([])
  const [loading, setLoading] = useState(false)
  const [applying, setApplying] = useState(false)
  const [modal, setModal] = useState(false)
  const [ruleSearch, setRuleSearch] = useState('')
  const [form] = Form.useForm()

  const fetchRules = async () => {
    setLoading(true)
    try {
      const res = await deptRoleRuleApi.list()
      setRules(res.data)
    } catch (e: any) {
      message.error(e?.response?.data?.message || '加载规则失败')
    } finally {
      setLoading(false)
    }
  }

  const fetchRoles = async () => {
    try {
      const res = await roleApi.list()
      setRoles(res.data)
    } catch (e: any) {
      message.error(e?.response?.data?.message || '加载角色失败')
    }
  }

  useEffect(() => {
    if (!canView) return
    fetchRules()
    if (canManage) fetchRoles()
  }, [canView, canManage])

  // 无 role:view 权限则不渲染本区块（其接口需要 role:view/role:manage）
  if (!canView) return null

  const openCreate = () => {
    form.resetFields()
    form.setFieldsValue({ include_children: true, enabled: true })
    setModal(true)
  }

  const handleCreate = async () => {
    const values = await form.validateFields()
    try {
      await deptRoleRuleApi.create(values)
      message.success('规则已新增')
      setModal(false)
      fetchRules()
    } catch (e: any) {
      message.error(e?.response?.data?.message || '新增失败')
    }
  }

  const toggle = async (rule: DeptRoleRule, field: 'include_children' | 'enabled', val: boolean) => {
    try {
      await deptRoleRuleApi.update(rule.id, { [field]: val })
      setRules((prev) => prev.map((r) => (r.id === rule.id ? { ...r, [field]: val } : r)))
    } catch (e: any) {
      message.error(e?.response?.data?.message || '更新失败')
    }
  }

  const handleDelete = async (rule: DeptRoleRule) => {
    try {
      await deptRoleRuleApi.delete(rule.id)
      message.success('规则已删除')
      fetchRules()
    } catch (e: any) {
      message.error(e?.response?.data?.message || '删除失败')
    }
  }

  const handleApplyAll = async () => {
    setApplying(true)
    try {
      const res = await deptRoleRuleApi.applyAll()
      message.success(`已应用：${res.data.users_touched} 名用户新增 ${res.data.roles_added} 个角色`)
    } catch (e: any) {
      message.error(e?.response?.data?.message || '应用失败')
    } finally {
      setApplying(false)
    }
  }

  // 规则条数不多，前端过滤即可（本区块在 canView 早退之后，不能用 hook）
  const rk = ruleSearch.trim().toLowerCase()
  const filteredRules = rk
    ? rules.filter((r) => [r.department_name, r.department_path, r.role_name, r.role_code]
        .some((v) => (v || '').toLowerCase().includes(rk)))
    : rules

  const columns = [
    {
      title: '部门',
      dataIndex: 'department_name',
      render: (_: any, r: DeptRoleRule) => (
        <div>
          <div className="text-sm font-medium text-slate-700">{r.department_name || '(已删除)'}</div>
          {r.department_path && <div className="text-[12px] font-mono text-slate-400">{r.department_path}</div>}
        </div>
      ),
    },
    {
      title: '自动角色',
      dataIndex: 'role_name',
      render: (_: any, r: DeptRoleRule) => (
        <span>
          {r.role_name || '(已删除)'}{' '}
          {r.role_code && <Tag color="blue" className="ml-1">{r.role_code}</Tag>}
        </span>
      ),
    },
    {
      title: (
        <Tooltip title="开启后，该部门的所有子部门成员也会命中此规则">
          <span>含子部门</span>
        </Tooltip>
      ),
      dataIndex: 'include_children',
      width: 110,
      render: (_: any, r: DeptRoleRule) => (
        <Switch size="small" disabled={!canManage} checked={r.include_children} onChange={(v) => toggle(r, 'include_children', v)} />
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 90,
      render: (_: any, r: DeptRoleRule) => (
        <Switch size="small" disabled={!canManage} checked={r.enabled} onChange={(v) => toggle(r, 'enabled', v)} />
      ),
    },
    ...(canManage ? [{
      title: '操作',
      width: 90,
      render: (_: any, r: DeptRoleRule) => (
        <Popconfirm title="确定删除此规则？" onConfirm={() => handleDelete(r)} okText="删除" okButtonProps={{ danger: true }}>
          <Button type="link" danger size="small">删除</Button>
        </Popconfirm>
      ),
    }] : []),
  ]

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-primary">rule</span>
          <div>
            <h3 className="text-sm font-bold text-slate-900">部门自动角色规则</h3>
            <p className="text-[12px] text-slate-400 mt-0.5">新建用户、修改部门或钉钉同步时，命中部门的成员会自动补上对应角色（仅新增、不删除已有角色）</p>
          </div>
        </div>
        {canManage && (
          <div className="flex items-center gap-2">
            <Popconfirm
              title="立即应用到存量用户？"
              description="将按现有规则为所有已存在的用户补角色（仅新增，不删除）。"
              onConfirm={handleApplyAll}
              okText="应用"
            >
              <Button loading={applying}>
                <span className="material-symbols-outlined text-sm mr-1">bolt</span>
                立即应用到存量用户
              </Button>
            </Popconfirm>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增规则</Button>
          </div>
        )}
      </div>
      <div className="p-4">
        <Input
          placeholder="搜索部门 / 角色..."
          prefix={<SearchOutlined className="text-slate-400" />}
          value={ruleSearch}
          onChange={(e) => setRuleSearch(e.target.value)}
          allowClear
          style={{ width: 260, background: '#f1f5f9', borderColor: 'transparent' }}
          className="rounded-lg mb-3"
        />
        <Table
          rowKey="id"
          size="small"
          loading={loading}
          dataSource={filteredRules}
          columns={columns as any}
          pagination={false}
          locale={{ emptyText: ruleSearch ? `没有匹配「${ruleSearch}」的规则` : '暂无规则，点击「新增规则」添加' }}
        />
      </div>

      <Modal title="新增部门角色规则" open={modal} onOk={handleCreate} onCancel={() => setModal(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="department_id" label="部门" rules={[{ required: true, message: '请选择部门' }]}>
            <TreeSelect
              treeData={toTreeSelectData(tree)}
              placeholder="选择部门"
              treeDefaultExpandAll
              showSearch
              treeNodeFilterProp="title"
              className="w-full"
            />
          </Form.Item>
          <Form.Item name="role_id" label="自动分配角色" rules={[{ required: true, message: '请选择角色' }]}>
            <Select
              placeholder="选择角色"
              showSearch
              optionFilterProp="label"
              options={roles.map((r) => ({ value: r.id, label: `${r.name} (${r.code})` }))}
            />
          </Form.Item>
          <Form.Item name="include_children" label="含子部门" valuePropName="checked" tooltip="开启后子部门成员也命中">
            <Switch />
          </Form.Item>
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
