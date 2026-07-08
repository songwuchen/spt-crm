import { useState, useEffect } from 'react'
import { Table, Button, Tag, Modal, Input, Select, Space, Switch, message, Spin } from 'antd'
import { PlusOutlined, TeamOutlined, CloudOutlined, ThunderboltOutlined, DatabaseOutlined } from '@ant-design/icons'
import { platformApi } from '@/api/platform'
import type { PlatformTenant, TenantPlan, PlatformOverview } from '@/api/platform'
import { usePageTitle } from '@/hooks/usePageTitle'
import DataView from '@/components/DataView'

/** 接口可能返回数组或分页对象 {items:[...]}，统一成数组，避免 Table 收到非数组而崩溃 */
function toArray<T>(data: unknown): T[] {
  if (Array.isArray(data)) return data as T[]
  if (data && typeof data === 'object' && Array.isArray((data as { items?: unknown }).items)) {
    return (data as { items: T[] }).items
  }
  return []
}

const metricLabels: Record<string, { label: string; icon: React.ReactNode; unit: string; format: (v: number) => string }> = {
  user_active: { label: '活跃用户', icon: <TeamOutlined />, unit: '人', format: (v) => String(Math.round(v)) },
  api_calls: { label: 'API 调用', icon: <ThunderboltOutlined />, unit: '次', format: (v) => v >= 10000 ? `${(v / 10000).toFixed(1)}万` : String(Math.round(v)) },
  ai_tokens: { label: 'AI Tokens', icon: <CloudOutlined />, unit: '', format: (v) => v >= 1000000 ? `${(v / 1000000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(1)}K` : String(Math.round(v)) },
  ai_cost: { label: 'AI 费用', icon: <CloudOutlined />, unit: '元', format: (v) => `¥${v.toFixed(2)}` },
  storage_bytes: { label: '存储用量', icon: <DatabaseOutlined />, unit: '', format: (v) => v >= 1073741824 ? `${(v / 1073741824).toFixed(1)} GB` : `${(v / 1048576).toFixed(1)} MB` },
}

function StatCard({ title, value, icon, sub }: { title: string; value: string | number; icon: React.ReactNode; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 flex items-start gap-4">
      <div className="w-11 h-11 rounded-xl bg-primary/10 flex items-center justify-center text-primary text-lg shrink-0">
        {icon}
      </div>
      <div>
        <div className="text-2xl font-extrabold text-slate-900 tracking-tight">{value}</div>
        <div className="text-sm text-slate-500 mt-0.5">{title}</div>
        {sub && <div className="text-[13px] text-slate-400 mt-0.5">{sub}</div>}
      </div>
    </div>
  )
}

export default function PlatformTenants() {
  usePageTitle('租户管理')
  const [tenants, setTenants] = useState<PlatformTenant[]>([])
  const [plans, setPlans] = useState<TenantPlan[]>([])
  const [overview, setOverview] = useState<PlatformOverview | null>(null)
  const [loading, setLoading] = useState(true)

  // Plan modal
  const [planModal, setPlanModal] = useState(false)
  const [planForm, setPlanForm] = useState({ name: '', status: 'active' })

  const fetchAll = () => {
    setLoading(true)
    Promise.all([
      platformApi.listTenants().then(r => setTenants(toArray<PlatformTenant>(r.data))).catch(() => {}),
      platformApi.listPlans().then(r => setPlans(toArray<TenantPlan>(r.data))).catch(() => {}),
      platformApi.getOverview().then(r => r.data && setOverview(r.data)).catch(() => {}),
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

      {/* Overview Cards */}
      {loading && !overview ? (
        <div className="flex justify-center py-8"><Spin /></div>
      ) : overview && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="租户总数"
            value={overview.total_tenants}
            icon={<TeamOutlined />}
            sub={`${overview.active_tenants} 个活跃`}
          />
          <StatCard
            title="用户总数"
            value={overview.total_users}
            icon={<TeamOutlined />}
          />
          {Object.entries(overview.usage_summary || {}).slice(0, 2).map(([code, val]) => {
            const m = metricLabels[code]
            return m ? (
              <StatCard
                key={code}
                title={`本月${m.label}`}
                value={m.format(val)}
                icon={m.icon}
                sub={overview.current_period}
              />
            ) : null
          })}
        </div>
      )}

      {/* Per-Tenant Usage */}
      {overview && Object.keys(overview.tenant_usage || {}).length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-6">
          <div className="p-4 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900">租户用量概览 ({overview.current_period})</h3>
          </div>
          <Table
            rowKey="id"
            dataSource={tenants.filter(t => overview.tenant_usage[t.id])}
            size="small"
            pagination={false}
            columns={[
              { title: '租户', dataIndex: 'name', width: 200,
                render: (v: string, r: PlatformTenant) => (
                  <div>
                    <div className="font-bold text-slate-900 text-sm">{v}</div>
                    <div className="text-[13px] text-slate-400 font-mono">{r.code}</div>
                  </div>
                ),
              },
              ...Object.keys(metricLabels).map(code => ({
                title: metricLabels[code].label,
                key: code,
                width: 120,
                align: 'right' as const,
                render: (_: unknown, r: PlatformTenant) => {
                  const val = overview.tenant_usage[r.id]?.[code]
                  return val != null ? (
                    <span className="text-sm font-bold text-slate-700">{metricLabels[code].format(val)}</span>
                  ) : <span className="text-slate-300">-</span>
                },
              })),
            ]}
          />
        </div>
      )}

      {/* Tenant List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="text-sm font-bold text-slate-900">租户列表</h3>
          <span className="text-sm text-slate-400">{tenants.length} 个租户</span>
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
            { title: '定价', dataIndex: 'pricing_json', render: (v: unknown) => <div className="max-w-xs"><DataView value={v} /></div> },
            { title: '限额', dataIndex: 'limits_json', render: (v: unknown) => <div className="max-w-xs"><DataView value={v} /></div> },
            { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => <Tag color={v === 'active' ? 'success' : 'default'}>{v === 'active' ? '启用' : v === 'inactive' ? '停用' : v}</Tag> },
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
