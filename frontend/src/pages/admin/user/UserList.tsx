import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Select, TreeSelect, Space, message, Switch } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { userApi, roleApi } from '@/api/user'
import { departmentApi } from '@/api/department'
import type { Role, Department } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

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
  const [roles, setRoles] = useState<Role[]>([])
  const [deptTree, setDeptTree] = useState<Department[]>([])
  const [deptFlat, setDeptFlat] = useState<{ id: string; name: string }[]>([])
  const [modal, setModal] = useState(false)
  const [editingUser, setEditingUser] = useState<UserItem | null>(null)
  const [form] = Form.useForm()

  const fetchData = async (page = pageNo, kw = keyword) => {
    setLoading(true)
    try {
      const res = await userApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined })
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

  const doSearch = () => { setPageNo(1); fetchData(1, keyword) }

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

  const columns = [
    { title: '用户', key: 'user', width: 200,
      render: (_: unknown, record: UserItem) => (
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center text-xs font-bold text-primary shrink-0">
            {(record.real_name || record.username).slice(0, 2)}
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900">{record.real_name || record.username}</div>
            <div className="text-[11px] text-slate-400">{record.username}</div>
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
            <span key={r} className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-primary/10 text-primary border border-primary/20">
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
            <span key={d} className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-600 border border-slate-200">
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
          <span className="text-xs font-medium text-slate-600">{v ? '启用' : '停用'}</span>
        </div>
      ),
    },
    { title: '', width: 80,
      render: (_: unknown, record: UserItem) => (
        <a className="text-primary text-xs font-bold uppercase tracking-widest" onClick={() => {
          setEditingUser(record)
          form.setFieldsValue({
            real_name: record.real_name, phone: record.phone, email: record.email,
            is_active: record.is_active,
            role_ids: roles.filter((r) => record.roles.includes(r.code)).map((r) => r.id),
            department_ids: deptFlat.filter((d) => record.departments.includes(d.name)).map((d) => d.id),
          })
          setModal(true)
        }}>编辑</a>
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
        <Button type="primary" icon={<PlusOutlined />}
          onClick={() => { setEditingUser(null); form.resetFields(); setModal(true) }}
          className="shadow-lg shadow-primary/20 font-bold">
          新建用户
        </Button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 items-center">
          <Input
            placeholder="搜索用户名/姓名..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }}
            className="rounded-lg"
          />
          <Button onClick={doSearch}>
            <span className="material-symbols-outlined text-sm mr-1">filter_list</span>
            筛选
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={data} loading={loading}
          scroll={{ x: 1000 }}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors"
        />
      </div>

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
              treeData={toTreeData(deptTree)}
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
    </div>
  )
}
