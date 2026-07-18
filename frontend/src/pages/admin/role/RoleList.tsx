import { useState, useEffect, useMemo } from 'react'
import { Table, Button, Modal, Form, Input, Select, Space, message, Checkbox, Tag, Alert, Spin } from 'antd'
import { PlusOutlined, DeleteOutlined, SearchOutlined, SyncOutlined } from '@ant-design/icons'
import { roleApi, permissionApi, rbacApi } from '@/api/user'
import type { RbacSyncPreview } from '@/api/user'
import type { Role, PermissionItem } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

const actionLabels: Record<string, string> = {
  view: '查看', create: '创建', edit: '编辑', delete: '删除',
  advance: '推进', sign: '签署', manage: '管理', export: '导出',
}

const DATA_SCOPE_OPTIONS = [
  { value: 'self', label: '仅本人' },
  { value: 'dept', label: '本部门及下级' },
  { value: 'all', label: '全部数据' },
]
const dataScopeLabel = (v?: string) => DATA_SCOPE_OPTIONS.find((o) => o.value === (v || 'self'))?.label || '仅本人'

export default function RoleList() {
  usePageTitle('角色管理')
  const [roles, setRoles] = useState<Role[]>([])
  const [permissions, setPermissions] = useState<PermissionItem[]>([])
  const [createModal, setCreateModal] = useState(false)
  const [permModal, setPermModal] = useState(false)
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)
  const [selectedPermIds, setSelectedPermIds] = useState<string[]>([])
  const [permSearch, setPermSearch] = useState('')
  const [editingRole, setEditingRole] = useState<Role | null>(null)
  const [form] = Form.useForm()

  // 同步标准角色与权限
  const [syncModal, setSyncModal] = useState(false)
  const [syncMode, setSyncMode] = useState<'additive' | 'reset'>('additive')
  const [syncPreview, setSyncPreview] = useState<RbacSyncPreview | null>(null)
  const [syncLoading, setSyncLoading] = useState(false)
  const [syncApplying, setSyncApplying] = useState(false)

  const loadSyncPreview = async (mode: 'additive' | 'reset') => {
    setSyncLoading(true)
    try {
      const res = await rbacApi.previewStandardSync(mode)
      setSyncPreview(res.data)
    } catch (e: any) {
      message.error(e?.response?.data?.message || '预览失败')
    } finally {
      setSyncLoading(false)
    }
  }

  const openSync = () => {
    setSyncMode('additive')
    setSyncPreview(null)
    setSyncModal(true)
    loadSyncPreview('additive')
  }

  const changeSyncMode = (mode: 'additive' | 'reset') => {
    setSyncMode(mode)
    loadSyncPreview(mode)
  }

  const doApplySync = async () => {
    setSyncApplying(true)
    try {
      const res = await rbacApi.applyStandardSync(syncMode)
      const r = res.data
      const extra = r.roles_updated.length ? `、更新 ${r.roles_updated.length} 个角色` : ''
      message.success(`同步完成:新建 ${r.created_roles.length} 个角色、新增 ${r.perms_added} 项授权、移除 ${r.perms_removed} 项${extra}`)
      setSyncModal(false)
      // 同步可能新建了权限行,一并刷新权限目录,否则权限矩阵看不到新权限
      fetchRoles()
      fetchPermissions()
    } catch (e: any) {
      message.error(e?.response?.data?.message || '同步失败')
    } finally {
      setSyncApplying(false)
    }
  }

  const fetchRoles = async () => {
    const res = await roleApi.list()
    setRoles(res.data)
  }

  const fetchPermissions = async () => {
    const res = await permissionApi.list()
    setPermissions(res.data)
  }

  useEffect(() => { fetchRoles(); fetchPermissions() }, [])

  const openCreate = () => { setEditingRole(null); form.resetFields(); form.setFieldsValue({ data_scope: 'self' }); setCreateModal(true) }
  const openEditRole = (role: Role) => {
    setEditingRole(role)
    form.setFieldsValue({ code: role.code, name: role.name, description: role.description, data_scope: role.data_scope || 'self' })
    setCreateModal(true)
  }

  const handleSave = async () => {
    const values = await form.validateFields()
    if (editingRole) {
      await roleApi.update(editingRole.id, { name: values.name, description: values.description, data_scope: values.data_scope })
      message.success('角色已更新')
    } else {
      await roleApi.create(values)
      message.success('角色已创建')
    }
    setCreateModal(false); form.resetFields(); setEditingRole(null)
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
            <div className="text-[13px] font-mono text-slate-400">{record.code}</div>
          </div>
        </div>
      ),
    },
    { title: '描述', dataIndex: 'description', width: 200,
      render: (v: string) => v || <span className="text-slate-300">-</span>,
    },
    { title: '类型', dataIndex: 'is_system', width: 90,
      render: (v: boolean) => v ? (
        <span className="inline-flex px-2 py-0.5 rounded text-[12px] font-bold bg-primary/10 text-primary border border-primary/20">
          系统内置
        </span>
      ) : (
        <span className="inline-flex px-2 py-0.5 rounded text-[12px] font-bold bg-slate-100 text-slate-500 border border-slate-200">
          自定义
        </span>
      ),
    },
    { title: '数据范围', dataIndex: 'data_scope', width: 130,
      render: (v: string) => <Tag color={v === 'all' ? 'red' : v === 'dept' ? 'blue' : 'default'}>{dataScopeLabel(v)}</Tag>,
    },
    { title: '权限数', dataIndex: 'permissions', width: 90,
      render: (v: string[]) => (
        <span className="text-sm font-black text-slate-700 tabular-nums">{v.length}</span>
      ),
    },
    { title: '', width: 240,
      render: (_: unknown, record: Role) => (
        <Space size={8}>
          <a className="text-slate-600 text-sm font-bold uppercase tracking-widest" onClick={() => openEditRole(record)}>编辑</a>
          <a className="text-primary text-sm font-bold uppercase tracking-widest flex items-center gap-1" onClick={() => openPermMatrix(record)}>
            <span className="material-symbols-outlined text-sm">tune</span>
            配置权限
          </a>
          {!record.is_system && (
            <a className="text-rose-500 text-sm font-bold flex items-center gap-0.5" onClick={() => handleDeleteRole(record)}>
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
        <Space>
          <Button icon={<SyncOutlined />} onClick={openSync} className="font-bold">
            同步标准角色与权限
          </Button>
          <Button type="primary" icon={<PlusOutlined />}
            onClick={openCreate}
            className="shadow-lg shadow-primary/20 font-bold">
            新建角色
          </Button>
        </Space>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={roles} pagination={false}
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors" />
      </div>

      {/* Create / Edit Modal */}
      <Modal title={editingRole ? '编辑角色' : '新建角色'} open={createModal} onOk={handleSave}
        onCancel={() => { setCreateModal(false); setEditingRole(null) }}>
        <Form form={form} layout="vertical">
          <Form.Item name="code" label="角色编码" rules={[{ required: true }]}>
            <Input placeholder="如 sales_manager" disabled={!!editingRole} />
          </Form.Item>
          <Form.Item name="name" label="角色名称" rules={[{ required: true }]}>
            <Input placeholder="如 销售经理" />
          </Form.Item>
          <Form.Item name="data_scope" label="数据范围"
            tooltip="控制该角色可见的业务数据范围（客户/线索/商机）：仅本人=只看自己负责的；本部门及下级=看本部门及所有下级部门成员的；全部=看本租户全部">
            <Select options={DATA_SCOPE_OPTIONS} />
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
                  <span className="text-sm font-bold uppercase tracking-widest text-slate-500">{group}</span>
                  <span className="text-[12px] text-slate-400 ml-auto">{checkedCount}/{groupIds.length}</span>
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
                        <span className="text-sm font-medium truncate">
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

      {/* 同步标准角色与权限 Modal */}
      <Modal
        title="同步标准角色与权限"
        open={syncModal}
        width={640}
        onCancel={() => setSyncModal(false)}
        onOk={doApplySync}
        okText={syncMode === 'reset' ? '应用同步(含移除)' : '应用同步'}
        okButtonProps={{
          loading: syncApplying,
          danger: syncMode === 'reset',
          disabled: syncLoading || !syncPreview
            || (syncPreview.summary.roles_to_create + syncPreview.summary.perms_to_add + syncPreview.summary.perms_to_remove
                + syncPreview.summary.roles_to_update + syncPreview.summary.permissions_to_create === 0),
        }}
      >
        <Alert
          type="info"
          showIcon
          className="mb-3"
          message="把本租户的「系统标准角色」对齐到系统标准目录"
          description="按需新建缺失的标准角色、补齐标准权限(含扩展平台)。自定义 / 人名角色不受影响。变更后本租户用户会自动刷新权限(无需等 5 分钟缓存)。"
        />

        <Checkbox
          className="mb-3"
          checked={syncMode === 'reset'}
          onChange={(e) => changeSyncMode(e.target.checked ? 'reset' : 'additive')}
        >
          <span className="text-sm">高级:重置为标准(<span className="text-rose-500 font-semibold">移除</span>标准角色上的多余/自定义授权)</span>
        </Checkbox>

        {syncLoading || !syncPreview ? (
          <div className="flex justify-center py-10"><Spin /></div>
        ) : (
          (() => {
            const s = syncPreview.summary
            const nothing = s.roles_to_create + s.perms_to_add + s.perms_to_remove
              + s.roles_to_update + s.permissions_to_create === 0
            if (nothing) {
              return <Alert type="success" showIcon message="已是最新 — 本租户标准角色权限无需变更。" />
            }
            return (
              <div className="max-h-[420px] overflow-y-auto space-y-3">
                <div className="flex flex-wrap gap-2">
                  <Tag color="blue">新建角色 {s.roles_to_create}</Tag>
                  <Tag color="green">新增授权 {s.perms_to_add}</Tag>
                  {syncMode === 'reset' && <Tag color="red">移除授权 {s.perms_to_remove}</Tag>}
                  {syncMode === 'reset' && s.roles_to_update > 0 && <Tag color="orange">更新角色 {s.roles_to_update}</Tag>}
                  {s.permissions_to_create > 0 && <Tag>补权限目录 {s.permissions_to_create}</Tag>}
                </div>

                {syncPreview.roles_to_update.length > 0 && (
                  <div className="border border-orange-100 bg-orange-50/40 rounded-lg p-3">
                    <div className="text-sm font-bold text-orange-500 mb-2">将对齐角色属性(名称/描述/数据范围)</div>
                    <div className="space-y-1">
                      {syncPreview.roles_to_update.map((r) => (
                        <div key={r.code} className="text-[13px]">
                          <span className="font-mono font-semibold text-slate-700">{r.code}</span>
                          <span className="text-slate-500">:{r.changes.join('、')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {syncPreview.roles_to_create.length > 0 && (
                  <div className="border border-slate-100 rounded-lg p-3">
                    <div className="text-sm font-bold text-slate-500 mb-2">将新建角色</div>
                    <div className="flex flex-wrap gap-2">
                      {syncPreview.roles_to_create.map((r) => (
                        <Tag key={r.code} color="blue">{r.name} <span className="opacity-60">({r.code} · {r.perm_count} 权限)</span></Tag>
                      ))}
                    </div>
                  </div>
                )}

                {Object.keys(syncPreview.perms_to_add).length > 0 && (
                  <div className="border border-slate-100 rounded-lg p-3">
                    <div className="text-sm font-bold text-slate-500 mb-2">给现有标准角色新增权限</div>
                    <div className="space-y-2">
                      {Object.entries(syncPreview.perms_to_add).map(([code, perms]) => (
                        <div key={code} className="text-[13px]">
                          <span className="font-mono font-semibold text-slate-700">{code}</span>
                          <span className="text-slate-400"> +{perms.length}:</span>{' '}
                          <span className="text-slate-500">{perms.map((p) => p.name).join('、')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {syncMode === 'reset' && Object.keys(syncPreview.perms_to_remove).length > 0 && (
                  <div className="border border-rose-100 bg-rose-50/40 rounded-lg p-3">
                    <div className="text-sm font-bold text-rose-500 mb-2">将从标准角色移除(重置)</div>
                    <div className="space-y-2">
                      {Object.entries(syncPreview.perms_to_remove).map(([code, perms]) => (
                        <div key={code} className="text-[13px]">
                          <span className="font-mono font-semibold text-slate-700">{code}</span>
                          <span className="text-rose-400"> -{perms.length}:</span>{' '}
                          <span className="text-slate-500">{perms.map((p) => p.name).join('、')}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })()
        )}
      </Modal>
    </div>
  )
}
