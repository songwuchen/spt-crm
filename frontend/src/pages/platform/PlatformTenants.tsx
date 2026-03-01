import { useState, useEffect } from 'react'
import { Table, Button, Tag, Modal, Input, Select, Space, Switch, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { platformApi } from '@/api/platform'
import type { PlatformTenant, TenantPlan } from '@/api/platform'
import { usePageTitle } from '@/hooks/usePageTitle'

export default function PlatformTenants() {
  usePageTitle('租户管理')
  const [tenants, setTenants] = useState<PlatformTenant[]>([])
  const [plans, setPlans] = useState<TenantPlan[]>([])
  const [loading, setLoading] = useState(true)

  // Plan modal
  const [planModal, setPlanModal] = useState(false)
  const [planForm, setPlanForm] = useState({ name: '', status: 'active' })

  const fetchAll = () => {
    setLoading(true)
    Promise.all([
      platformApi.listTenants().then(r => r.data && setTenants(r.data)).catch(() => {}),
      platformApi.listPlans().then(r => r.data && setPlans(r.data)).catch(() => {}),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { fetchAll() }, [])

  const handleToggleActive = async (tenant: PlatformTenant) => {
    try {
      await platformApi.updateTenant(tenant.id, { is_active: !tenant.is_active })
      message.success(tenant.is_active ? '已停用' : '已启用')
      fetchAll()
    } catch { message.error('操作失败') }
  }

  const handleBindPlan = async (tenantId: string, plan: string) => {
    try {
      await platformApi.updateTenant(tenantId, { plan })
      message.success('套餐已绑定')
      fetchAll()
    } catch { message.error('绑定失败') }
  }

  const handleCreatePlan = async () => {
    try {
      await platformApi.createPlan(planForm)
      message.success('套餐已创建')
      setPlanModal(false)
      setPlanForm({ name: '', status: 'active' })
      fetchAll()
    } catch { message.error('创建套餐失败') }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">平台租户管理</h1>
        <p className="text-sm text-slate-500 mt-1">管理租户开通、停用与套餐绑定</p>
      </div>

      {/* Tenant List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="text-sm font-bold text-slate-900">租户列表</h3>
          <span className="text-xs text-slate-400">{tenants.length} 个租户</span>
        </div>
        <Table rowKey="id" dataSource={tenants} loading={loading} size="small" pagination={{ pageSize: 20 }}
          columns={[
            { title: '编码', dataIndex: 'code', width: 120, render: (v: string) => <span className="font-mono font-bold text-primary">{v}</span> },
            { title: '名称', dataIndex: 'name', width: 200 },
            { title: '联系人', dataIndex: 'contact_name', width: 120 },
            { title: '邮箱', dataIndex: 'contact_email', width: 200 },
            { title: '套餐', dataIndex: 'plan', width: 120,
              render: (v: string, r: PlatformTenant) => (
                <Select size="small" value={v || ''} onChange={(val) => handleBindPlan(r.id, val)}
                  style={{ width: 100 }}
                  options={[
                    { value: '', label: '无' },
                    ...plans.map(p => ({ value: p.name, label: p.name })),
                  ]} />
              ),
            },
            { title: '状态', dataIndex: 'is_active', width: 100,
              render: (v: boolean) => v ? <Tag color="success">活跃</Tag> : <Tag color="default">停用</Tag>,
            },
            { title: '创建时间', dataIndex: 'created_at', width: 160,
              render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-',
            },
            { title: '操作', key: 'actions', width: 100,
              render: (_: unknown, r: PlatformTenant) => (
                <Switch checked={r.is_active} size="small" onChange={() => handleToggleActive(r)}
                  checkedChildren="启用" unCheckedChildren="停用" />
              ),
            },
          ]}
        />
      </div>

      {/* Plans Section */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="text-sm font-bold text-slate-900">套餐计划</h3>
          <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setPlanModal(true)}>新增套餐</Button>
        </div>
        <Table rowKey="id" dataSource={plans} size="small" pagination={false}
          columns={[
            { title: '名称', dataIndex: 'name', width: 150 },
            { title: '定价', dataIndex: 'pricing_json', render: (v: unknown) => v ? <pre className="text-xs text-slate-600 whitespace-pre-wrap max-w-xs">{JSON.stringify(v, null, 2)}</pre> : '-' },
            { title: '限额', dataIndex: 'limits_json', render: (v: unknown) => v ? <pre className="text-xs text-slate-600 whitespace-pre-wrap max-w-xs">{JSON.stringify(v, null, 2)}</pre> : '-' },
            { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => <Tag color={v === 'active' ? 'success' : 'default'}>{v}</Tag> },
            { title: '创建时间', dataIndex: 'created_at', width: 130, render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
          ]}
        />
      </div>

      {/* Create Plan Modal */}
      <Modal title="新增套餐" open={planModal} onOk={handleCreatePlan} onCancel={() => setPlanModal(false)}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">套餐名称</label>
            <Input value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} placeholder="标准版 / 专业版 / 企业版" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">状态</label>
            <Select className="w-full" value={planForm.status} onChange={(v) => setPlanForm({ ...planForm, status: v })}
              options={[{ value: 'active', label: '启用' }, { value: 'inactive', label: '停用' }]} />
          </div>
        </div>
      </Modal>
    </div>
  )
}
