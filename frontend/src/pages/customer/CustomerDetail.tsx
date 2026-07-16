import { useState, useEffect } from 'react'
import { Tag, Button, Space, Table, Modal, Form, Input, Select, Switch, Spin, Tabs, Popover, message } from 'antd'
import { PlusOutlined as PlusIcon } from '@ant-design/icons'
import { EditOutlined, PlusOutlined, DeleteOutlined, MergeCellsOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { contactApi } from '@/api/contact'
import { projectApi } from '@/api/project'
import { roleApi } from '@/api/user'
import AttachmentPanel from '@/components/AttachmentPanel'
import AiAnalysisButton from '@/components/ai/AiAnalysisButton'
import CustomFieldsPanel from '@/components/lowcode/EntityCustomFields'
import ActivityTimeline from '@/components/ActivityTimeline'
import ChangeHistory from '@/components/ChangeHistory'
import type { Customer, Contact, OpportunityProject, CustomerReport } from '@/api/types'
import { sourceLabels, stageLabels, stageColors } from '@/api/types'
import { opportunityStatusMap, quoteStatusLabels, contractStatusLabels, orderStatusLabels, tenderStatusLabels, ticketStatusLabels, ticketTypeLabels, ticketPriorityLabels } from '@/constants/labels'
import type { ColumnsType } from 'antd/es/table'
import client from '@/api/client'
import { downloadFile } from '@/utils/download'
import { formatRegion } from '@/utils/address'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'
import CustomerRelationGraph from '@/components/CustomerRelationGraph'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useDataDict } from '@/hooks/useDataDict'
import InternalNotes from '@/components/InternalNotes'
import ContactOrgChart from '@/components/ContactOrgChart'

const roleTypeMap: Record<string, { label: string; color: string }> = {
  decision_maker: { label: '决策者', color: 'bg-emerald-50 text-emerald-600 border-emerald-100' },
  influencer: { label: '影响者', color: 'bg-blue-50 text-blue-600 border-blue-100' },
  user: { label: '使用者', color: 'bg-slate-50 text-slate-600 border-slate-200' },
  finance: { label: '财务', color: 'bg-amber-50 text-amber-600 border-amber-100' },
  procurement: { label: '采购', color: 'bg-purple-50 text-purple-600 border-purple-100' },
}

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="py-3 border-b border-slate-50 last:border-0">
      <div className="text-[12px] text-slate-400 uppercase font-bold tracking-wider mb-1">{label}</div>
      <div className="text-sm font-semibold text-slate-700">{value || <span className="text-slate-300">-</span>}</div>
    </div>
  )
}

function ReportSection({ title, dataSource, columns }: { title: string; dataSource: any[]; columns: ColumnsType<any> }) {
  return (
    <div>
      <div className="text-sm font-bold text-slate-800 mb-2">{title}</div>
      {dataSource.length === 0 ? (
        <div className="text-slate-300 text-xs py-2">暂无数据</div>
      ) : (
        <Table rowKey="id" size="small" pagination={false} dataSource={dataSource} columns={columns} />
      )}
    </div>
  )
}

export default function CustomerDetail() {
  usePageTitle('客户详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState<Customer | null>(null)
  const [contacts, setContacts] = useState<Contact[]>([])
  const [contactModal, setContactModal] = useState(false)
  const [editingContact, setEditingContact] = useState<Contact | null>(null)
  const [contactCustomFields, setContactCustomFields] = useState<Record<string, unknown>>({})
  const [contactView, setContactView] = useState<'table' | 'chart'>('table')
  const [form] = Form.useForm()
  const [relations, setRelations] = useState<{ id: string; from_customer_id: string; to_customer_id: string; relation_type: string; to_customer_name?: string; note?: string }[]>([])
  const [shares, setShares] = useState<{ id: string; user_id: string; user_name?: string; permission_level: string }[]>([])
  const [relModal, setRelModal] = useState(false)
  const [shareModal, setShareModal] = useState(false)
  const [relForm] = Form.useForm()
  const [shareForm] = Form.useForm()
  const [allCustomers, setAllCustomers] = useState<Customer[]>([])
  const [roleList, setRoleList] = useState<{ id: string; name: string }[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [projects, setProjects] = useState<OpportunityProject[]>([])
  const [tickets, setTickets] = useState<{ id: string; ticket_no: string; type: string; status: string; priority: string; description?: string; created_at?: string }[]>([])
  const [contracts, setContracts] = useState<{ id: string; contract_no: string; status: string; amount?: number; created_at?: string }[]>([])
  const [mergeModal, setMergeModal] = useState(false)
  const [mergeTargetId, setMergeTargetId] = useState<string | undefined>()
  const [health, setHealth] = useState<{ score: number; grade: string; breakdown: Record<string, { score: number; max: number; detail: string }> } | null>(null)
  const [report, setReport] = useState<CustomerReport | null>(null)

  const customerSelect = useRemoteSelect(async (kw) => {
    const r = await customerApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).filter((c) => c.id !== id).map((c) => ({ label: c.name, value: c.id }))
  })

  const userSelect = useUserSelect()
  const industryDict = useDataDict('industry')
  const industryMap = Object.fromEntries(industryDict.options.map((o) => [o.value, o.label]))

  const fetchCustomer = async () => { const res = await customerApi.get(id!); setCustomer(res.data) }
  const fetchContacts = async () => { const res = await contactApi.list(id!); setContacts(res.data) }
  const fetchRelations = async () => { const res = await customerApi.listRelations(id!); setRelations(res.data) }
  const fetchShares = async () => { const res = await customerApi.listShares(id!); setShares(res.data) }
  const fetchStats = async () => { const res = await customerApi.stats(id!); setStats(res.data) }
  const fetchProjects = async () => {
    const res = await projectApi.list({ pageNo: 1, pageSize: 100, customer_id: id })
    setProjects(res.data.items)
  }
  const fetchTickets = async () => {
    const res = await client.get('/api/v1/service_tickets', { params: { customer_id: id } })
    const resData = res as { data?: { items?: typeof tickets } }
    setTickets(resData.data?.items || [])
  }

  useEffect(() => {
    if (!id) return
    let cancelled = false
    const load = async () => {
      fetchCustomer(); fetchContacts(); fetchRelations(); fetchShares(); fetchStats(); fetchProjects(); fetchTickets()
      customerApi.health(id).then(r => { if (!cancelled) setHealth(r.data) }).catch(() => {})
      customerApi.report(id).then((r) => { if (!cancelled) setReport(r.data) }).catch(() => {})
      customerApi.list({ pageNo: 1, pageSize: 100 }).then((r) => { if (!cancelled) setAllCustomers(r.data.items) }).catch(() => {})
    }
    load()
    return () => { cancelled = true }
  }, [id])

  const handleContactSubmit = async () => {
    const values = { ...(await form.validateFields()), custom_fields_json: contactCustomFields }
    if (editingContact) {
      await contactApi.update(id!, editingContact.id, values)
      message.success('联系人已更新')
    } else {
      await contactApi.create(id!, values)
      message.success('联系人已创建')
    }
    setContactModal(false); form.resetFields(); setEditingContact(null); fetchContacts()
  }

  const contactColumns: ColumnsType<Contact> = [
    { title: '姓名', dataIndex: 'name', width: 120,
      render: (v) => <span className="font-bold text-slate-900">{v}</span> },
    { title: '职务', dataIndex: 'title', width: 120 },
    { title: '角色', dataIndex: 'role_type', width: 100,
      render: (v) => {
        if (!v) return <span className="text-slate-300">-</span>
        const r = roleTypeMap[v]
        return r ? (
          <span className={`inline-flex px-2 py-0.5 rounded text-[12px] font-bold uppercase border ${r.color}`}>{r.label}</span>
        ) : v
      },
    },
    { title: '电话', dataIndex: 'phone', width: 130 },
    { title: '手机', dataIndex: 'mobile', width: 130 },
    { title: '邮箱', dataIndex: 'email', width: 180 },
    { title: '主要', dataIndex: 'is_primary', width: 70,
      render: (v) => v ? (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-primary/10 text-primary text-[12px] font-bold">
          <span className="material-symbols-outlined text-sm">star</span> 主要
        </span>
      ) : null,
    },
    { title: '', width: 100,
      render: (_, record) => (
        <Space size={4}>
          <a className="text-primary text-sm font-bold" onClick={() => {
            setEditingContact(record); form.setFieldsValue(record); setContactCustomFields((record as unknown as { custom_fields_json?: Record<string, unknown> }).custom_fields_json || {}); setContactModal(true)
          }}>编辑</a>
          <a className="text-rose-500 text-sm font-bold" onClick={() => {
            Modal.confirm({
              title: '确认删除', content: `确定要删除联系人「${record.name}」？`, okType: 'danger',
              onOk: async () => { await contactApi.delete(id!, record.id); message.success('已删除'); fetchContacts() },
            })
          }}>删除</a>
        </Space>
      ),
    },
  ]

  if (!customer) return (
    <DetailSkeleton />
  )

  const levelColors: Record<string, string> = { A: 'red', B: 'orange', C: 'blue', D: 'default' }

  return (
    <div>
      {/* Account Header */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-xl bg-slate-50 border border-slate-200 shadow-sm flex items-center justify-center text-2xl font-black text-slate-600">
              {customer.name.slice(0, 2)}
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl font-bold text-slate-900">{customer.name}</h1>
                {customer.level && (
                  <Tag color={levelColors[customer.level]}>{customer.level} 级客户</Tag>
                )}
                <div className="flex items-center gap-1.5">
                  <span className={`w-2 h-2 rounded-full ${customer.status === 'active' ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                  <span className="text-sm font-medium text-slate-500">
                    {customer.status === 'active' ? '活跃' : '不活跃'}
                  </span>
                </div>
              </div>
              {/* Tags */}
              <div className="flex items-center gap-1 flex-wrap mt-1">
                {(customer.tags_json || []).map((tag: string) => (
                  <Tag key={tag} closable onClose={async () => {
                    const next = (customer.tags_json || []).filter((t: string) => t !== tag)
                    await customerApi.update(id!, { tags_json: next })
                    fetchCustomer()
                  }} className="text-sm">{tag}</Tag>
                ))}
                <Popover trigger="click" content={
                  <Input size="small" placeholder="输入标签回车" style={{ width: 120 }}
                    onPressEnter={async (e) => {
                      const val = (e.target as HTMLInputElement).value.trim()
                      if (!val) return
                      const tags = customer.tags_json || []
                      if (tags.includes(val)) return
                      await customerApi.update(id!, { tags_json: [...tags, val] })
                      ;(e.target as HTMLInputElement).value = ''
                      fetchCustomer()
                    }} />
                }>
                  <Tag className="cursor-pointer border-dashed"><PlusIcon className="text-[12px]" /> 标签</Tag>
                </Popover>
              </div>
              <div className="flex items-center gap-4 text-sm text-slate-500">
                {customer.industry && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">factory</span> {industryMap[customer.industry] || customer.industry}
                  </span>
                )}
                {formatRegion(customer) && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">location_on</span> {formatRegion(customer)}
                  </span>
                )}
                {customer.customer_code && (
                  <span className="font-mono text-sm text-slate-400">#{customer.customer_code}</span>
                )}
              </div>
            </div>
          </div>
          <Space>
            <AiAnalysisButton bizType="customer" bizId={id!} />
            <Button icon={<EditOutlined />} onClick={() => navigate(`/customers/${id}/edit`)}>编辑</Button>
            {customer.status !== 'pool' && (
              <Button onClick={() => {
                Modal.confirm({
                  title: '释放到公海', content: `确定要将客户「${customer.name}」释放到公海池？`,
                  onOk: async () => { await customerApi.release(id!); message.success('已释放到公海'); navigate('/customer-pool') },
                })
              }}>释放到公海</Button>
            )}
            {customer.status === 'pool' && (
              <Button type="primary" onClick={async () => {
                try { await customerApi.claim(id!); message.success('已领取'); window.location.reload() }
                catch { message.error('领取失败') }
              }}>
                领取客户
              </Button>
            )}
            <Button icon={<MergeCellsOutlined />} onClick={() => { setMergeTargetId(undefined); setMergeModal(true) }}>合并</Button>
            <Button danger icon={<DeleteOutlined />} onClick={() => {
              Modal.confirm({
                title: '确认删除', content: `确定要删除客户「${customer.name}」及其所有联系人？`, okType: 'danger',
                onOk: async () => { await customerApi.delete(id!); message.success('客户已删除'); navigate('/customers') },
              })
            }}>删除</Button>
          </Space>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: '商机', value: stats.project_count || 0, amount: stats.project_amount, amountLabel: '预期金额', icon: 'trending_up', color: 'text-blue-600 bg-blue-50' },
          { label: '报价', value: stats.quote_count || 0, icon: 'request_quote', color: 'text-indigo-600 bg-indigo-50' },
          { label: '合同', value: stats.contract_count || 0, amount: stats.contract_amount, amountLabel: '签约金额', icon: 'description', color: 'text-emerald-600 bg-emerald-50' },
          { label: '工单', value: stats.ticket_count || 0, sub: stats.ticket_open ? `${stats.ticket_open} 处理中` : undefined, icon: 'support_agent', color: 'text-amber-600 bg-amber-50' },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <div className="flex items-center gap-3 mb-2">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${s.color}`}>
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{s.icon}</span>
              </div>
              <div>
                <div className="text-[12px] uppercase font-bold tracking-wider text-slate-400">{s.label}</div>
                <div className="text-xl font-black text-slate-900">{s.value}</div>
              </div>
            </div>
            {s.amount != null && s.amount > 0 && (
              <div className="text-sm text-slate-500">{s.amountLabel}: <span className="font-bold">¥{Number(s.amount).toLocaleString()}</span></div>
            )}
            {s.sub && <div className="text-sm text-amber-600 mt-1">{s.sub}</div>}
          </div>
        ))}
      </div>

      {/* Health Score */}
      {health && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-6">
          <div className="flex items-center gap-4 mb-3">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-lg font-black ${
              health.grade === 'A' ? 'bg-emerald-50 text-emerald-600' :
              health.grade === 'B' ? 'bg-blue-50 text-blue-600' :
              health.grade === 'C' ? 'bg-amber-50 text-amber-600' : 'bg-red-50 text-red-600'
            }`}>{health.grade}</div>
            <div>
              <div className="text-[12px] uppercase font-bold tracking-wider text-slate-400">健康度评分</div>
              <div className="text-xl font-black text-slate-900">{health.score}<span className="text-sm text-slate-400 font-normal">/100</span></div>
            </div>
            <div className="flex-1">
              <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${
                  health.score >= 80 ? 'bg-emerald-500' : health.score >= 60 ? 'bg-blue-500' : health.score >= 40 ? 'bg-amber-500' : 'bg-red-500'
                }`} style={{ width: `${health.score}%` }} />
              </div>
            </div>
          </div>
          <div className="grid grid-cols-4 gap-3">
            {Object.entries(health.breakdown).map(([key, b]) => (
              <div key={key} className="text-center">
                <div className="text-sm font-bold text-slate-500">{b.score}/{b.max}</div>
                <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mt-1 mb-1">
                  <div className="h-full bg-primary rounded-full" style={{ width: `${(b.score / b.max) * 100}%` }} />
                </div>
                <div className="text-[12px] text-slate-400">{b.detail}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Profile Metrics */}
      {(stats.won_count > 0 || stats.lost_count > 0 || stats.collection_rate > 0) && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-emerald-50 flex items-center justify-center">
              <span className="material-symbols-outlined text-emerald-600" style={{ fontSize: 22 }}>emoji_events</span>
            </div>
            <div>
              <div className="text-[12px] uppercase font-bold tracking-wider text-slate-400">赢单率</div>
              <div className="text-xl font-black text-slate-900">{((stats.win_rate || 0) * 100).toFixed(1)}%</div>
              <div className="text-sm text-slate-500">
                赢 <span className="font-bold text-emerald-600">{stats.won_count || 0}</span> / 丢 <span className="font-bold text-red-500">{stats.lost_count || 0}</span>
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center">
              <span className="material-symbols-outlined text-blue-600" style={{ fontSize: 22 }}>account_balance</span>
            </div>
            <div>
              <div className="text-[12px] uppercase font-bold tracking-wider text-slate-400">回款率</div>
              <div className={`text-xl font-black ${(stats.collection_rate || 0) >= 0.8 ? 'text-emerald-600' : (stats.collection_rate || 0) >= 0.5 ? 'text-amber-600' : 'text-red-600'}`}>
                {((stats.collection_rate || 0) * 100).toFixed(1)}%
              </div>
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center gap-4">
            <div className="w-10 h-10 rounded-full bg-violet-50 flex items-center justify-center">
              <span className="material-symbols-outlined text-violet-600" style={{ fontSize: 22 }}>payments</span>
            </div>
            <div>
              <div className="text-[12px] uppercase font-bold tracking-wider text-slate-400">签约总额</div>
              <div className="text-xl font-black text-slate-900">¥{Number(stats.contract_amount || 0).toLocaleString()}</div>
            </div>
          </div>
        </div>
      )}

      {/* Content Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Customer Portrait */}
        <div className="col-span-3">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-0">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">客户画像</h3>
            <InfoField label="简称" value={customer.short_name} />
            <InfoField label="企业规模" value={customer.scale_level} />
            <InfoField label="详细地址" value={customer.address} />
            <InfoField label="网站" value={customer.website} />
            <InfoField label="来源" value={customer.source ? (sourceLabels[customer.source] || customer.source) : undefined} />
            <InfoField label="负责人" value={customer.owner_name} />
            <InfoField label="备注" value={customer.remark} />
            <div className="pt-3">
              <CustomFieldsPanel entityType="customer" values={customer.custom_fields_json} readOnly />
            </div>
          </div>
        </div>

        {/* Center + Right: Tabs */}
        <div className="col-span-9">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <Tabs
              defaultActiveKey="contacts"
              className="px-6 pt-2"
              items={[
                {
                  key: 'contacts',
                  label: <span className="font-semibold">联系人 ({contacts.length})</span>,
                  children: (
                    <div className="pb-6">
                      <div className="flex justify-between mb-3">
                        <div className="flex gap-1">
                          <Button size="small" type={contactView === 'table' ? 'primary' : 'default'}
                            onClick={() => setContactView('table')}>列表</Button>
                          <Button size="small" type={contactView === 'chart' ? 'primary' : 'default'}
                            onClick={() => setContactView('chart')}>组织架构</Button>
                        </div>
                        <Button type="primary" size="small" icon={<PlusOutlined />}
                          onClick={() => { setEditingContact(null); form.resetFields(); setContactCustomFields({}); setContactModal(true) }}>
                          添加联系人
                        </Button>
                      </div>
                      {contactView === 'table' ? (
                        <Table rowKey="id" columns={contactColumns} dataSource={contacts} pagination={false} size="small"
                          scroll={{ x: 900 }} />
                      ) : (
                        <ContactOrgChart contacts={contacts} onSelect={(c) => {
                          setEditingContact(c)
                          form.setFieldsValue(c)
                          setContactCustomFields((c as unknown as { custom_fields_json?: Record<string, unknown> }).custom_fields_json || {})
                          setContactModal(true)
                        }} />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'activities',
                  label: <span className="font-semibold">互动记录</span>,
                  children: (
                    <div className="py-4">
                      <ActivityTimeline bizType="customer" bizId={id!} customerId={id!} />
                    </div>
                  ),
                },
                {
                  key: 'notes',
                  label: <span className="font-semibold">内部备忘</span>,
                  children: (
                    <div className="py-4">
                      <InternalNotes bizType="customer" bizId={id!} />
                    </div>
                  ),
                },
                {
                  key: 'relations',
                  label: <span className="font-semibold">关联企业 ({relations.length})</span>,
                  children: (
                    <div className="pb-6">
                      <div className="flex justify-end mb-3">
                        <Button type="primary" size="small" icon={<PlusOutlined />}
                          onClick={() => { relForm.resetFields(); setRelModal(true) }}>
                          添加关系
                        </Button>
                      </div>
                      {relations.length === 0 ? (
                        <div className="text-center py-8 text-slate-400 text-sm">暂无关联企业</div>
                      ) : (
                        <div className="space-y-2">
                          {relations.map((r) => {
                            const typeLabels: Record<string, { label: string; color: string }> = {
                              parent: { label: '母公司', color: 'text-blue-600 bg-blue-50' },
                              subsidiary: { label: '子公司', color: 'text-indigo-600 bg-indigo-50' },
                              affiliate: { label: '关联企业', color: 'text-emerald-600 bg-emerald-50' },
                              partner: { label: '合作伙伴', color: 'text-amber-600 bg-amber-50' },
                              competitor: { label: '竞争对手', color: 'text-red-600 bg-red-50' },
                            }
                            const t = typeLabels[r.relation_type] || { label: r.relation_type, color: 'text-slate-600 bg-slate-50' }
                            const relatedId = r.from_customer_id === id ? r.to_customer_id : r.from_customer_id
                            const relatedName = allCustomers.find((c) => c.id === relatedId)?.name || relatedId
                            return (
                              <div key={r.id} className="flex items-center gap-3 p-3 rounded-lg bg-slate-50 border border-slate-100">
                                <span className={`px-2 py-0.5 rounded text-[12px] font-bold ${t.color}`}>{t.label}</span>
                                <a onClick={() => navigate(`/customers/${relatedId}`)} className="text-sm font-bold text-primary hover:underline flex-1">{relatedName}</a>
                                {r.note && <span className="text-sm text-slate-400">{r.note}</span>}
                                <a className="text-rose-500 text-sm font-bold" onClick={async () => {
                                  await customerApi.deleteRelation(id!, r.id); message.success('已删除'); fetchRelations()
                                }}>删除</a>
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  ),
                },
                {
                  key: 'shares',
                  label: <span className="font-semibold">共享 ({shares.length})</span>,
                  children: (
                    <div className="pb-6">
                      <div className="flex justify-end mb-3">
                        <Button type="primary" size="small" icon={<PlusOutlined />}
                          onClick={() => {
                            shareForm.resetFields()
                            roleApi.list().then((r) => setRoleList(r.data || [])).catch(() => {})
                            setShareModal(true)
                          }}>
                          共享给
                        </Button>
                      </div>
                      {shares.length === 0 ? (
                        <div className="text-center py-8 text-slate-400 text-sm">暂未共享给其他人</div>
                      ) : (
                        <Table rowKey="id" dataSource={shares} size="small" pagination={false} columns={[
                          { title: '共享对象', dataIndex: 'shared_to_name', width: 150, render: (v: string) => <span className="font-bold">{v || '-'}</span> },
                          { title: '类型', dataIndex: 'shared_to_type', width: 80, render: (v: string) => ({ user: '用户', department: '部门', role: '角色' }[v] || v) },
                          { title: '权限', dataIndex: 'permission', width: 80, render: (v: string) => v === 'edit' ? <Tag color="blue">编辑</Tag> : <Tag>查看</Tag> },
                          { title: '共享人', dataIndex: 'shared_by_name', width: 100 },
                          { title: '', width: 60, render: (_: unknown, r: any) => (
                            <a className="text-rose-500 text-sm font-bold" onClick={async () => {
                              await customerApi.deleteShare(id!, r.id); message.success('已删除'); fetchShares()
                            }}>删除</a>
                          )},
                        ]} />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'projects',
                  label: <span className="font-semibold">商机 ({projects.length})</span>,
                  children: (
                    <div className="pb-6">
                      {projects.length === 0 ? (
                        <div className="text-center py-8 text-slate-400 text-sm">暂无关联商机</div>
                      ) : (
                        <Table rowKey="id" dataSource={projects} size="small" pagination={false} columns={[
                          { title: '项目', key: 'name', width: 200,
                            render: (_, r) => (
                              <a onClick={() => navigate(`/opportunities/${r.id}`)} className="text-sm font-bold text-primary hover:underline">
                                {r.name}
                              </a>
                            ),
                          },
                          { title: '阶段', key: 'stage', width: 100,
                            render: (_, r) => (
                              <span className={`inline-flex items-center px-2 py-0.5 rounded text-[12px] font-bold border ${stageColors[r.stage_code] || stageColors.S1}`}>
                                {r.stage_code} {stageLabels[r.stage_code]}
                              </span>
                            ),
                          },
                          { title: '预期金额', dataIndex: 'amount_expect', width: 120, align: 'right',
                            render: (v) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                          { title: '状态', dataIndex: 'status', width: 80,
                            render: (v) => (
                              <div className="flex items-center gap-1.5">
                                <span className={`w-2 h-2 rounded-full ${v === 'active' ? 'bg-blue-500' : v === 'won' ? 'bg-emerald-500' : v === 'lost' ? 'bg-red-500' : 'bg-slate-400'}`} />
                                <span className="text-sm">{v === 'active' ? '进行中' : v === 'won' ? '赢单' : v === 'lost' ? '丢单' : '暂停'}</span>
                              </div>
                            ),
                          },
                        ]} />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'tickets',
                  label: <span className="font-semibold">工单 ({tickets.length})</span>,
                  children: (
                    <div className="pb-6">
                      {tickets.length === 0 ? (
                        <div className="text-center py-8 text-slate-400 text-sm">暂无售后工单</div>
                      ) : (
                        <Table rowKey="id" dataSource={tickets} size="small" pagination={false} columns={[
                          { title: '工单号', dataIndex: 'ticket_no', width: 140,
                            render: (v: string) => <span className="font-mono text-sm font-bold">{v}</span> },
                          { title: '类型', dataIndex: 'type', width: 90, render: (v: string) => ticketTypeLabels[v] || v },
                          { title: '状态', dataIndex: 'status', width: 90,
                            render: (v: string) => {
                              const c: Record<string, string> = { open: 'blue', in_progress: 'orange', resolved: 'green', closed: 'default' }
                              return <Tag color={c[v] || 'default'}>{ticketStatusLabels[v] || v}</Tag>
                            },
                          },
                          { title: '优先级', dataIndex: 'priority', width: 80, render: (v: string) => ticketPriorityLabels[v] || v },
                          { title: '创建时间', dataIndex: 'created_at', width: 110,
                            render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                        ]} />
                      )}
                    </div>
                  ),
                },
                {
                  key: 'relation_graph',
                  label: <span className="font-semibold">关系图</span>,
                  children: (
                    <div className="pb-6">
                      <CustomerRelationGraph
                        customerId={id!}
                        customerName={customer.name}
                        contacts={contacts}
                        relations={relations}
                        allCustomers={allCustomers}
                      />
                    </div>
                  ),
                },
                {
                  key: 'attachments',
                  label: <span className="font-semibold">附件</span>,
                  children: (
                    <div className="py-4">
                      <AttachmentPanel bizType="customer" bizId={id!} />
                    </div>
                  ),
                },
                {
                  key: 'history',
                  label: <span className="font-semibold">变更历史</span>,
                  children: (
                    <div className="py-4">
                      <ChangeHistory resourceType="customer" resourceId={id!} />
                    </div>
                  ),
                },
                {
                  key: 'report',
                  label: <span className="font-semibold">客户报告</span>,
                  children: (
                    <div className="pb-6">
                      <div className="flex items-center justify-between mb-4">
                        <div className="text-sm text-slate-500">该客户关联的商机 / 报价 / 合同 / 订单 / 标书 / 回款 / 工单 / 交付</div>
                        <Button
                          icon={<span className="material-symbols-outlined text-sm mr-1">download</span>}
                          onClick={() => downloadFile(`/api/v1/customers/${id}/report/export`, `客户报告_${customer.name}.xlsx`)}
                        >
                          导出Excel
                        </Button>
                      </div>
                      {!report ? (
                        <div className="text-center py-8 text-slate-400 text-sm">加载中…</div>
                      ) : (
                        <div className="space-y-6">
                          <ReportSection title={`商机 (${report.projects.length})`} dataSource={report.projects} columns={[
                            { title: '项目编码', dataIndex: 'project_code', width: 150 },
                            { title: '名称', dataIndex: 'name' },
                            { title: '阶段', dataIndex: 'stage_code', width: 80, render: (v: string) => `${v || ''} ${stageLabels[v] || ''}` },
                            { title: '预期金额', dataIndex: 'amount_expect', width: 120, align: 'right' as const, render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                            { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => opportunityStatusMap[v]?.label || v },
                          ]} />
                          <ReportSection title={`报价 (${report.quotes.length})`} dataSource={report.quotes} columns={[
                            { title: '报价单号', dataIndex: 'quote_no', width: 170 },
                            { title: '版本', dataIndex: 'current_version_no', width: 70 },
                            { title: '金额', dataIndex: 'amount', width: 120, align: 'right' as const, render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                            { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => quoteStatusLabels[v] || v },
                          ]} />
                          <ReportSection title={`合同 (${report.contracts.length})`} dataSource={report.contracts} columns={[
                            { title: '合同编号', dataIndex: 'contract_no', width: 170 },
                            { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => contractStatusLabels[v] || v },
                            { title: '签约日期', dataIndex: 'signed_date', width: 110 },
                            { title: '金额', dataIndex: 'amount_total', width: 120, align: 'right' as const, render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                          ]} />
                          <ReportSection title={`订单 (${report.orders.length})`} dataSource={report.orders} columns={[
                            { title: '订单号', dataIndex: 'order_no', width: 160 },
                            { title: '标题', dataIndex: 'title' },
                            { title: '金额', dataIndex: 'amount', width: 120, align: 'right' as const, render: (v: number, r: any) => v != null ? `${r.currency || ''} ${Number(v).toLocaleString()}` : '-' },
                            { title: '状态', dataIndex: 'status', width: 90, render: (v: string) => orderStatusLabels[v] || v },
                            { title: '交付日期', dataIndex: 'delivery_date', width: 110 },
                          ]} />
                          <ReportSection title={`标书 (${report.tenders.length})`} dataSource={report.tenders} columns={[
                            { title: '标书号', dataIndex: 'tender_no', width: 160 },
                            { title: '标题', dataIndex: 'title' },
                            { title: '投标金额', dataIndex: 'bid_amount', width: 120, align: 'right' as const, render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                            { title: '状态', dataIndex: 'status', width: 90, render: (v: string) => tenderStatusLabels[v] || v },
                          ]} />
                          <ReportSection title={`回款记录 (${report.payment_records.length})`} dataSource={report.payment_records} columns={[
                            { title: '收款日期', dataIndex: 'received_date', width: 120 },
                            { title: '金额', dataIndex: 'amount', width: 120, align: 'right' as const, render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                            { title: '渠道', dataIndex: 'channel', width: 120 },
                            { title: '参考号', dataIndex: 'reference_no' },
                          ]} />
                          <ReportSection title={`工单 (${report.tickets.length})`} dataSource={report.tickets} columns={[
                            { title: '工单号', dataIndex: 'ticket_no', width: 150 },
                            { title: '类型', dataIndex: 'type', width: 100, render: (v: string) => ticketTypeLabels[v] || v },
                            { title: '状态', dataIndex: 'status', width: 100, render: (v: string) => ticketStatusLabels[v] || v },
                            { title: '优先级', dataIndex: 'priority', width: 90, render: (v: string) => ticketPriorityLabels[v] || v },
                          ]} />
                        </div>
                      )}
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>
      </div>

      {/* Contact Modal */}
      <Modal
        title={editingContact ? '编辑联系人' : '添加联系人'}
        open={contactModal}
        onOk={handleContactSubmit}
        onCancel={() => { setContactModal(false); setEditingContact(null); form.resetFields() }}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="姓名" rules={[{ required: true }]}><Input /></Form.Item>
          <Form.Item name="title" label="职务"><Input /></Form.Item>
          <Form.Item name="role_type" label="角色类型">
            <Select placeholder="请选择角色" allowClear
              options={Object.entries(roleTypeMap).map(([k, v]) => ({ label: v.label, value: k }))} />
          </Form.Item>
          <Form.Item name="phone" label="电话"><Input /></Form.Item>
          <Form.Item name="mobile" label="手机"><Input /></Form.Item>
          <Form.Item name="email" label="邮箱"><Input /></Form.Item>
          <Form.Item name="is_primary" label="主要联系人" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item name="reports_to_id" label="上级联系人">
            <Select placeholder="选择上级" allowClear
              options={contacts.filter((c) => c.id !== editingContact?.id).map((c) => ({ label: `${c.name}${c.title ? ' · ' + c.title : ''}`, value: c.id }))} />
          </Form.Item>
          <Form.Item name="remark" label="备注"><Input.TextArea rows={2} /></Form.Item>
          <CustomFieldsPanel entityType="contact" value={contactCustomFields} onChange={setContactCustomFields} />
        </Form>
      </Modal>

      {/* Relation Modal */}
      <Modal title="添加关联企业" open={relModal} onCancel={() => setRelModal(false)}
        onOk={async () => {
          const vals = await relForm.validateFields()
          await customerApi.createRelation(id!, vals)
          message.success('关系已创建')
          setRelModal(false)
          fetchRelations()
        }}>
        <Form form={relForm} layout="vertical">
          <Form.Item name="to_customer_id" label="关联客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select showSearch filterOption={false} placeholder="请选择客户"
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </Form.Item>
          <Form.Item name="relation_type" label="关系类型" rules={[{ required: true, message: '请选择类型' }]}>
            <Select options={[
              { label: '母公司', value: 'parent' },
              { label: '子公司', value: 'subsidiary' },
              { label: '关联企业', value: 'affiliate' },
              { label: '合作伙伴', value: 'partner' },
              { label: '竞争对手', value: 'competitor' },
            ]} />
          </Form.Item>
          <Form.Item name="note" label="备注"><Input /></Form.Item>
        </Form>
      </Modal>

      {/* Merge Modal */}
      <Modal title="合并客户" open={mergeModal} onCancel={() => setMergeModal(false)}
        okText="确认合并" okButtonProps={{ danger: true }}
        onOk={() => {
          if (!mergeTargetId) { message.warning('请选择要合并的客户'); return }
          Modal.confirm({
            title: '确认合并', okType: 'danger', okText: '确认合并',
            content: `将选中客户的所有联系人、商机、工单、关联关系合并到「${customer.name}」中，原客户将被删除。此操作不可撤销！`,
            onOk: async () => {
              await customerApi.merge(id!, mergeTargetId)
              message.success('客户合并成功')
              setMergeModal(false)
              fetchCustomer(); fetchContacts(); fetchRelations(); fetchShares(); fetchStats(); fetchProjects(); fetchTickets()
            },
          })
        }}>
        <div className="py-2">
          <div className="mb-3 p-3 bg-amber-50 rounded-lg text-sm text-amber-800 border border-amber-200">
            将选中客户的所有数据（联系人、商机、工单等）合并到当前客户「<b>{customer.name}</b>」，原客户将被删除。
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">选择要合并的客户（将被删除）</label>
            <Select className="w-full" showSearch filterOption={false} placeholder="搜索客户"
              value={mergeTargetId} onChange={setMergeTargetId}
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </div>
        </div>
      </Modal>

      {/* Share Modal */}
      <Modal title="共享客户" open={shareModal} onCancel={() => setShareModal(false)}
        onOk={async () => {
          const vals = await shareForm.validateFields()
          await customerApi.createShare(id!, vals)
          message.success('已共享')
          setShareModal(false)
          fetchShares()
        }}>
        <Form form={shareForm} layout="vertical">
          <Form.Item name="shared_to_type" label="共享类型" rules={[{ required: true }]} initialValue="user">
            <Select options={[
              { label: '用户', value: 'user' },
              { label: '角色', value: 'role' },
            ]} onChange={() => { shareForm.setFieldsValue({ shared_to_id: undefined, shared_to_name: undefined }) }} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.shared_to_type !== cur.shared_to_type}>
            {({ getFieldValue }) => {
              const type = getFieldValue('shared_to_type')
              if (type === 'user') {
                return (
                  <Form.Item name="shared_to_id" label="选择用户" rules={[{ required: true, message: '请选择用户' }]}>
                    <Select showSearch filterOption={false} placeholder="搜索并选择用户"
                      loading={userSelect.loading}
                      options={userSelect.options}
                      onSearch={userSelect.onSearch}
                      onDropdownVisibleChange={userSelect.onDropdownVisibleChange}
                      onChange={(_v, option) => {
                        shareForm.setFieldValue('shared_to_name', (option as { label: string })?.label || '')
                      }} />
                  </Form.Item>
                )
              }
              if (type === 'role') {
                return (
                  <Form.Item name="shared_to_id" label="选择角色" rules={[{ required: true, message: '请选择角色' }]}>
                    <Select showSearch optionFilterProp="label" placeholder="搜索并选择角色"
                      options={roleList.map((r) => ({ label: r.name, value: r.id }))}
                      onChange={(v) => {
                        const r = roleList.find((x) => x.id === v)
                        shareForm.setFieldValue('shared_to_name', r?.name || '')
                      }} />
                  </Form.Item>
                )
              }
              return null
            }}
          </Form.Item>
          <Form.Item name="shared_to_name" hidden><Input /></Form.Item>
          <Form.Item name="permission" label="权限" initialValue="view">
            <Select options={[
              { label: '查看', value: 'view' },
              { label: '编辑', value: 'edit' },
            ]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
