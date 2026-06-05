import { useState, useEffect } from 'react'
import {
  Tabs, Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, message, Tag, Statistic,
} from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, BellOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { collectionApi } from '@/api/collection'
import type { ArAgingRow, DebtTransfer } from '@/api/types'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useCustomerSelect } from '@/hooks/useSelectOptions'

const BUCKETS = [
  { key: 'd0_30', label: '0-30天', color: '#10b981' },
  { key: 'd31_60', label: '31-60天', color: '#22c55e' },
  { key: 'd61_90', label: '61-90天', color: '#f59e0b' },
  { key: 'd91_180', label: '91-180天', color: '#f97316' },
  { key: 'd180p', label: '180天+', color: '#ef4444' },
]
const TYPE_OPTIONS = [
  { label: '销售转清欠', value: 'sales_to_collection' },
  { label: '清欠转回销售', value: 'collection_to_sales' },
  { label: '转法务', value: 'to_legal' },
  { label: '部门间移交', value: 'dept_to_dept' },
  { label: '财务转诉讼', value: 'finance_to_litigation' },
]
const TYPE_LABEL: Record<string, string> = Object.fromEntries(TYPE_OPTIONS.map(o => [o.value, o.label]))
const STATUS_OPTIONS = [
  { label: '待接收', value: 'pending' },
  { label: '已接收', value: 'claimed' },
  { label: '已撤回', value: 'withdrawn' },
  { label: '已完成', value: 'done' },
]
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS_OPTIONS.map(o => [o.value, o.label]))
const STATUS_COLOR: Record<string, string> = { pending: 'gold', claimed: 'blue', withdrawn: 'default', done: 'green', rejected: 'red' }

const money = (v?: number) => (v ? `¥${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}` : '-')

function AgingTab() {
  const [rows, setRows] = useState<ArAgingRow[]>([])
  const [summary, setSummary] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await collectionApi.aging()
      setRows(res.data.rows || [])
      setSummary(res.data.summary || {})
    } finally { setLoading(false) }
  }
  useEffect(() => { fetchData() }, [])

  const notify = async () => {
    try { const r = await collectionApi.agingNotify(); message.success(`已提醒 ${r.data.notified} 位负责人`) }
    catch { message.error('提醒失败') }
  }

  const columns: ColumnsType<ArAgingRow> = [
    { title: '客户', dataIndex: 'customer_name', width: 200, fixed: 'left', ellipsis: true },
    { title: '负责人', dataIndex: 'owner_name', width: 90, render: (v) => v || '-' },
    { title: '合同应收', dataIndex: 'contract_total', width: 120, align: 'right', render: money },
    { title: '已回款', dataIndex: 'received_total', width: 120, align: 'right', render: money },
    { title: '应收余额', dataIndex: 'outstanding', width: 130, align: 'right', render: (v) => <span className="font-semibold text-slate-900">{money(v)}</span> },
    ...BUCKETS.map((b) => ({
      title: b.label, dataIndex: b.key, width: 110, align: 'right' as const,
      render: (v: number) => v ? <span style={{ color: b.color, fontWeight: 600 }}>{money(v)}</span> : <span className="text-slate-300">-</span>,
    })),
  ]

  return (
    <div>
      <div className="grid grid-cols-6 gap-3 mb-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-3 col-span-1">
          <Statistic title="应收余额" value={summary.outstanding || 0} precision={0} prefix="¥" valueStyle={{ color: '#0f172a', fontSize: 18 }} />
        </div>
        {BUCKETS.map((b) => (
          <div key={b.key} className="bg-white rounded-xl border border-slate-200 shadow-sm p-3">
            <div className="text-xs text-slate-500 mb-1">{b.label}</div>
            <div className="text-lg font-bold" style={{ color: b.color }}>{money(summary[b.key])}</div>
          </div>
        ))}
      </div>
      <div className="flex justify-end mb-3">
        <Space>
          <Button icon={<BellOutlined />} onClick={notify}>提醒逾期负责人</Button>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/collection/aging/export/excel', 'ar_aging.xlsx')}>导出账龄</Button>
        </Space>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey={(r) => r.customer_id || r.customer_name} columns={columns} dataSource={rows} loading={loading}
          scroll={{ x: 1200 }} pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 个客户` }} />
      </div>
    </div>
  )
}

function TransferTab() {
  const [data, setData] = useState<DebtTransfer[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()
  const [claimTarget, setClaimTarget] = useState<DebtTransfer | null>(null)
  const [claimForm] = Form.useForm()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await collectionApi.listTransfers({ pageNo: p, pageSize, keyword: keyword || undefined, status })
      setData(res.data.items); setTotal(res.data.total)
    } finally { setLoading(false) }
  }
  useEffect(() => { fetchData(1); setPage(1) }, [status]) // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => { form.resetFields(); form.setFieldsValue({ transfer_type: 'sales_to_collection' }); setModalOpen(true) }

  const handleCreate = async () => {
    let values
    try { values = await form.validateFields() } catch { return }
    const payload: Record<string, unknown> = {
      ...values,
      deadline: values.deadline ? values.deadline.format('YYYY-MM-DD') : undefined,
      assess_date: values.assess_date ? values.assess_date.format('YYYY-MM-DD') : undefined,
    }
    if (values.customer_id) {
      const opt = customerSelect.options.find((o) => o.value === values.customer_id)
      if (opt) payload.customer_name = opt.label
    }
    try { await collectionApi.createTransfer(payload); message.success('已创建移交单'); setModalOpen(false); fetchData() }
    catch { message.error('创建失败') }
  }

  const doClaim = async () => {
    if (!claimTarget) return
    const values = await claimForm.validateFields().catch(() => null)
    if (!values) return
    try { await collectionApi.claim(claimTarget.id, values); message.success('已接收（抢单成功）'); setClaimTarget(null); fetchData() }
    catch (e: any) { message.error(e?.message || '接收失败') }
  }

  const doWithdraw = (r: DebtTransfer) => Modal.confirm({
    title: '撤回移交单', content: `确认撤回 ${r.transfer_no}？`,
    onOk: async () => { await collectionApi.withdraw(r.id); message.success('已撤回'); fetchData() },
  })
  const doDelete = (r: DebtTransfer) => Modal.confirm({
    title: '删除移交单', content: `确认删除 ${r.transfer_no}？`, okType: 'danger',
    onOk: async () => { await collectionApi.deleteTransfer(r.id); message.success('已删除'); fetchData() },
  })

  const columns: ColumnsType<DebtTransfer> = [
    { title: '编号', dataIndex: 'transfer_no', width: 150, fixed: 'left', render: (v) => <span className="font-mono text-xs">{v}</span> },
    { title: '客户', dataIndex: 'customer_name', width: 180, ellipsis: true, render: (v) => v || '-' },
    { title: '类型', dataIndex: 'transfer_type', width: 120, render: (v) => TYPE_LABEL[v] || v },
    { title: '欠款余额', dataIndex: 'debt_amount', width: 120, align: 'right', render: money },
    { title: '原负责人', dataIndex: 'from_owner_name', width: 90, render: (v) => v || '-' },
    { title: '目标部门', dataIndex: 'to_department_name', width: 120, render: (v) => v || '-' },
    { title: '状态', dataIndex: 'status', width: 90, render: (v) => <Tag color={STATUS_COLOR[v] || 'default'}>{STATUS_LABEL[v] || v}</Tag> },
    { title: '接收人', dataIndex: 'claimed_by_name', width: 90, render: (v) => v || '-' },
    { title: '截止', dataIndex: 'deadline', width: 110, render: (v) => v || '-' },
    {
      title: '', key: 'actions', width: 170, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          {r.status === 'pending' && <a className="text-emerald-600 text-sm font-bold px-2" onClick={() => { setClaimTarget(r); claimForm.resetFields() }}>抢单接收</a>}
          {r.status === 'pending' && <a className="text-slate-500 text-sm px-2" onClick={() => doWithdraw(r)}>撤回</a>}
          <a className="text-rose-500 text-sm px-2" onClick={() => doDelete(r)}>删除</a>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center justify-between">
          <div className="flex gap-3 flex-wrap items-center">
            <Input placeholder="编号 / 客户" prefix={<SearchOutlined className="text-slate-400" />} value={keyword}
              onChange={(e) => setKeyword(e.target.value)} onPressEnter={() => { setPage(1); fetchData(1) }} allowClear style={{ width: 220 }} />
            <Select placeholder="状态" allowClear style={{ width: 140 }} value={status} onChange={setStatus} options={STATUS_OPTIONS} />
            <Button onClick={() => { setPage(1); fetchData(1) }}>筛选</Button>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建移交单</Button>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={data} loading={loading} scroll={{ x: 1300 }}
          pagination={{ current: page, total, pageSize, showTotal: (t) => `共 ${t} 条`, onChange: (p) => { setPage(p); fetchData(p) } }} />
      </div>

      <Modal title="新建清欠移交单" open={modalOpen} onOk={handleCreate} onCancel={() => setModalOpen(false)} okText="提交" destroyOnClose width={600}>
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="customer_id" label="客户">
            <Select showSearch filterOption={false} placeholder="搜索客户" options={customerSelect.options} loading={customerSelect.loading}
              onSearch={customerSelect.onSearch} onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} allowClear />
          </Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="transfer_type" label="移交类型"><Select options={TYPE_OPTIONS} /></Form.Item>
            <Form.Item name="debt_amount" label="欠款余额"><InputNumber min={0} style={{ width: '100%' }} prefix="¥" /></Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="to_department_name" label="目标部门"><Input placeholder="如：清欠办" /></Form.Item>
            <Form.Item name="contact" label="联系人"><Input /></Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="deadline" label="接收截止"><DatePicker style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="assess_date" label="考核日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
          </div>
          <Form.Item name="debt_note" label="欠款说明"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal title={`抢单接收 — ${claimTarget?.transfer_no || ''}`} open={!!claimTarget} onOk={doClaim}
        onCancel={() => setClaimTarget(null)} okText="确认接收" destroyOnClose width={480}>
        <p className="text-sm text-slate-500 mb-3">接收后，客户「{claimTarget?.customer_name}」的责任人将变更为你。</p>
        <Form form={claimForm} layout="vertical">
          <Form.Item name="commitment" label="清收承诺"><Input.TextArea rows={3} placeholder="如：3个月内清收 50%" /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default function CollectionPage() {
  usePageTitle('应收清欠')
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">应收清欠</h1>
        <p className="text-sm text-slate-500 mt-0.5">应收账龄分析 + 清欠责任移交与抢单接收</p>
      </div>
      <Tabs items={[
        { key: 'aging', label: '应收账龄', children: <AgingTab /> },
        { key: 'transfer', label: '清欠移交 / 抢单', children: <TransferTab /> },
      ]} />
    </div>
  )
}
