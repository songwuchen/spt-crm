import { useState, useEffect, useMemo } from 'react'
import { Table, Button, Modal, Form, Input, Space, message, Checkbox, Tag } from 'antd'
import { PlusOutlined, DeleteOutlined, SearchOutlined } from '@ant-design/icons'
import { roleApi, permissionApi } from '@/api/user'
import type { Role, PermissionItem } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

const actionLabels: Record<string, string> = {
  view: '查看', create: '创建', edit: '编辑', delete: '删除',
  advance: '推进', sign: '签署', manage: '管理', export: '导出',
}

export default function RoleList() {
  usePageTitle('角色管理')
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<PermissionItem[]>([])
  const [createModal, setCreateModal] = useState(false)
  const [permModal, setPermModal] = useState(false)
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)
  const [selectedPermIds, setSelectedPermIds] = useState<string[]>([])
  const [permSearch, setPermSearch] = useState('')
  const [form] = Form.useForm()

  const fetchRoles = async () => {
    const res = await roleApi.list()
    setRoles(res.data)
  }

  const fetchPermissions = async () => {
    const res = await permissionApi.list()
    setPermissions(res.data)
  }

  useEffect(() => { fetchRoles(); fetchPermissions() }, [])

  const handleCreate = async () => {
    const values = await form.validateFields()
    await roleApi.create(values)
    message.success('角色已创建')
    setCreateModal(false); form.resetFields()
    fetchRoles()
  }

  const openPermMatrix = (role: Role) => {
    setSelectedRole(role)
    const permIds = permissions.filter((p) => role.permissions.includes(p.code)).map((p) => p.id)
    setSelectedPermIds(permIds)
    setPermSearch('')
    setPermModal(true)
  }

  const handleDeleteRole = (role: Role) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除角色「${role.name}」？删除后不可恢复。`,
      okType: 'danger',
      onOk: async () => {
        try {
          await roleApi.delete(role.id)
          message.success('角色已删除')
          fetchRoles()
        } catch (e: any) {
          message.error(e?.response?.data?.message || '删除失败')
        }
      },
    })
  }

  const handleGrantPermissions = async () => {
    if (!selectedRole) return
    await roleApi.grantPermissions(selectedRole.id, selectedPermIds)
    message.success('权限已更新')
    setPermModal(false)
    fetchRoles()
  }

  // Build permission matrix: group → { resource → action[] }
  const permGroups = useMemo(() => {
    const groups: Record<string, PermissionItem[]> = {}
    permissions.forEach((p) => {
      if (!groups[p.group_name]) groups[p.group_name] = []
      groups[p.group_name].push(p)
    })
    return groups
  }, [permissions])

  // Filter groups by search
  const filteredGroups = useMemo(() => {
    if (!permSearch) return permGroups
    const kw = permSearch.toLowerCase()
    const result: Record<string, PermissionItem[]> = {}
    Object.entries(permGroups).forEach(([group, perms]) => {
      const matched = perms.filter(
        (p) => p.name.toLowerCase().includes(kw) || p.code.toLowerCase().includes(kw) || group.toLowerCase().includes(kw)
      )
      if (matched.length > 0) result[group] = matched
    })
    return result
  }, [permGroups, permSearch])

  const toggleGroup = (groupPerms: PermissionItem[]) => {
    const groupIds = groupPerms.map((p) => p.id)
    const allChecked = groupIds.every((id) => selectedPermIds.includes(id))
    if (allChecked) {
      setSelectedPermIds((prev) => prev.filter((id) => !groupIds.includes(id)))
    } else {
      setSelectedPermIds((prev) => [...new Set([...prev, ...groupIds])])
    }
  }

  const toggleAll = () => {
    const allIds = permissions.map((p) => p.id)
    if (selectedPermIds.length === allIds.length) {
      setSelectedPermIds([])
    } else {
      setSelectedPermIds(allIds)
    }
  }

  const columns = [
    { title: '角色', key: 'role', width: 200,
      render: (_: unknown, record: Role) => (
        <div className="flex items-center gap-3">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${
            record.is_system ? 'bg-primary/10 border border-primary/20' : 'bg-slate-100 border border-slate-200'
          }`}>
            <span className={`material-symbols-outlined text-sm ${record.is_system ? 'text-primary' : 'text-slate-400'}`}>
              {record.is_system ? 'verified_user' : 'shield'}
            </span>
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900">{record.name}</div>
            <div className="text-[11px] font-mono text-slate-400">{record.code}</div>
          </div>
        </div>
      ),
    },
    { title: '描述', dataIndex: 'description', width: 200,
      render: (v: string) => v || <span className="text-slate-300">-</span>,
    },
    { title: '类型', dataIndex: 'is_system', width: 90,
      render: (v: boolean) => v ? (
        <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-primary/10 text-primary border border-primary/20">
          系统内置
        </span>
      ) : (
        <span className="inline-flex px-2 py-0.5 rounded text-[10px] font-bold bg-slate-100 text-slate-500 border border-slate-200">
          自定义
        </span>
      ),
    },
    { title: '权限数', dataIndex: 'permissions', width: 90,
      render: (v: string[]) => (
        <span className="text-sm font-black text-slate-700 tabular-nums">{v.length}</span>
      ),
    },
    { title: '', width: 180,
      render: (_: unknown, record: Role) => (
        <Space size={8}>
          <a className="text-primary text-xs font-bold uppercase tracking-widest flex items-center gap-1" onClick={() => openPermMatrix(record)}>
            <span className="material-symbols-outlined text-sm">tune</span>
            配置权限
          </a>
          {!record.is_system && (
            <a className="text-rose-500 text-xs font-bold flex items-center gap-0.5" onClick={() => handleDeleteRole(record)}>
              <DeleteOutlined style={{ fontSize: 12 }} />
              删除
            </a>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">角色权限</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理角色和权限分配</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />}
          onClick={() => { form.resetFields(); setCreateModal(true) }}
          className="shadow-lg shadow-primary/20 font-bold">
          新建角色
        </Button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={roles} pagination={false}
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors" />
      </div>

      {/* Create Modal */}
      <Modal title="新建角色" open={createModal} onOk={handleCreate} onCancel={() => setCreateModal(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="code" label="角色编码" rules={[{ required: true }]}>
            <Input placeholder="如 sales_manager" />
          </Form.Item>
          <Form.Item name="name" label="角色名称" rules={[{ required: true }]}>
            <Input placeholder="如 销售经理" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="角色描述" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Permission Matrix Modal */}
      <Modal title={`配置权限 — ${selectedRole?.name || ''}`} open={permModal}
        onOk={handleGrantPermissions} onCancel={() => setPermModal(false)} width={720}
        okText="保存权限">
        <div className="mb-4 flex items-center gap-3">
          <Input
            placeholder="搜索权限..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={permSearch}
            onChange={(e) => setPermSearch(e.target.value)}
            allowClear
            style={{ width: 240 }}
          />
          <Button size="small" onClick={toggleAll}>
            {selectedPermIds.length === permissions.length ? '取消全选' : '全选'}
          </Button>
          <Tag color="blue">{selectedPermIds.length}/{permissions.length} 已选</Tag>
        </div>

        <div className="max-h-[480px] overflow-y-auto space-y-4">
          {Object.entries(filteredGroups).map(([group, perms]) => {
            const groupIds = perms.map((p) => p.id)
            const checkedCount = groupIds.filter((id) => selectedPermIds.includes(id)).length
            const allChecked = checkedCount === groupIds.length
            const indeterminate = checkedCount > 0 && !allChecked

            return (
              <div key={group} className="border border-slate-100 rounded-lg overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-2.5 bg-slate-50 border-b border-slate-100">
                  <Checkbox
                    checked={allChecked}
                    indeterminate={indeterminate}
                    onChange={() => toggleGroup(perms)}
                  />
                  <span className="text-xs font-bold uppercase tracking-widest text-slate-500">{group}</span>
                  <span className="text-[10px] text-slate-400 ml-auto">{checkedCount}/{groupIds.length}</span>
                </div>
                <div className="p-3 grid grid-cols-4 gap-2">
                  {perms.map((p) => {
                    const checked = selectedPermIds.includes(p.id)
                    const action = p.code.split(':')[1]
                    return (
                      <label key={p.id}
                        className={`flex items-center gap-2 px-3 py-2 rounded-lg border cursor-pointer transition-all
                          ${checked
                            ? 'border-primary/30 bg-primary/5 text-primary'
                            : 'border-slate-100 hover:border-slate-200 text-slate-600'
                          }`}
                      >
                        <Checkbox
                          checked={checked}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setSelectedPermIds((prev) => [...prev, p.id])
                            } else {
                              setSelectedPermIds((prev) => prev.filter((id) => id !== p.id))
                            }
                          }}
                        />
                        <span className="text-xs font-medium truncate">
                          {actionLabels[action] || p.name}
                        </span>
                      </label>
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      </Modal>
    </div>
  )
}
