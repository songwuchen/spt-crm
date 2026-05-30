import { useState, useEffect } from 'react'
import { Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { tenderApi } from '@/api/tender'
import type { Tender } from '@/api/types'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useCustomerSelect, useUserSelect } from '@/hooks/useSelectOptions'

const STATUS_OPTIONS = [
  { label: '编制中', value: 'preparing' },
  { label: '已投标', value: 'submitted' },
  { label: '中标', value: 'won' },
  { label: '未中标', value: 'lost' },
  { label: '已取消', value: 'cancelled' },
]
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS_OPTIONS.map(o => [o.value, o.label]))

export default function TenderList() {
  usePageTitle('标书管理')
  const [data, setData] = useState<Tender[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Tender | null>(null)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()
  const ownerSelect = useUserSelect()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await tenderApi.list({ pageNo: p, pageSize, keyword: keyword || undefined, status })
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
    form.setFieldsValue({ status: 'preparing' })
    setModalOpen(true)
  }

  const openEdit = (record: Tender) => {
    setEditing(record)
    form.setFieldsValue({
      ...record,
      submit_date: record.submit_date ? dayjs(record.submit_date) : undefined,
      open_date: record.open_date ? dayjs(record.open_date) : undefined,
    })
    if (record.customer_id) customerSelect.setInitialOption({ label: record.customer_id, value: record.customer_id })
    if (record.owner_id && record.owner_name) ownerSelect.setInitialOption({ label: record.owner_name, value: record.owner_id })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    const values = await form.validateFields()
    const payload = {
      ...values,
      submit_date: values.submit_date ? values.submit_date.format('YYYY-MM-DD') : undefined,
      open_date: values.open_date ? values.open_date.format('YYYY-MM-DD') : undefined,
    }
    try {
      if (editing) {
        await tenderApi.update(editing.id, payload)
        message.success('已更新')
      } else {
        await tenderApi.create(payload)
        message.success('已创建')
      }
      setModalOpen(false)
      fetchData()
    } catch (e: any) {
      if (e?.errorFields) return
      message.error('保存失败')
    }
  }

  const handleDelete = (record: Tender) => {
    Modal.confirm({
      title: '删除标书', content: `确认删除标书 ${record.tender_no}?`, okType: 'danger',
      onOk: async () => { await tenderApi.delete(record.id); message.success('已删除'); fetchData() },
    })
  }

  const handleExport = () => {
    const qs = new URLSearchParams()
    if (keyword) qs.set('keyword', keyword)
    if (status) qs.set('status', status)
    const q = qs.toString()
    downloadFile(`/api/v1/tenders/export/excel${q ? `?${q}` : ''}`, 'tenders.xlsx')
  }

  const columns: ColumnsType<Tender> = [
    { title: '标书号', dataIndex: 'tender_no', width: 160, render: (v) => <span className="font-mono text-sm">{v}</span> },
    { title: '标题', dataIndex: 'title' },
    { title: '投标金额', dataIndex: 'bid_amount', width: 130, render: (v) => v != null ? Number(v).toLocaleString() : '-' },
    { title: '状态', dataIndex: 'status', width: 100, render: (v) => STATUS_LABEL[v] || v },
    { title: '提交日期', dataIndex: 'submit_date', width: 120, render: (v) => v || '-' },
    { title: '开标日期', dataIndex: 'open_date', width: 120, render: (v) => v || '-' },
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
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">标书管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理客户投标/招标项目，可关联商机</p>
        </div>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建标书</Button>
        </Space>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="标书号 / 标题"
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
        title={editing ? '编辑标书' : '新建标书'}
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
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}><Input placeholder="标书标题" /></Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="bid_amount" label="投标金额"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="budget_amount" label="预算金额"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          </div>
          <Form.Item name="status" label="状态"><Select options={STATUS_OPTIONS} /></Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="submit_date" label="提交日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="open_date" label="开标日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
          </div>
          <Form.Item name="result" label="结果"><Input placeholder="中标/未中标说明" /></Form.Item>
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
