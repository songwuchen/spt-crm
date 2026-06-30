import { useState, useEffect, useRef } from 'react'
import {
  Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, message, Tag, Statistic,
} from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, BellOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { guaranteeApi } from '@/api/guarantee'
import type { Guarantee, GuaranteeSummary } from '@/api/types'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useCustomerSelect, useUserSelect } from '@/hooks/useSelectOptions'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'

const TYPE_OPTIONS = [
  { label: '履约保函', value: 'performance' },
  { label: '预付保函', value: 'advance' },
  { label: '质量保函', value: 'quality' },
  { label: '投标保证金', value: 'bid' },
  { label: '履约保证金', value: 'deposit' },
]
const TYPE_LABEL: Record<string, string> = Object.fromEntries(TYPE_OPTIONS.map(o => [o.value, o.label]))
const STATUS_OPTIONS = [
  { label: '生效中', value: 'active' },
  { label: '已退还', value: 'returned' },
  { label: '已逾期', value: 'expired' },
  { label: '已取消', value: 'cancelled' },
]
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS_OPTIONS.map(o => [o.value, o.label]))
const STATUS_COLOR: Record<string, string> = { active: 'blue', returned: 'green', expired: 'red', cancelled: 'default' }
const DIRECTION_OPTIONS = [
  { label: '我方开出', value: 'outgoing' },
  { label: '我方收取', value: 'incoming' },
]

const money = (v?: number) => (v != null ? `¥${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '-')

function daysLeft(expiry?: string): number | null {
  if (!expiry) return null
  return dayjs(expiry).startOf('day').diff(dayjs().startOf('day'), 'day')
}

export default function GuaranteePage() {
  usePageTitle('保函管理')
  const [data, setData] = useState<Guarantee[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [type, setType] = useState<string | undefined>()
  const [status, setStatus] = useState<string | undefined>()
  const [summary, setSummary] = useState<GuaranteeSummary | null>(null)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Guarantee | null>(null)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()
  const ownerSelect = useUserSelect()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await guaranteeApi.list({ pageNo: p, pageSize, keyword: keyword || undefined, type, status, ...view.buildParams() })
      setData(res.data.items); setTotal(res.data.total)
    } finally { setLoading(false) }
  }
  const fetchSummary = async () => { try { setSummary((await guaranteeApi.summary()).data) } catch { /* */ } }
  useEffect(() => { fetchData(1); setPage(1); fetchSummary() }, [type, status]) // eslint-disable-line react-hooks/exhaustive-deps

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload]) // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => {
    setEditing(null); form.resetFields()
    form.setFieldsValue({ type: 'performance', direction: 'outgoing' })
    setModalOpen(true)
  }
  const openEdit = (g: Guarantee) => {
    setEditing(g)
    form.setFieldsValue({
      ...g,
      effective_date: g.effective_date ? dayjs(g.effective_date) : undefined,
      expiry_date: g.expiry_date ? dayjs(g.expiry_date) : undefined,
    })
    if (g.customer_id && g.customer_name) customerSelect.setInitialOption({ label: g.customer_name, value: g.customer_id })
    if (g.owner_id && g.owner_name) ownerSelect.setInitialOption({ label: g.owner_name, value: g.owner_id })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    let values
    try { values = await form.validateFields() } catch { return }
    const payload: Record<string, unknown> = {
      ...values,
      effective_date: values.effective_date ? values.effective_date.format('YYYY-MM-DD') : undefined,
      expiry_date: values.expiry_date ? values.expiry_date.format('YYYY-MM-DD') : undefined,
    }
    if (values.customer_id) {
      const opt = customerSelect.options.find((o) => o.value === values.customer_id)
      if (opt) payload.customer_name = opt.label
    }
    if (values.owner_id) {
      const opt = ownerSelect.options.find((o) => o.value === values.owner_id)
      if (opt) payload.owner_name = opt.label
    }
    try {
      if (editing) { await guaranteeApi.update(editing.id, payload); message.success('已更新') }
      else { await guaranteeApi.create(payload); message.success('已登记') }
      setModalOpen(false); fetchData(); fetchSummary()
    } catch { message.error('保存失败') }
  }

  const doReturn = (g: Guarantee) => {
    let d = dayjs()
    Modal.confirm({
      title: '保函退还', content: (
        <div className="mt-2">
          <span className="text-sm text-slate-500">退还日期：</span>
          <DatePicker defaultValue={d} onChange={(v) => { if (v) d = v }} />
        </div>
      ),
      onOk: async () => { await guaranteeApi.markReturned(g.id, { return_date: d.format('YYYY-MM-DD') }); message.success('已退还'); fetchData(); fetchSummary() },
    })
  }
  const doDelete = (g: Guarantee) => Modal.confirm({
    title: '删除保函', content: `确认删除 ${g.guarantee_no}？`, okType: 'danger',
    onOk: async () => { await guaranteeApi.remove(g.id); message.success('已删除'); fetchData(); fetchSummary() },
  })
  const notify = async () => {
    try { const r = await guaranteeApi.notify(30); message.success(`已提醒 ${r.data.notified} 位负责人`) }
    catch { message.error('提醒失败') }
  }

  const columns: ColumnsType<Guarantee> = [
    { title: '保函编号', dataIndex: 'guarantee_no', width: 150, fixed: 'left', render: (v) => <span className="font-mono text-xs">{v}</span> },
    { title: '类型', dataIndex: 'type', width: 110, render: (v) => TYPE_LABEL[v] || v },
    { title: '客户', dataIndex: 'customer_name', width: 170, ellipsis: true, render: (v) => v || '-' },
    { title: '金额', dataIndex: 'amount', width: 130, align: 'right', render: money },
    { title: '出具机构', dataIndex: 'issuer', width: 130, ellipsis: true, render: (v) => v || '-' },
    {
      title: '到期日', dataIndex: 'expiry_date', width: 150,
      render: (v, r) => {
        if (!v) return '-'
        const dl = daysLeft(v)
        if (r.status === 'active' && dl != null && dl <= 30) {
          return <span className="text-rose-500 font-semibold">{v} {dl >= 0 ? `(${dl}天)` : '(已逾期)'}</span>
        }
        return v
      },
    },
    { title: '状态', dataIndex: 'status', width: 90, render: (v) => <Tag color={STATUS_COLOR[v] || 'default'}>{STATUS_LABEL[v] || v}</Tag> },
    { title: '负责人', dataIndex: 'owner_name', width: 90, render: (v) => v || '-' },
    {
      title: '', key: 'actions', width: 170, fixed: 'right',
      render: (_, g) => (
        <Space size={0}>
          {g.status === 'active' && <a className="text-emerald-600 text-sm font-bold px-2" onClick={() => doReturn(g)}>退还</a>}
          <a className="text-primary text-sm px-2" onClick={() => openEdit(g)}>编辑</a>
          <a className="text-rose-500 text-sm px-2" onClick={() => doDelete(g)}>删除</a>
        </Space>
      ),
    },
  ]

  const view = useListView<Guarantee>('guarantee', columns, { pageKey: 'guarantees' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">保函管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">保函 / 保证金台账，到期前自动预警，避免应退未退</p>
        </div>
        <Space>
          <Button icon={<BellOutlined />} onClick={notify}>提醒到期</Button>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/guarantees/export/excel', 'guarantees.xlsx')}>导出</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>登记保函</Button>
        </Space>
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <Statistic title="在保金额" value={summary?.active_amount || 0} precision={2} prefix="¥" valueStyle={{ color: '#137fec' }} />
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <Statistic title="30天内到期" value={summary?.expiring_30d || 0} suffix="笔" valueStyle={{ color: '#ef4444' }} />
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <Statistic title="已逾期" value={summary?.by_status?.expired?.count || 0} suffix="笔" valueStyle={{ color: '#f97316' }} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input placeholder="编号 / 客户 / 机构" prefix={<SearchOutlined className="text-slate-400" />} value={keyword}
            onChange={(e) => setKeyword(e.target.value)} onPressEnter={() => { setPage(1); fetchData(1) }} allowClear style={{ width: 220 }} />
          <Select placeholder="类型" allowClear style={{ width: 140 }} value={type} onChange={setType} options={TYPE_OPTIONS} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={status} onChange={setStatus} options={STATUS_OPTIONS} />
          <Button onClick={() => { setPage(1); fetchData(1) }}>筛选</Button>
          <ListToolbar resource="guarantee" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={view.columns} dataSource={data} loading={loading} scroll={{ x: 1200 }}
          pagination={{ current: page, total, pageSize, showTotal: (t) => `共 ${t} 条`, onChange: (p) => { setPage(p); fetchData(p) } }} />
      </div>

      <Modal title={editing ? '编辑保函' : '登记保函'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)}
        okText="保存" destroyOnClose width={620}>
        <Form form={form} layout="vertical" className="mt-4">
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="type" label="类型" rules={[{ required: true }]}><Select options={TYPE_OPTIONS} /></Form.Item>
            <Form.Item name="direction" label="方向"><Select options={DIRECTION_OPTIONS} /></Form.Item>
          </div>
          <Form.Item name="customer_id" label="客户">
            <Select showSearch filterOption={false} allowClear placeholder="搜索客户" options={customerSelect.options}
              loading={customerSelect.loading} onSearch={customerSelect.onSearch} onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="amount" label="金额" rules={[{ required: true }]}><InputNumber min={0} style={{ width: '100%' }} prefix="¥" /></Form.Item>
            <Form.Item name="issuer" label="出具机构"><Input placeholder="如：工商银行" /></Form.Item>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Form.Item name="effective_date" label="生效日"><DatePicker style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="expiry_date" label="到期日" rules={[{ required: true, message: '请选择到期日' }]}><DatePicker style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="fee" label="手续费"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="owner_id" label="负责人">
              <Select showSearch filterOption={false} allowClear placeholder="搜索用户" options={ownerSelect.options}
                loading={ownerSelect.loading} onSearch={ownerSelect.onSearch} onDropdownVisibleChange={ownerSelect.onDropdownVisibleChange} />
            </Form.Item>
            {editing && <Form.Item name="status" label="状态"><Select options={STATUS_OPTIONS} /></Form.Item>}
          </div>
          <Form.Item name="remark" label="备注"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
