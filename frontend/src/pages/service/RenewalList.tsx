import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, InputNumber, Select, Tag, Space, DatePicker, message } from 'antd'
import { PlusOutlined, FilterOutlined } from '@ant-design/icons'
import { renewalApi } from '@/api/renewal'
import { customerApi } from '@/api/customer'
import { userApi } from '@/api/user'
import type { RenewalItem } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import dayjs from 'dayjs'

const statusConfig: Record<string, { label: string; color: string }> = {
  open: { label: '跟进中', color: 'processing' },
  won: { label: '已赢单', color: 'success' },
  lost: { label: '已丢单', color: 'error' },
}

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'open', label: '跟进中' },
  { value: 'won', label: '已赢单' },
  { value: 'lost', label: '已丢单' },
]

export default function RenewalList() {
  usePageTitle('续约管理')
  const [items, setItems] = useState<RenewalItem[]>([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState('')
  const [form] = Form.useForm()

  const customerSelect = useRemoteSelect(async (kw) => {
    const r = await customerApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((c: any) => ({ label: c.name, value: c.id }))
  })

  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  const fetch = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {}
      if (statusFilter) params.status = statusFilter
      const res = await renewalApi.list(params)
      setItems(res.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetch() }, [statusFilter])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    if (values.close_date_expect) {
      values.close_date_expect = values.close_date_expect.format('YYYY-MM-DD')
    }
    if (editingId) {
      await renewalApi.update(editingId, values)
      message.success('已更新')
    } else {
      await renewalApi.create(values)
      message.success('已创建')
    }
    setModal(false)
    form.resetFields()
    setEditingId(null)
    fetch()
  }

  const openEdit = (item: RenewalItem) => {
    setEditingId(item.id)
    form.setFieldsValue({
      ...item,
      close_date_expect: item.close_date_expect ? dayjs(item.close_date_expect) : null,
    })
    setModal(true)
  }

  // Summary stats
  const total = items.length
  const openCount = items.filter((i) => i.status === 'open').length
  const wonCount = items.filter((i) => i.status === 'won').length
  const wonAmount = items.filter((i) => i.status === 'won').reduce((s, i) => s + (i.amount_expect || 0), 0)

  const columns = [
    { title: '名称', dataIndex: 'name', width: 200,
      render: (v: string) => <span className="font-semibold text-slate-800">{v}</span> },
    { title: '客户', dataIndex: 'customer_name', width: 150,
      render: (v: string, r: RenewalItem) => v || r.customer_id?.slice(0, 8) + '...' },
    { title: '预期金额', dataIndex: 'amount_expect', width: 120, align: 'right' as const,
      render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
    { title: '预计关闭', dataIndex: 'close_date_expect', width: 110 },
    { title: '概率', dataIndex: 'probability', width: 70,
      render: (v: number) => v != null ? (
        <span className={v >= 80 ? 'text-emerald-600 font-bold' : v >= 50 ? 'text-amber-600' : 'text-slate-500'}>{v}%</span>
      ) : '-' },
    { title: '负责人', dataIndex: 'owner_name', width: 100 },
    { title: '状态', dataIndex: 'status', width: 80,
      render: (v: string) => {
        const cfg = statusConfig[v] || { label: v, color: 'default' }
        return <Tag color={cfg.color}>{cfg.label}</Tag>
      },
    },
    { title: '创建时间', dataIndex: 'created_at', width: 150,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
    { title: '', key: 'actions', width: 80,
      render: (_: unknown, r: RenewalItem) => (
        <a className="text-primary text-xs font-bold" onClick={() => openEdit(r)}>编辑</a>
      ),
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">续约管理</h1>
          <p className="text-sm text-slate-500 mt-1">管理复购和续约商机</p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          setEditingId(null); form.resetFields(); setModal(true)
        }}>新增续约</Button>
      </div>

      {/* Stats + Filter */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex gap-4">
          <div className="px-3 py-2 bg-white rounded-lg border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-400">总数</span>
            <span className="ml-2 text-sm font-black text-slate-800">{total}</span>
          </div>
          <div className="px-3 py-2 bg-white rounded-lg border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-400">跟进中</span>
            <span className="ml-2 text-sm font-black text-blue-600">{openCount}</span>
          </div>
          <div className="px-3 py-2 bg-white rounded-lg border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-400">赢单</span>
            <span className="ml-2 text-sm font-black text-emerald-600">{wonCount}</span>
          </div>
          <div className="px-3 py-2 bg-white rounded-lg border border-slate-200 shadow-sm">
            <span className="text-xs text-slate-400">赢单额</span>
            <span className="ml-2 text-sm font-black text-amber-600">¥{(wonAmount / 10000).toFixed(1)}万</span>
          </div>
        </div>
        <Select value={statusFilter} onChange={setStatusFilter} options={statusOptions}
          style={{ width: 120 }} size="small" suffixIcon={<FilterOutlined />} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading}
          pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 条` }}
          size="small" />
      </div>

      <Modal title={editingId ? '编辑续约' : '新增续约'} open={modal}
        onOk={handleSubmit} onCancel={() => { setModal(false); setEditingId(null); form.resetFields() }}
        width={550}>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="续约/复购名称" />
          </Form.Item>
          <Form.Item name="customer_id" label="客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select showSearch filterOption={false} placeholder="搜索并选择客户"
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </Form.Item>
          <Form.Item name="owner_id" label="负责人">
            <Select showSearch filterOption={false} placeholder="搜索并选择负责人" allowClear
              loading={userSelect.loading}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
          </Form.Item>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="amount_expect" label="预期金额"
              rules={[{ type: 'number', min: 0, message: '金额不能为负' }]}>
              <InputNumber className="w-full" min={0} precision={2} placeholder="0.00" />
            </Form.Item>
            <Form.Item name="probability" label="赢单概率 (%)"
              rules={[{ type: 'number', min: 0, max: 100, message: '范围 0-100' }]}>
              <InputNumber className="w-full" min={0} max={100} />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="close_date_expect" label="预计关闭日期">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="status" label="状态" initialValue="open">
              <Select options={[
                { value: 'open', label: '跟进中' },
                { value: 'won', label: '已赢单' },
                { value: 'lost', label: '已丢单' },
              ]} />
            </Form.Item>
          </div>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
