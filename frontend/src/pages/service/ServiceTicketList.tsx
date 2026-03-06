import { useState, useEffect } from 'react'
import { Button, Table, Tag, Space, Modal, Input, Select, Tabs, InputNumber, DatePicker, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { serviceTicketApi } from '@/api/serviceTicket'
import { customerApi } from '@/api/customer'
import type { ServiceTicketItem, RenewalItem, Customer } from '@/api/types'

import { ticketTypeLabels as typeLabels, ticketPriorityLabels as priorityLabels, ticketPriorityColors as priorityColors, ticketStatusColors as statusColors, ticketStatusLabels as statusLabels, renewalStatusLabels, renewalStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'

const { TextArea } = Input

export default function ServiceTicketList() {
  usePageTitle('售后工单')
  const navigate = useNavigate()
  const [tickets, setTickets] = useState<ServiceTicketItem[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [createModal, setCreateModal] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({ type: 'fault', priority: 'medium', description: '' })
  const [customers, setCustomers] = useState<Customer[]>([])

  // Filters
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined)
  const [searchText, setSearchText] = useState('')

  // Renewals
  const [renewals, setRenewals] = useState<RenewalItem[]>([])
  const [renewalModal, setRenewalModal] = useState(false)
  const [renewalForm, setRenewalForm] = useState<Record<string, any>>({ status: 'open' })
  const [editingRenewal, setEditingRenewal] = useState<RenewalItem | null>(null)

  const fetchTickets = async (page = pageNo, kw = searchText, st = filterStatus) => {
    setLoading(true)
    try {
      const r = await serviceTicketApi.list({
        pageNo: page, pageSize: 20,
        keyword: kw || undefined, status: st,
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

  useEffect(() => { fetchTickets(); fetchRenewals() }, [])

  const fetchCustomers = async () => {
    try {
      const r = await customerApi.list({ pageNo: 1, pageSize: 100 })
      setCustomers(r.data?.items || [])
    } catch {}
  }

  const handleCreate = async () => {
    if (!form.description?.trim()) {
      message.warning('请填写问题描述')
      return
    }
    try {
      const data = { ...form }
      if (!data.customer_id) delete data.customer_id
      await serviceTicketApi.create(data)
      message.success('工单已创建')
      setCreateModal(false)
      setForm({ type: 'fault', priority: 'medium', description: '' })
      fetchTickets()
    } catch {
      message.error('创建工单失败')
    }
  }

  const openCreate = () => {
    fetchCustomers()
    setForm({ type: 'fault', priority: 'medium', description: '' })
    setCreateModal(true)
  }

  const openRenewalCreate = () => {
    fetchCustomers()
    setEditingRenewal(null)
    setRenewalForm({ status: 'open' })
    setRenewalModal(true)
  }

  const openRenewalEdit = (r: RenewalItem) => {
    fetchCustomers()
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
      message.success('续约机会已更新')
    } else {
      await serviceTicketApi.createRenewal(data)
      message.success('续约机会已创建')
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
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">售后服务</h1>
          <p className="text-sm text-slate-500 mt-1">管理售后工单与续约/复购机会</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <Tabs defaultActiveKey="tickets" className="px-4 pt-2" items={[
          {
            key: 'tickets',
            label: '售后工单',
            children: (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3 flex-wrap">
                    <Input prefix={<SearchOutlined />} placeholder="搜索编号/描述" allowClear
                      value={searchText} onChange={(e) => setSearchText(e.target.value)}
                      onPressEnter={() => { setPageNo(1); fetchTickets(1, searchText, filterStatus) }}
                      style={{ width: 220 }} />
                    <Select allowClear placeholder="状态" value={filterStatus}
                      onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchTickets(1, searchText, v) }}
                      style={{ width: 130 }} options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v }))} />
                  </div>
                  <Space>
                    <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/service_tickets/export/excel', 'service_tickets.xlsx')}>导出</Button>
                    <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建工单</Button>
                  </Space>
                </div>
                <Table rowKey="id" dataSource={tickets} loading={loading} size="small" scroll={{ x: 900 }}
                  pagination={{
                    current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
                    onChange: (p) => { setPageNo(p); fetchTickets(p) },
                  }}
                  columns={[
                    { title: '工单编号', dataIndex: 'ticket_no', render: (v: string, r: ServiceTicketItem) => (
                      <a className="font-mono font-bold text-primary cursor-pointer" onClick={() => navigate(`/service-tickets/${r.id}`)}>{v}</a>
                    )},
                    { title: '类型', dataIndex: 'type', render: (v: string) => typeLabels[v] || v },
                    { title: '优先级', dataIndex: 'priority', render: (v: string) => <Tag color={priorityColors[v]}>{priorityLabels[v] || v}</Tag> },
                    { title: '状态', dataIndex: 'status', render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v] || v}</Tag> },
                    { title: '描述', dataIndex: 'description', ellipsis: true, width: 200 },
                    { title: '负责人', dataIndex: 'assigned_to_name', render: (v: string) => v || '-' },
                    { title: '创建人', dataIndex: 'created_by_name', responsive: ['lg'] as any },
                    { title: '创建时间', dataIndex: 'created_at', responsive: ['xl'] as any, render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                  ]}
                />
              </div>
            ),
          },
          {
            key: 'renewals',
            label: `续约/复购 (${renewals.length})`,
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
                    <span className="text-xs text-slate-400 ml-2">
                      预计金额: ¥{renewals.filter((r) => r.status === 'open').reduce((sum, r) => sum + (r.amount_expect || 0), 0).toLocaleString()}
                    </span>
                  </div>
                  <Button type="primary" icon={<PlusOutlined />} onClick={openRenewalCreate}>新建续约机会</Button>
                </div>
                <Table rowKey="id" dataSource={renewals} pagination={{ pageSize: 20 }} size="small"
                  columns={[
                    { title: '名称', dataIndex: 'name', render: (v: string) => <span className="font-semibold">{v}</span> },
                    { title: '状态', dataIndex: 'status', width: 100, render: (v: string) => <Tag color={renewalStatusColors[v]}>{renewalStatusLabels[v] || v}</Tag> },
                    { title: '预计金额', dataIndex: 'amount_expect', width: 130, render: (v: number | null) => v != null ? `¥${v.toLocaleString()}` : '-' },
                    { title: '预计关闭', dataIndex: 'close_date_expect', width: 120, render: (v: string) => v || '-' },
                    { title: '概率', dataIndex: 'probability', width: 80, render: (v: number | null) => v != null ? `${v}%` : '-' },
                    { title: '负责人', dataIndex: 'owner_name', width: 100, render: (v: string) => v || '-' },
                    { title: '备注', dataIndex: 'remark', ellipsis: true, width: 180 },
                    { title: '创建时间', dataIndex: 'created_at', width: 110, render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                    { title: '', key: 'actions', width: 60, render: (_: unknown, r: RenewalItem) => (
                      <a className="text-primary text-xs font-bold" onClick={() => openRenewalEdit(r)}>编辑</a>
                    )},
                  ]}
                />
              </div>
            ),
          },
        ]} />
      </div>

      {/* Create Ticket Modal */}
      <Modal title="新建售后工单" open={createModal} onOk={handleCreate} onCancel={() => setCreateModal(false)} width={500}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">关联客户</label>
            <Select className="w-full" allowClear showSearch optionFilterProp="label" placeholder="选择关联客户（可选）"
              value={form.customer_id} onChange={(v) => setForm({ ...form, customer_id: v })}
              options={customers.map((c) => ({ value: c.id, label: c.name }))} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">类型</label>
              <Select className="w-full" value={form.type} onChange={(v) => setForm({ ...form, type: v })}
                options={Object.entries(typeLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">优先级</label>
              <Select className="w-full" value={form.priority} onChange={(v) => setForm({ ...form, priority: v })}
                options={Object.entries(priorityLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">描述</label>
            <TextArea rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="描述问题..." />
          </div>
        </div>
      </Modal>

      {/* Renewal Modal */}
      <Modal title={editingRenewal ? '编辑续约机会' : '新建续约机会'} open={renewalModal}
        onOk={handleRenewalSave} onCancel={() => { setRenewalModal(false); setEditingRenewal(null) }} width={500}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">关联客户 <span className="text-red-500">*</span></label>
            <Select className="w-full" showSearch optionFilterProp="label" placeholder="选择客户"
              value={renewalForm.customer_id} onChange={(v) => setRenewalForm({ ...renewalForm, customer_id: v })}
              options={customers.map((c) => ({ value: c.id, label: c.name }))} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">名称 <span className="text-red-500">*</span></label>
            <Input value={renewalForm.name} onChange={(e) => setRenewalForm({ ...renewalForm, name: e.target.value })} placeholder="续约/复购名称" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">预计金额</label>
              <InputNumber className="w-full" min={0} prefix="¥" value={renewalForm.amount_expect}
                onChange={(v) => setRenewalForm({ ...renewalForm, amount_expect: v })} placeholder="0" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">预计关闭日期</label>
              <DatePicker className="w-full" value={renewalForm.close_date_expect ? dayjs(renewalForm.close_date_expect) : null}
                onChange={(v) => setRenewalForm({ ...renewalForm, close_date_expect: v })} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">概率 (%)</label>
              <InputNumber className="w-full" min={0} max={100} value={renewalForm.probability}
                onChange={(v) => setRenewalForm({ ...renewalForm, probability: v })} placeholder="50" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">状态</label>
              <Select className="w-full" value={renewalForm.status} onChange={(v) => setRenewalForm({ ...renewalForm, status: v })}
                options={Object.entries(renewalStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">备注</label>
            <TextArea rows={2} value={renewalForm.remark} onChange={(e) => setRenewalForm({ ...renewalForm, remark: e.target.value })} placeholder="备注信息..." />
          </div>
        </div>
      </Modal>
    </div>
  )
}
