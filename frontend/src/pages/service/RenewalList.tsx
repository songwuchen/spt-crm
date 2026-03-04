import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, InputNumber, Select, Tag, Space, DatePicker, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { renewalApi } from '@/api/renewal'
import type { RenewalItem } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import dayjs from 'dayjs'

const statusConfig: Record<string, { label: string; color: string }> = {
  open: { label: '跟进中', color: 'processing' },
  won: { label: '已赢单', color: 'success' },
  lost: { label: '已丢单', color: 'error' },
}

export default function RenewalList() {
  usePageTitle('续约管理')
  const [items, setItems] = useState<RenewalItem[]>([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form] = Form.useForm()

  const fetch = async () => {
    setLoading(true)
    try {
      const res = await renewalApi.list()
      setItems(res.data || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetch() }, [])

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

  const columns = [
    { title: '名称', dataIndex: 'name', width: 200,
      render: (v: string) => <span className="font-semibold text-slate-800">{v}</span> },
    { title: '客户ID', dataIndex: 'customer_id', width: 120, ellipsis: true },
    { title: '预期金额', dataIndex: 'amount_expect', width: 120, align: 'right' as const,
      render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
    { title: '预计关闭', dataIndex: 'close_date_expect', width: 110 },
    { title: '概率', dataIndex: 'probability', width: 70,
      render: (v: number) => v != null ? `${v}%` : '-' },
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
          <Form.Item name="customer_id" label="客户ID" rules={[{ required: true, message: '请输入客户ID' }]}>
            <Input placeholder="客户 UUID" />
          </Form.Item>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="amount_expect" label="预期金额">
              <InputNumber className="w-full" min={0} precision={2} />
            </Form.Item>
            <Form.Item name="probability" label="赢单概率 (%)">
              <InputNumber className="w-full" min={0} max={100} />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="close_date_expect" label="预计关闭日期">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="status" label="状态">
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
