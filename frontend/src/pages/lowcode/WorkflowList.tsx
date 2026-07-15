// 扩展平台 → 流程管理: 审批流程定义列表(建/设计/发布/删,建时绑定表单)。
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Table, Button, Space, Tag, Modal, Form, Input, Select, message, Popconfirm, Typography } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfDefinition, FormTemplate } from '@/types/lowcode'

const { Title } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  published: { color: 'green', text: '已发布' },
  deprecated: { color: 'orange', text: '已停用' },
}

export default function WorkflowList() {
  const nav = useNavigate()
  const [items, setItems] = useState<WfDefinition[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [forms, setForms] = useState<FormTemplate[]>([])
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const res = await workflowApi.listDefs({ pageNo, pageSize: 20 })
      setItems(res.data.items); setTotal(res.data.total)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [pageNo])  // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = async () => {
    const res = await lowcodeApi.listTemplates({ pageNo: 1, pageSize: 100, published_only: true })
    setForms(res.data.items)
    setOpen(true)
  }

  const handleCreate = async () => {
    const v = await form.validateFields()
    const res = await workflowApi.createDef(v)
    message.success('已创建，去设计流程')
    setOpen(false); form.resetFields()
    nav(`/lowcode/workflows/${res.data.id}/design`)
  }

  const del = async (id: string) => { await workflowApi.deleteDef(id); message.success('已删除'); load() }

  const columns = [
    { title: '流程名称', dataIndex: 'name', key: 'name' },
    { title: '编码', dataIndex: 'code', key: 'code' },
    { title: '绑定表单', dataIndex: 'form_template_id', key: 'form', render: (v: string) => (v ? <Tag color="blue">已绑定</Tag> : '—') },
    { title: '状态', dataIndex: 'status', key: 'status', render: (s: string) => { const t = STATUS_TAG[s] || { color: 'default', text: s }; return <Tag color={t.color}>{t.text}</Tag> } },
    { title: '版本', dataIndex: 'current_version', key: 'v', render: (v: number) => `v${v}` },
    {
      title: '操作', key: 'op', width: 220,
      render: (_: unknown, r: WfDefinition) => (
        <Space size="small">
          <Button size="small" onClick={() => nav(`/lowcode/workflows/${r.id}/design`)}>设计</Button>
          <Popconfirm title="确认删除该流程?" onConfirm={() => del(r.id)}>
            <Button size="small" type="link" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>流程管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建流程</Button>
      </div>
      <Table rowKey="id" loading={loading} columns={columns} dataSource={items}
        pagination={{ current: pageNo, total, pageSize: 20, onChange: setPageNo, showSizeChanger: false }} />

      <Modal title="新建审批流程" open={open} onOk={handleCreate} onCancel={() => setOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="流程名称" rules={[{ required: true, message: '请输入流程名称' }]}>
            <Input placeholder="如: 请假审批 / 报销审批" />
          </Form.Item>
          <Form.Item name="form_template_id" label="绑定表单" tooltip="绑定后,该表单提交即自动发起此审批流程">
            <Select allowClear placeholder="选择已发布的表单(可稍后再绑)"
              options={forms.map((f) => ({ label: f.name, value: f.id }))} />
          </Form.Item>
          <Form.Item name="biz_type" label="或 绑定业务类型" tooltip="绑定后,该业务单据提交审批时走此可视化流程,结果回写业务状态(灰度替换旧审批)">
            <Select allowClear showSearch optionFilterProp="label" placeholder="订单 / 线索 / 工单 / 报价 / 合同…(与表单二选一)"
              options={[
                { label: '订单', value: 'order' },
                { label: '线索', value: 'lead' },
                { label: '售后工单', value: 'service_ticket' },
                { label: '报价单', value: 'quote_version' },
                { label: '合同', value: 'contract_version' },
                { label: '变更单', value: 'change_request' },
                { label: '方案', value: 'solution' },
              ]} />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  )
}
