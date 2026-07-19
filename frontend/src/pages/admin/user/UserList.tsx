import { useState, useEffect, useRef, useMemo } from 'react'
import { Table, Button, Modal, Form, Input, Select, TreeSelect, Space, message, Switch, Popconfirm, Upload, Alert, Radio, Checkbox } from 'antd'
import { PlusOutlined, SearchOutlined, UploadOutlined, DownloadOutlined, DeleteOutlined } from '@ant-design/icons'
import { userApi, roleApi } from '@/api/user'
import { departmentApi } from '@/api/department'
import type { Role, Department } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePageSize } from '@/hooks/usePageSize'

import Icon from '@/components/Icon'
interface UserItem {
  id: string; username: string; real_name: string
  phone?: string; email?: string; is_active: boolean
  roles: string[]; departments: string[]
}

function flattenDeptTree(depts: Department[]): { id: string; name: string }[] {
  const result: { id: string; name: string }[] = []
  function walk(list: Department[]) {
    for (const d of list) {
      result.push({ id: d.id, name: d.name })
      if (d.children) walk(d.children)
    }
  }
  walk(depts)
  return result
}

interface TreeNode { title: string; value: string; children?: TreeNode[] }

function toTreeData(depts: Department[]): TreeNode[] {
  return depts.map((d) => ({
    title: d.name,
    value: d.id,
    children: d.children?.length ? toTreeData(d.children) : undefined,
  }))
}

export default function UserList() {
  usePageTitle('用户管理')
  const [data, setData] = useState<UserItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterRoleId, setFilterRoleId] = useState<string | undefined>()
  const [filterDeptId, setFilterDeptId] = useState<string | undefined>()
  const [filterActive, setFilterActive] = useState<boolean | undefined>()
  const [pageSize, setPageSize] = usePageSize('users')
  const [roles, setRoles] = useState<Role[]>([])
  const [deptTree, setDeptTree] = useState<Department[]>([])
  const [deptFlat, setDeptFlat] = useState<{ id: string; name: string }[]>([])
  const [modal, setModal] = useState(false)
  const [editingUser, setEditingUser] = useState<UserItem | null>(null)
  const [form] = Form.useForm()
  // 部门树加载后就不再变，按引用缓存，避免每次输入关键字都递归重建整棵树
  const deptTreeData = useMemo(() => toTreeData(deptTree), [deptTree])

  // Import state
  const [importModal, setImportModal] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ success: number; failed: { row: number; reason: string }[]; total: number } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Reset password state
  const [resetModal, setResetModal] = useState(false)
  const [resetTarget, setResetTarget] = useState<UserItem | null>(null)
  const [resetForm] = Form.useForm()
  const [resetting, setResetting] = useState(false)

  // 批量改角色
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [bulkModal, setBulkModal] = useState(false)
  const [bulkRoleIds, setBulkRoleIds] = useState<string[]>([])
  const [bulkMode, setBulkMode] = useState<'replace' | 'add'>('replace')
  const [bulkSaving, setBulkSaving] = useState(false)

  const doBulkRoles = async () => {
    setBulkSaving(true)
    try {
      const res = await userApi.bulkRoles({ user_ids: selectedRowKeys as string[], role_ids: bulkRoleIds, mode: bulkMode })
      message.success(`已更新 ${res.data.updated} 个用户的角色`)
      setBulkModal(false); setBulkRoleIds([]); setSelectedRowKeys([])
      fetchData()
    } catch {
      message.error('批量更新失败')
    } finally {
      setBulkSaving(false)
    }
  }

  // 当前筛选条件。overrides 用于 Select 的 onChange —— 那一刻 state 还没更新，
  // 必须把新值直接传进来，否则会用上一次的旧值发请求。
  const buildFilters = (overrides: Record<string, unknown> = {}) => ({
    keyword: keyword || undefined,
    role_id: filterRoleId,
    dept_id: filterDeptId,
    is_active: filterActive,
    ...overrides,
  })

  // size 需显式传入：切换「每页条数」时 setPageSize 尚未生效，读 state 会拿到旧值，
  // 导致分页器显示 50/页、实际却按 20 条请求。
  const fetchData = async (page = pageNo, overrides: Record<string, unknown> = {}, size = pageSize) => {
    setLoading(true)
    try {
      const res = await userApi.list({ pageNo: page, pageSize: size, ...buildFilters(overrides) })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally { setLoading(false) }
  }

  const fetchRoles = async () => {
    const res = await roleApi.list()
    setRoles(res.data)
  }

  const fetchDepts = async () => {
    const res = await departmentApi.tree()
    setDeptTree(res.data)
    setDeptFlat(flattenDeptTree(res.data))
  }

  useEffect(() => { fetchData(); fetchRoles(); fetchDepts() }, [])

  const doSearch = () => { setPageNo(1); fetchData(1) }

  const resetFilters = () => {
    setKeyword(''); setFilterRoleId(undefined); setFilterDeptId(undefined); setFilterActive(undefined)
    setPageNo(1)
    fetchData(1, { keyword: undefined, role_id: undefined, dept_id: undefined, is_active: undefined })
  }

  const activeFilterCount = [keyword, filterRoleId, filterDeptId, filterActive].filter(
    (v) => v !== undefined && v !== '',
  ).length

  const handleSubmit = async () => {
    const values = await form.validateFields()
    if (editingUser) {
      await userApi.update(editingUser.id, values)
      message.success('用户已更新')
    } else {
      await userApi.create(values)
      message.success('用户已创建')
    }
    setModal(false); form.resetFields(); setEditingUser(null)
    fetchData()
  }

  const handleDelete = async (userId: string) => {
    await userApi.delete(userId)
    message.success('用户已删除')
    fetchData()
  }

  const handleExport = async () => {
    try {
      const res = await userApi.exportCsv(buildFilters()) as unknown as Blob
      const url = URL.createObjectURL(res)
      const a = document.createElement('a')
      a.href = url
      a.download = 'users.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      message.error('导出失败')
    }
  }

  const handleImport = async () => {
    if (!importFile) { message.warning('请选择CSV文件'); return }
    setImporting(true)
    setImportResult(null)
    try {
      const res = await userApi.importCsv(importFile)
      setImportResult(res.data)
      if (res.data.failed.length === 0) {
        message.success(`成功导入 ${res.data.success} 个用户`)
        setImportModal(false)
        setImportFile(null)
        fetchData()
      }
    } catch {
      message.error('导入失败')
    } finally {
      setImporting(false)
    }
  }

  const openImportModal = () => {
    setImportFile(null)
    setImportResult(null)
    setImportModal(true)
  }

  const openResetPassword = (user: UserItem) => {
    setResetTarget(user)
    resetForm.resetFields()
    setResetModal(true)
  }

  const handleResetPassword = async () => {
    if (!resetTarget) return
    const values = await resetForm.validateFields()
    setResetting(true)
    try {
      await userApi.resetPassword(resetTarget.id, values.new_password, !!values.require_change)
      message.success(`已重置 ${resetTarget.real_name || resetTarget.username} 的密码`)
      setResetModal(false)
      setResetTarget(null)
      resetForm.resetFields()
    } finally {
      setResetting(false)
    }
  }

  const columns = [
    { title: '用户', key: 'user', width: 200,
      render: (_: unknown, record: UserItem) => (
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-sm font-bold text-primary shrink-0">
            {(record.real_name || record.username).slice(0, 2)}
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900">{record.real_name || record.username}</div>
            <div className="text-[13px] text-slate-400">{record.username}</div>
          </div>
        </div>
      ),
    },
    { title: '手机', dataIndex: 'phone', width: 130, responsive: ['lg'] as any,
      render: (v: string) => v || <span className="text-slate-300">-</span>,
    },
    { title: '邮箱', dataIndex: 'email', width: 180, responsive: ['xl'] as any,
      render: (v: string) => v || <span className="text-slate-300">-</span>,
    },
    { title: '角色', dataIndex: 'roles', width: 160,
      render: (v: string[]) => v.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {v.map((r) => (
            <span key={r} className="inline-flex px-2 py-0.5 rounded text-[12px] font-bold bg-primary/10 text-primary border border-primary/20">
              {r}
            </span>
          ))}
        </div>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '部门', dataIndex: 'departments', width: 160, responsive: ['lg'] as any,
      render: (v: string[]) => v.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {v.map((d) => (
            <span key={d} className="inline-flex px-2 py-0.5 rounded text-[12px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
              {d}
            </span>
          ))}
        </div>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '状态', dataIndex: 'is_active', width: 80,
      render: (v: boolean) => (
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${v ? 'bg-emerald-500' : 'bg-slate-300'}`} />
          <span className="text-sm font-medium text-slate-600">{v ? '启用' : '停用'}</span>
        </div>
      ),
    },
    { title: '', width: 180,
      render: (_: unknown, record: UserItem) => (
        <Space size={8}>
          <a className="text-primary text-sm font-bold uppercase tracking-widest" onClick={() => {
            setEditingUser(record)
            form.setFieldsValue({
              real_name: record.real_name, phone: record.phone, email: record.email,
              is_active: record.is_active,
              role_ids: roles.filter((r) => record.roles.includes(r.code)).map((r) => r.id),
              department_ids: deptFlat.filter((d) => record.departments.includes(d.name)).map((d) => d.id),
            })
            setModal(true)
          }}>编辑</a>
          <a className="text-amber-600 text-sm font-bold uppercase tracking-widest" onClick={() => openResetPassword(record)}>
            重置密码
          </a>
          <Popconfirm
            title="确认删除该用户？"
            description="删除后不可恢复"
            okText="删除"
            okButtonProps={{ danger: true }}
            cancelText="取消"
            onConfirm={() => handleDelete(record.id)}
          >
            <a className="text-red-500 text-sm font-bold uppercase tracking-widest">删除</a>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">用户管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理系统用户账号和权限</p>
        </div>
        <Space>
          {selectedRowKeys.length > 0 && (
            <Button type="primary" ghost onClick={() => { setBulkRoleIds([]); setBulkMode('replace'); setBulkModal(true) }}>
              批量改角色 ({selectedRowKeys.length})
            </Button>
          )}
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>
          <Button icon={<UploadOutlined />} onClick={openImportModal}>批量导入</Button>
          <Button type="primary" icon={<PlusOutlined />}
            onClick={() => { setEditingUser(null); form.resetFields(); setModal(true) }}
            className="shadow-lg shadow-primary/20 font-bold">
            新建用户
          </Button>
        </Space>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 items-center flex-wrap">
          <Input
            placeholder="搜索用户名/姓名/手机/邮箱..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            onClear={() => { setPageNo(1); fetchData(1, { keyword: undefined }) }}
            style={{ width: 240, background: '#f1f5f9', borderColor: 'transparent' }}
            className="rounded-lg"
          />
          <Select
            placeholder="角色"
            allowClear
            showSearch
            optionFilterProp="label"
            style={{ width: 160 }}
            value={filterRoleId}
            onChange={(v) => { setFilterRoleId(v); setPageNo(1); fetchData(1, { role_id: v }) }}
            options={roles.map((r) => ({ label: r.name, value: r.id }))}
          />
          <TreeSelect
            placeholder="部门"
            allowClear
            showSearch
            treeNodeFilterProp="title"
            treeDefaultExpandAll
            style={{ width: 180 }}
            value={filterDeptId}
            onChange={(v) => { setFilterDeptId(v); setPageNo(1); fetchData(1, { dept_id: v }) }}
            treeData={deptTreeData}
          />
          <Select
            placeholder="状态"
            allowClear
            style={{ width: 110 }}
            value={filterActive}
            onChange={(v) => { setFilterActive(v); setPageNo(1); fetchData(1, { is_active: v }) }}
            options={[{ label: '启用', value: true }, { label: '停用', value: false }]}
          />
          <Button type="primary" ghost onClick={doSearch}>
            <Icon name="filter_list" className="text-sm mr-1" />
            筛选
          </Button>
          {activeFilterCount > 0 && (
            <Button type="link" onClick={resetFilters} className="px-1">
              清空筛选 ({activeFilterCount})
            </Button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={data} loading={loading}
          scroll={{ x: 1000 }}
          rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys, preserveSelectedRowKeys: true }}
          pagination={{
            current: pageNo, total, pageSize, showTotal: (t) => `共 ${t} 条`,
            showSizeChanger: true, pageSizeOptions: ['20', '50', '100'],
            // 改每页条数时 antd 会同时触发 onShowSizeChange 和 onChange。
            // 只在 onChange 里发请求(它带着新的 size)，onShowSizeChange 仅负责持久化，
            // 否则两次请求里后落地的那次会用上旧 pageSize 把结果覆盖回去。
            onChange: (p, size) => { setPageNo(p); fetchData(p, {}, size) },
            onShowSizeChange: (_current, size) => { setPageSize(size); setPageNo(1) },
          }}
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors"
        />
      </div>

      {/* Create / Edit Modal */}
      <Modal title={editingUser ? '编辑用户' : '新建用户'} open={modal} onOk={handleSubmit}
        onCancel={() => { setModal(false); setEditingUser(null); form.resetFields() }} width={500}>
        <Form form={form} layout="vertical">
          {!editingUser && (
            <>
              <Form.Item name="username" label="用户名" rules={[{ required: true }]}><Input placeholder="请输入用户名" /></Form.Item>
              <Form.Item name="password" label="密码" rules={[{ required: true }]}><Input.Password placeholder="请输入密码" /></Form.Item>
            </>
          )}
          <Form.Item name="real_name" label="姓名" rules={[{ required: true }]}><Input placeholder="请输入姓名" /></Form.Item>
          <Form.Item name="phone" label="手机"><Input placeholder="请输入手机号" /></Form.Item>
          <Form.Item name="email" label="邮箱"><Input placeholder="请输入邮箱" /></Form.Item>
          <Form.Item name="role_ids" label="角色">
            <Select mode="multiple" placeholder="选择角色"
              options={roles.map((r) => ({ label: r.name, value: r.id }))} />
          </Form.Item>
          <Form.Item name="department_ids" label="部门">
            <TreeSelect
              treeData={deptTreeData}
              multiple
              placeholder="选择部门"
              treeDefaultExpandAll
              allowClear
            />
          </Form.Item>
          {editingUser && (
            <Form.Item name="is_active" label="启用" valuePropName="checked"><Switch /></Form.Item>
          )}
        </Form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal
        title="重置用户密码"
        open={resetModal}
        onOk={handleResetPassword}
        confirmLoading={resetting}
        onCancel={() => { setResetModal(false); setResetTarget(null); resetForm.resetFields() }}
        okText="重置"
        okButtonProps={{ danger: true }}
        width={440}
      >
        {resetTarget && (
          <div className="mb-3 p-3 bg-amber-50 rounded-lg text-sm text-amber-700 border border-amber-100">
            将为用户 <b>{resetTarget.real_name || resetTarget.username}</b> (<span className="font-mono">{resetTarget.username}</span>) 重置密码。重置后该用户原密码将立即失效。
          </div>
        )}
        <Form form={resetForm} layout="vertical">
          <Form.Item
            name="new_password"
            label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, message: '密码长度不能少于 8 位' },
              {
                validator: (_r, v) => {
                  if (!v) return Promise.resolve()
                  const hasUpper = /[A-Z]/.test(v)
                  const hasLower = /[a-z]/.test(v)
                  const hasDigit = /\d/.test(v)
                  return hasUpper && hasLower && hasDigit
                    ? Promise.resolve()
                    : Promise.reject(new Error('密码必须包含大小写字母和数字'))
                },
              },
            ]}
          >
            <Input.Password placeholder="至少 8 位，含大小写字母和数字" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="confirm_password"
            label="确认密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_r, v) {
                  if (!v || getFieldValue('new_password') === v) return Promise.resolve()
                  return Promise.reject(new Error('两次输入的密码不一致'))
                },
              }),
            ]}
          >
            <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
          </Form.Item>
          <Form.Item name="require_change" valuePropName="checked" className="!mb-0">
            <Checkbox>
              要求用户自行设置密码
              <div className="text-sm text-slate-400 font-normal">
                勾选后该用户下次修改密码无需填写原密码。用于你不打算把这个密码告知本人的情况
                （如钉钉同步建号时写入的默认密码）。
              </div>
            </Checkbox>
          </Form.Item>
        </Form>
      </Modal>

      {/* Import Modal */}
      <Modal
        title="批量导入用户"
        open={importModal}
        onOk={handleImport}
        onCancel={() => { setImportModal(false); setImportFile(null); setImportResult(null) }}
        okText="开始导入"
        confirmLoading={importing}
        width={520}
      >
        <div className="space-y-4">
          <div className="text-sm text-slate-500">
            请上传CSV文件，文件需包含以下列（第一行为标题行）：
            <div className="mt-2 bg-slate-50 rounded p-2 text-sm font-mono text-slate-700 break-all">
              username, password, real_name, phone, email, role_codes, department_names
            </div>
            <div className="mt-1 text-sm text-slate-400">
              role_codes 和 department_names 可用英文逗号分隔多个值
            </div>
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              style={{ display: 'none' }}
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) { setImportFile(f); setImportResult(null) }
              }}
            />
            <Button icon={<UploadOutlined />} onClick={() => fileInputRef.current?.click()}>
              选择CSV文件
            </Button>
            {importFile && (
              <span className="ml-2 text-sm text-slate-600">{importFile.name}</span>
            )}
          </div>
          {importResult && (
            <div className="space-y-2">
              <Alert
                type={importResult.failed.length === 0 ? 'success' : 'warning'}
                message={`导入完成：成功 ${importResult.success} 条，失败 ${importResult.failed.length} 条`}
                showIcon
              />
              {importResult.failed.length > 0 && (
                <div className="max-h-40 overflow-y-auto bg-red-50 rounded p-2">
                  {importResult.failed.map((f, i) => (
                    <div key={i} className="text-sm text-red-600">第 {f.row} 行：{f.reason}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>

      {/* 批量改角色 Modal */}
      <Modal
        title={`批量修改角色（已选 ${selectedRowKeys.length} 个用户）`}
        open={bulkModal}
        onOk={doBulkRoles}
        confirmLoading={bulkSaving}
        onCancel={() => setBulkModal(false)}
        okText="确定"
        cancelText="取消"
        width={480}
      >
        <div className="space-y-4 py-1">
          <div>
            <div className="text-sm font-medium text-slate-700 mb-1.5">应用方式</div>
            <Radio.Group value={bulkMode} onChange={(e) => setBulkMode(e.target.value)}>
              <Radio value="replace">覆盖（用所选角色替换原有角色）</Radio>
              <Radio value="add">追加（在原有角色基础上增加）</Radio>
            </Radio.Group>
          </div>
          <div>
            <div className="text-sm font-medium text-slate-700 mb-1.5">角色</div>
            <Select mode="multiple" placeholder="选择角色" className="w-full"
              value={bulkRoleIds} onChange={setBulkRoleIds}
              options={roles.map((r) => ({ label: r.name, value: r.id }))} />
            {bulkMode === 'replace' && bulkRoleIds.length === 0 && (
              <div className="text-[12px] text-amber-600 mt-1">提示：覆盖模式下不选角色，将清空所选用户的全部角色。</div>
            )}
          </div>
        </div>
      </Modal>
    </div>
  )
}
