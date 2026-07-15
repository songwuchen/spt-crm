import { useState, useEffect, useRef } from 'react'
import { Button, Table, Tag, Space, Modal, Form, Input, Select, Tabs, InputNumber, DatePicker, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, UploadOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import ImportModal from '@/components/ImportModal'
import { serviceTicketApi } from '@/api/serviceTicket'
import { useCustomerSelect, useUserSelect } from '@/hooks/useSelectOptions'
import type { ServiceTicketItem, RenewalItem } from '@/api/types'

import { ticketTypeLabels as typeLabels, ticketPriorityLabels as priorityLabels, ticketPriorityColors as priorityColors, ticketStatusColors as statusColors, ticketStatusLabels as statusLabels, renewalStatusLabels, renewalStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'
import EntityCustomFields from '@/components/lowcode/EntityCustomFields'
import { t } from '@/locales'

const { TextArea } = Input

interface SlaStats {
  open_tickets: number
  resolved_tickets: number
  breach_count: number
  near_breach_count: number
  on_time_rate: number
  sla_config: Record<string, number>
  by_priority: Record<string, number>
}

export default function ServiceTicketList() {
  usePageTitle(t('service.pageTitle'))
  const navigate = useNavigate()
  const [slaStats, setSlaStats] = useState<SlaStats | null>(null)
  const [tickets, setTickets] = useState<ServiceTicketItem[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)
  const [createModal, setCreateModal] = useState(false)
  const [importModal, setImportModal] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({ type: 'fault', priority: 'medium', description: '' })
  const [ticketCustomFields, setTicketCustomFields] = useState<Record<string, unknown>>({})
  const customerSelect = useCustomerSelect()

  // 关联订单（可选）——按所选客户过滤，便于售后获取产品信息
  const [orderOpts, setOrderOpts] = useState<{ label: string; value: string }[]>([])
  const [orderLoading, setOrderLoading] = useState(false)
  const searchOrders = async (kw?: string, customerId?: string) => {
    setOrderLoading(true)
    try {
      // 走售后专用的 order_options 端点（service 权限即可），修复 issue #85：
      // 原先直接调订单列表需 order:view，售后/无订单权限的角色会报「缺少权限」
      const r = await serviceTicketApi.orderOptions({ keyword: kw || undefined, customer_id: customerId || undefined }) as any
      setOrderOpts((r.data?.items || []).map((o: any) => ({ label: `${o.order_no}${o.title ? ' · ' + o.title : ''}`, value: o.id })))
    } catch { /* ignore */ } finally { setOrderLoading(false) }
  }

  // Filters
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined)
  const [filterPriority, setFilterPriority] = useState<string | undefined>(undefined)
  const [filterType, setFilterType] = useState<string | undefined>(undefined)
  const [searchText, setSearchText] = useState('')
  const [selectedTicketKeys, setSelectedTicketKeys] = useState<React.Key[]>([])
  const [batchAssignModal, setBatchAssignModal] = useState(false)
  const [assignForm] = Form.useForm()
  const assignUserSelect = useUserSelect()

  const handleBatchAssign = async () => {
    const values = await assignForm.validateFields()
    const userName = assignUserSelect.options.find(o => o.value === values.assigned_to_id)?.label || ''
    const results = await Promise.allSettled(
      selectedTicketKeys.map((id) => serviceTicketApi.update(id as string, { assigned_to_id: values.assigned_to_id, assigned_to_name: userName }))
    )
    const ok = results.filter(r => r.status === 'fulfilled').length
    message.success(t('service.batchAssignDone', { count: ok }))
    setBatchAssignModal(false)
    assignForm.resetFields()
    setSelectedTicketKeys([])
    fetchTickets()
  }

  // Renewals
  const [renewals, setRenewals] = useState<RenewalItem[]>([])
  const [renewalModal, setRenewalModal] = useState(false)
  const [renewalForm, setRenewalForm] = useState<Record<string, any>>({ status: 'open' })
  const [editingRenewal, setEditingRenewal] = useState<RenewalItem | null>(null)

  const fetchTickets = async (page = pageNo, kw = searchText, st = filterStatus, pri = filterPriority, tp = filterType) => {
    setLoading(true)
    try {
      const r = await serviceTicketApi.list({
        pageNo: page, pageSize: 20,
        keyword: kw || undefined, status: st, priority: pri, type: tp,
        ...view.buildParams(),
      })
      setTickets(r.data?.items || [])
      setTotal(r.data?.total || 0)
    } finally {
      setLoading(false)
    }
  }

  const fetchRenewals = async () => {
    const r = await serviceTicketApi.listRenewals()
    setRenewals(r.data || [])
  }

  const fetchSlaStats = async () => {
    try {
      const r = await serviceTicketApi.slaStats() as any
      setSlaStats(r.data || null)
    } catch { /* ignore */ }
  }

  const ticketColumns: import('antd/es/table').ColumnsType<ServiceTicketItem> = [
    { title: t('service.ticketNo'), dataIndex: 'ticket_no', render: (v: string, r: ServiceTicketItem) => (
      <a className="font-mono font-bold text-primary cursor-pointer" onClick={() => navigate(`/service-tickets/${r.id}`)}>{v}</a>
    )},
    { title: '客户名称', dataIndex: 'customer_name', ellipsis: true, render: (v: string) => v || '-' },
    { title: '订单名称', dataIndex: 'order_name', ellipsis: true, render: (v: string) => v || '-' },
    { title: t('service.type'), dataIndex: 'type', render: (v: string) => typeLabels[v] || v },
    { title: t('service.priority'), dataIndex: 'priority', render: (v: string) => <Tag color={priorityColors[v]}>{priorityLabels[v] || v}</Tag> },
    { title: t('common.status'), dataIndex: 'status', render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v] || v}</Tag> },
    { title: t('service.description'), dataIndex: 'description', ellipsis: true, width: 200 },
    { title: t('common.owner'), dataIndex: 'assigned_to_name', render: (v: string) => v || '-' },
    { title: t('common.createdBy'), dataIndex: 'created_by_name', responsive: ['lg'] as any },
    { title: t('common.createdAt'), dataIndex: 'created_at', responsive: ['xl'] as any, render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
  ]

  const view = useListView<ServiceTicketItem>('service_ticket', ticketColumns, { pageKey: 'service_tickets' })

  useEffect(() => { fetchTickets(); fetchRenewals(); fetchSlaStats() }, [])

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchTickets(1)
  }, [reload])

  const handleCreate = async () => {
    if (!form.description?.trim()) {
      message.warning(t('service.descriptionRequired'))
      return
    }
    try {
      const data: Record<string, any> = { ...form, custom_fields_json: ticketCustomFields }
      if (!data.customer_id) delete data.customer_id
      await serviceTicketApi.create(data)
      message.success(t('service.ticketCreated'))
      setCreateModal(false)
      setForm({ type: 'fault', priority: 'medium', description: '' })
      fetchTickets()
    } catch {
      message.error(t('service.ticketCreateFailed'))
    }
  }

  const openCreate = () => {
    setForm({ type: 'fault', priority: 'medium', description: '' })
    setTicketCustomFields({})
    setCreateModal(true)
  }

  const openRenewalCreate = () => {
    setEditingRenewal(null)
    setRenewalForm({ status: 'open' })
    setRenewalModal(true)
  }

  const openRenewalEdit = (r: RenewalItem) => {
    setEditingRenewal(r)
    setRenewalForm({
      customer_id: r.customer_id,
      name: r.name,
      amount_expect: r.amount_expect,
      close_date_expect: r.close_date_expect,
      probability: r.probability,
      status: r.status,
      remark: r.remark,
    })
    setRenewalModal(true)
  }

  const handleRenewalSave = async () => {
    const data = { ...renewalForm }
    if (data.close_date_expect && dayjs.isDayjs(data.close_date_expect)) {
      data.close_date_expect = data.close_date_expect.format('YYYY-MM-DD')
    }
    if (editingRenewal) {
      await serviceTicketApi.updateRenewal(editingRenewal.id, data)
      message.success(t('service.renewalUpdated'))
    } else {
      await serviceTicketApi.createRenewal(data)
      message.success(t('service.renewalCreated'))
    }
    setRenewalModal(false)
    setEditingRenewal(null)
    setRenewalForm({ status: 'open' })
    fetchRenewals()
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">{t('service.pageTitle')}</h1>
          <p className="text-sm text-slate-500 mt-1">{t('service.pageSubtitle')}</p>
        </div>
      </div>

      {/* SLA Dashboard */}
      {slaStats && (
        <div className="mb-4 space-y-3">
          {/* SLA Stats Row */}
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[140px] bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm text-slate-500 mb-1">{t('service.slaRate')}</div>
              <div className={`text-2xl font-black ${slaStats.on_time_rate >= 90 ? 'text-emerald-600' : slaStats.on_time_rate >= 70 ? 'text-amber-600' : 'text-red-600'}`}>
                {slaStats.on_time_rate}%
              </div>
              <div className="mt-2 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div className={`h-full rounded-full transition-all ${slaStats.on_time_rate >= 90 ? 'bg-emerald-500' : slaStats.on_time_rate >= 70 ? 'bg-amber-500' : 'bg-red-500'}`}
                  style={{ width: `${Math.min(100, slaStats.on_time_rate)}%` }} />
              </div>
            </div>
            <div className="flex-1 min-w-[140px] bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm text-slate-500 mb-1">{t('service.openTickets')}</div>
              <div className="text-2xl font-black text-blue-600">{slaStats.open_tickets}</div>
            </div>
            <div className="flex-1 min-w-[140px] bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm text-slate-500 mb-1">{t('service.breached')}</div>
              <div className={`text-2xl font-black ${slaStats.breach_count > 0 ? 'text-red-600' : 'text-slate-400'}`}>
                {slaStats.breach_count}
              </div>
            </div>
            <div className="flex-1 min-w-[140px] bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm text-slate-500 mb-1">{t('service.nearBreach')}</div>
              <div className={`text-2xl font-black ${slaStats.near_breach_count > 0 ? 'text-amber-600' : 'text-slate-400'}`}>
                {slaStats.near_breach_count}
              </div>
            </div>
            <div className="flex-1 min-w-[140px] bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm text-slate-500 mb-1">{t('service.resolved')}</div>
              <div className="text-2xl font-black text-emerald-600">{slaStats.resolved_tickets}</div>
            </div>
          </div>

          {/* Priority Distribution + SLA Config */}
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[280px] bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-3">{t('service.priorityDistribution')}</div>
              {(() => {
                const prios = slaStats.by_priority || {}
                const maxVal = Math.max(...Object.values(prios), 1)
                const colors: Record<string, string> = { critical: 'bg-red-500', high: 'bg-orange-500', medium: 'bg-blue-500', low: 'bg-slate-400' }
                return (
                  <div className="space-y-2">
                    {['critical', 'high', 'medium', 'low'].map((p) => (
                      <div key={p} className="flex items-center gap-2">
                        <span className="text-sm text-slate-500 w-12">{priorityLabels[p] || p}</span>
                        <div className="flex-1 h-5 bg-slate-100 rounded overflow-hidden">
                          <div className={`h-full rounded ${colors[p] || 'bg-slate-300'} transition-all`}
                            style={{ width: `${((prios[p] || 0) / maxVal) * 100}%`, minWidth: prios[p] ? 16 : 0 }} />
                        </div>
                        <span className="text-sm font-bold text-slate-700 w-8 text-right">{prios[p] || 0}</span>
                      </div>
                    ))}
                  </div>
                )
              })()}
            </div>
            <div className="flex-1 min-w-[280px] bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-3">{t('service.slaResponseTime')}</div>
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(slaStats.sla_config || {}).map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between bg-slate-50 rounded-lg px-3 py-2 border border-slate-100">
                    <span className="text-sm text-slate-600">{priorityLabels[k] || k}</span>
                    <span className="text-sm font-bold text-slate-800">{v}h</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <Tabs defaultActiveKey="tickets" className="px-4 pt-2" items={[
          {
            key: 'tickets',
            label: t('service.ticketsTab'),
            children: (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <Input prefix={<SearchOutlined />} placeholder={t('service.searchNoDesc')} allowClear
                      value={searchText} onChange={(e) => setSearchText(e.target.value)}
                      onPressEnter={() => { setPageNo(1); fetchTickets(1, searchText, filterStatus, filterPriority, filterType) }}
                      style={{ width: 220 }} />
                    <Select allowClear placeholder={t('common.status')} value={filterStatus}
                      onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchTickets(1, searchText, v, filterPriority, filterType) }}
                      style={{ width: 130 }} options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v }))} />
                    <Select allowClear placeholder={t('service.priority')} value={filterPriority}
                      onChange={(v) => { setFilterPriority(v); setPageNo(1); fetchTickets(1, searchText, filterStatus, v, filterType) }}
                      style={{ width: 130 }} options={Object.entries(priorityLabels).map(([k, v]) => ({ value: k, label: v }))} />
                    <Select allowClear placeholder={t('service.type')} value={filterType}
                      onChange={(v) => { setFilterType(v); setPageNo(1); fetchTickets(1, searchText, filterStatus, filterPriority, v) }}
                      style={{ width: 130 }} options={Object.entries(typeLabels).map(([k, v]) => ({ value: k, label: v }))} />
                    <ListToolbar resource="service_ticket" view={view} onChange={() => setReload((r) => r + 1)} />
                  </div>
                  <Space wrap>
                    {selectedTicketKeys.length > 0 && (
                      <Button onClick={() => { assignForm.resetFields(); setBatchAssignModal(true) }}>
                        {t('service.batchAssign', { count: selectedTicketKeys.length })}
                      </Button>
                    )}
                    <Button icon={<UploadOutlined />} onClick={() => setImportModal(true)}>{t('common.import')}</Button>
                    <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/service_tickets/export/excel', 'service_tickets.xlsx')}>{t('common.export')}</Button>
                    <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>{t('service.createTicket')}</Button>
                  </Space>
                </div>
                <Table rowKey="id" dataSource={tickets} loading={loading} size="small" scroll={{ x: 1200 }}
                  rowSelection={{ selectedRowKeys: selectedTicketKeys, onChange: setSelectedTicketKeys }}
                  pagination={{
                    current: pageNo, total, pageSize: 20, showTotal: (total) => t('common.totalCount', { count: total }),
                    onChange: (p) => { setPageNo(p); fetchTickets(p) },
                  }}
                  columns={view.columns}
                />
              </div>
            ),
          },
          {
            key: 'renewals',
            label: t('service.renewalsTab', { count: renewals.length }),
            children: (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    {['open', 'won', 'lost'].map((s) => {
                      const cnt = renewals.filter((r) => r.status === s).length
                      return (
                        <Tag key={s} color={renewalStatusColors[s]}>
                          {renewalStatusLabels[s]} {cnt}
                        </Tag>
                      )
                    })}
                    <span className="text-sm text-slate-400 ml-2">
                      {t('service.estimatedAmount')} ¥{renewals.filter((r) => r.status === 'open').reduce((sum, r) => sum + (r.amount_expect || 0), 0).toLocaleString()}
                    </span>
                  </div>
                  <Button type="primary" icon={<PlusOutlined />} onClick={openRenewalCreate}>{t('service.createRenewal')}</Button>
                </div>
                <Table rowKey="id" dataSource={renewals} pagination={{ pageSize: 20 }} size="small"
                  columns={[
                    { title: t('service.renewalName'), dataIndex: 'name', render: (v: string) => <span className="font-semibold">{v}</span> },
                    { title: t('common.status'), dataIndex: 'status', width: 100, render: (v: string) => <Tag color={renewalStatusColors[v]}>{renewalStatusLabels[v] || v}</Tag> },
                    { title: t('service.expectedAmount'), dataIndex: 'amount_expect', width: 130, render: (v: number | null) => v != null ? `¥${v.toLocaleString()}` : '-' },
                    { title: t('service.expectedCloseDate'), dataIndex: 'close_date_expect', width: 120, render: (v: string) => v || '-' },
                    { title: t('service.probability'), dataIndex: 'probability', width: 80, render: (v: number | null) => v != null ? `${v}%` : '-' },
                    { title: t('common.owner'), dataIndex: 'owner_name', width: 100, render: (v: string) => v || '-' },
                    { title: t('common.remark'), dataIndex: 'remark', ellipsis: true, width: 180 },
                    { title: t('common.createdAt'), dataIndex: 'created_at', width: 110, render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                    { title: '', key: 'actions', width: 60, render: (_: unknown, r: RenewalItem) => (
                      <a className="text-primary text-sm font-bold" onClick={() => openRenewalEdit(r)}>{t('common.edit')}</a>
                    )},
                  ]}
                />
              </div>
            ),
          },
        ]} />
      </div>

      {/* Import Modal */}
      <ImportModal
        open={importModal}
        onClose={() => setImportModal(false)}
        onSuccess={() => fetchTickets()}
        previewUrl="/api/v1/service_tickets/import/preview"
        importUrl="/api/v1/service_tickets/import/excel"
        templateUrl="/api/v1/service_tickets/import/template"
        title="导入售后工单"
        expectedHeaders={['工单类型', '优先级', '关联客户', '关联订单号', '负责人', '问题描述']}
      />

      {/* Create Ticket Modal */}
      <Modal title={t('service.createTicketTitle')} open={createModal} onOk={handleCreate} onCancel={() => setCreateModal(false)} width={500}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.relatedCustomer')}</label>
            <Select className="w-full" allowClear showSearch filterOption={false} placeholder={t('service.relatedCustomerPlaceholder')}
              value={form.customer_id} onChange={(v) => setForm({ ...form, customer_id: v, order_id: undefined })}
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">关联订单（选填，便于获取产品信息）</label>
            <Select className="w-full" allowClear showSearch filterOption={false} placeholder="搜索订单号 / 标题"
              value={form.order_id} onChange={(v) => setForm({ ...form, order_id: v })}
              loading={orderLoading} options={orderOpts}
              onSearch={(kw) => searchOrders(kw, form.customer_id)}
              onDropdownVisibleChange={(o) => { if (o) searchOrders(undefined, form.customer_id) }} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.type')}</label>
              <Select className="w-full" value={form.type} onChange={(v) => setForm({ ...form, type: v })}
                options={Object.entries(typeLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.priority')}</label>
              <Select className="w-full" value={form.priority} onChange={(v) => setForm({ ...form, priority: v })}
                options={Object.entries(priorityLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.description')}</label>
            <TextArea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder={t('service.descriptionPlaceholder')} />
          </div>
          <EntityCustomFields entityType="service_ticket" value={ticketCustomFields} onChange={setTicketCustomFields} />
        </div>
      </Modal>

      {/* Renewal Modal */}
      <Modal title={editingRenewal ? t('service.editRenewal') : t('service.createRenewal')} open={renewalModal}
        onOk={handleRenewalSave} onCancel={() => { setRenewalModal(false); setEditingRenewal(null) }} width={500}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.relatedCustomer')} <span className="text-red-500">*</span></label>
            <Select className="w-full" showSearch filterOption={false} placeholder={t('service.customer')}
              value={renewalForm.customer_id} onChange={(v) => setRenewalForm({ ...renewalForm, customer_id: v })}
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.renewalName')} <span className="text-red-500">*</span></label>
            <Input value={renewalForm.name} onChange={(e) => setRenewalForm({ ...renewalForm, name: e.target.value })} placeholder={t('service.renewalNamePlaceholder')} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.expectedAmount')}</label>
              <InputNumber className="w-full" min={0} prefix="¥" value={renewalForm.amount_expect}
                onChange={(v) => setRenewalForm({ ...renewalForm, amount_expect: v })} placeholder="0" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.expectedCloseDate')}</label>
              <DatePicker className="w-full" value={renewalForm.close_date_expect ? dayjs(renewalForm.close_date_expect) : null}
                onChange={(v) => setRenewalForm({ ...renewalForm, close_date_expect: v })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">{t('service.probabilityPercent')}</label>
              <InputNumber className="w-full" min={0} max={100} value={renewalForm.probability}
                onChange={(v) => setRenewalForm({ ...renewalForm, probability: v })} placeholder="50" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">{t('common.status')}</label>
              <Select className="w-full" value={renewalForm.status} onChange={(v) => setRenewalForm({ ...renewalForm, status: v })}
                options={Object.entries(renewalStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">{t('common.remark')}</label>
            <TextArea rows={2} value={renewalForm.remark} onChange={(e) => setRenewalForm({ ...renewalForm, remark: e.target.value })} placeholder={t('service.remarkPlaceholder')} />
          </div>
        </div>
      </Modal>

      {/* Batch Assign Modal */}
      <Modal title={t('service.batchAssignTitle')} open={batchAssignModal} onOk={handleBatchAssign}
        onCancel={() => setBatchAssignModal(false)} okText={t('service.confirmAssign')}>
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            {t('service.batchAssignMsg', { count: selectedTicketKeys.length })}
          </div>
          <Form form={assignForm} layout="vertical">
            <Form.Item name="assigned_to_id" label={t('common.owner')} rules={[{ required: true, message: t('service.selectUser') }]}>
              <Select showSearch filterOption={false} placeholder={t('service.searchUser')}
                loading={assignUserSelect.loading} options={assignUserSelect.options}
                onSearch={assignUserSelect.onSearch} onDropdownVisibleChange={assignUserSelect.onDropdownVisibleChange} />
            </Form.Item>
          </Form>
        </div>
      </Modal>
    </div>
  )
}
