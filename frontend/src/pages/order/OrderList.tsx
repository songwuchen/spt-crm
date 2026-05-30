import { useState, useEffect } from 'react'
import { Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { orderApi } from '@/api/order'
import type { Order } from '@/api/types'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useCustomerSelect, useUserSelect } from '@/hooks/useSelectOptions'

const STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '已确认', value: 'confirmed' },
  { label: '生产中', value: 'producing' },
  { label: '已发货', value: 'shipped' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' },
]
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS_OPTIONS.map(o => [o.value, o.label]))

export default function OrderList() {
  usePageTitle('订单管理')
  const [data, setData] = useState<Order[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Order | null>(null)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()
  const ownerSelect = useUserSelect()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await orderApi.list({ pageNo: p, pageSize, keyword: keyword || undefined, status })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData(1); setPage(1) }, [status]) // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({ status: 'draft', currency: 'CNY' })
    setModalOpen(true)
  }

  const openEdit = (record: Order) => {
    setEditing(record)
    form.setFieldsValue({
      ...record,
      order_date: record.order_date ? dayjs(record.order_date) : undefined,
      delivery_date: record.delivery_date ? dayjs(record.delivery_date) : undefined,
    })
    if (record.customer_id) customerSelect.setInitialOption({ label: record.customer_id, value: record.customer_id })
    if (record.owner_id && record.owner_name) ownerSelect.setInitialOption({ label: record.owner_name, value: record.owner_id })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    const payload = {
      ...values,
      order_date: values.order_date ? values.order_date.format('YYYY-MM-DD') : undefined,
      delivery_date: values.delivery_date ? values.delivery_date.format('YYYY-MM-DD') : undefined,
    }
    try {
      if (editing) {
        await orderApi.update(editing.id, payload)
        message.success('已更新')
      } else {
        await orderApi.create(payload)
        message.success('已创建')
      }
      setModalOpen(false)
      fetchData()
    } catch (e: any) {
      if (e?.errorFields) return // validation error
      message.error('保存失败')
    }
  }

  const handleDelete = (record: Order) => {
    Modal.confirm({
      title: '删除订单', content: `确认删除订单 ${record.order_no}?`, okType: 'danger',
      onOk: async () => { await orderApi.delete(record.id); message.success('已删除'); fetchData() },
    })
  }

  const handleExport = () => {
    const qs = new URLSearchParams()
    if (keyword) qs.set('keyword', keyword)
    if (status) qs.set('status', status)
    const q = qs.toString()
    downloadFile(`/api/v1/orders/export/excel${q ? `?${q}` : ''}`, 'orders.xlsx')
  }

  const columns: ColumnsType<Order> = [
    { title: '订单号', dataIndex: 'order_no', width: 160, render: (v) => <span className="font-mono text-sm">{v}</span> },
    { title: '标题', dataIndex: 'title', render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '金额', dataIndex: 'amount', width: 130, render: (v, r) => v != null ? `${r.currency || ''} ${Number(v).toLocaleString()}` : '-' },
    { title: '状态', dataIndex: 'status', width: 100, render: (v) => STATUS_LABEL[v] || v },
    { title: '下单日期', dataIndex: 'order_date', width: 120, render: (v) => v || '-' },
    { title: '交付日期', dataIndex: 'delivery_date', width: 120, render: (v) => v || '-' },
    { title: '负责人', dataIndex: 'owner_name', width: 100, render: (v) => v || '-' },
    {
      title: '', key: 'actions', width: 130, fixed: 'right',
      render: (_, record) => (
        <Space size={0}>
          <a className="text-primary text-sm font-bold px-2" onClick={() => openEdit(record)}>编辑</a>
          <a className="text-rose-500 text-sm font-bold px-2" onClick={() => handleDelete(record)}>删除</a>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">订单管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理客户成交订单，可关联商机与合同</p>
        </div>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建订单</Button>
        </Space>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="订单号 / 标题"
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => fetchData(1)}
            allowClear
            style={{ width: 220 }}
          />
          <Select placeholder="状态" allowClear style={{ width: 140 }} value={status} onChange={setStatus} options={STATUS_OPTIONS} />
          <Button onClick={() => { setPage(1); fetchData(1) }}>筛选</Button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 1000 }}
          pagination={{
            current: page, total, pageSize, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPage(p); fetchData(p) },
          }}
        />
      </div>

      <Modal
        title={editing ? '编辑订单' : '新建订单'}
        open={modalOpen}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        okText="保存"
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="customer_id" label="客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select
              showSearch filterOption={false} placeholder="搜索客户"
              options={customerSelect.options} loading={customerSelect.loading}
              onSearch={customerSelect.onSearch} onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
              disabled={!!editing}
            />
          </Form.Item>
          <Form.Item name="title" label="标题"><Input placeholder="订单标题" /></Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="amount" label="金额"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="currency" label="币种"><Input /></Form.Item>
          </div>
          <Form.Item name="status" label="状态"><Select options={STATUS_OPTIONS} /></Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="order_date" label="下单日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="delivery_date" label="交付日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
          </div>
          <Form.Item name="owner_id" label="负责人">
            <Select
              showSearch filterOption={false} allowClear placeholder="搜索用户"
              options={ownerSelect.options} loading={ownerSelect.loading}
              onSearch={ownerSelect.onSearch} onDropdownVisibleChange={ownerSelect.onDropdownVisibleChange}
            />
          </Form.Item>
          <Form.Item name="remark" label="备注"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
