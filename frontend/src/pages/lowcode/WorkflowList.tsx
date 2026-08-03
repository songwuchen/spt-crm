// 扩展平台 → 流程管理: 审批流程定义列表(建/设计/发布/删,建时绑定表单或业务类型)。
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Space, Tag, Modal, Form, Input, Select, message, Popconfirm, Typography } from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import { PlusOutlined } from '@ant-design/icons'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import { usePermission } from '@/hooks/usePermission'
import type { WfDefinition, FormTemplate } from '@/types/lowcode'

const { Title, Text } = Typography

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  published: { color: 'green', text: '已发布' },
  deprecated: { color: 'orange', text: '已停用' },
}

/** 业务类型展示名（与新建弹窗选项一致） */
const BIZ_TYPE_LABEL: Record<string, string> = {
  order: '订单',
  lead: '线索',
  service_ticket: '售后工单',
  quote_version: '报价单',
  contract_version: '合同版本（登记运营）',
  contract_review: '合同评审会签',
  change_request: '变更单',
  solution: '方案',
}

const BIZ_TYPE_OPTIONS = [
  { label: '订单', value: 'order' },
  { label: '线索', value: 'lead' },
  { label: '售后工单', value: 'service_ticket' },
  { label: '报价单', value: 'quote_version' },
  { label: '合同版本（登记运营 / 签署前）', value: 'contract_version' },
  { label: '合同评审会签', value: 'contract_review' },
  { label: '变更单', value: 'change_request' },
  { label: '方案', value: 'solution' },
]

export default function WorkflowList() {
  const nav = useNavigate()
  const { hasPermission } = usePermission()
  const canManage = hasPermission('workflow:manage')
  const [items, setItems] = useState<WfDefinition[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [forms, setForms] = useState<FormTemplate[]>([])
  const [form] = Form.useForm()

  const load = async () => {
    setLoading(true)
    try {
      const res = await workflowApi.listDefs({ pageNo, pageSize: 20 })
      setItems(res.data.items); setTotal(res.data.total)
    } catch {
      message.error('加载流程列表失败')
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [pageNo])  // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = async () => {
    try {
      const res = await lowcodeApi.listTemplates({ pageNo: 1, pageSize: 100, published_only: true })
      setForms(res.data.items)
      form.resetFields()
      setOpen(true)
    } catch { message.error('加载可绑定表单失败') }
  }

  const handleCreate = async () => {
    const v = await form.validateFields()
    if (v.form_template_id && v.biz_type) {
      message.error('绑定表单与业务类型只能二选一')
      return
    }
    if (!v.form_template_id && !v.biz_type) {
      message.error('请绑定表单或业务类型之一')
      return
    }
    setCreating(true)
    try {
      const res = await workflowApi.createDef(v)
      message.success('已创建，去设计流程')
      setOpen(false); form.resetFields()
      nav(`/lowcode/workflows/${res.data.id}/design`)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '创建流程失败')
    } finally { setCreating(false) }
  }

  const del = async (id: string, isSystem?: boolean) => {
    try {
      await workflowApi.deleteDef(id)
      message.success(isSystem ? '已删除（下次打开列表可能自动恢复系统默认流）' : '已删除')
      load()
    } catch { message.error('删除失败') }
  }

  const columns = [
    { title: '流程名称', dataIndex: 'name', key: 'name',
      render: (v: string, r: WfDefinition) => (
        <Space size={6}>
          <span>{v}</span>
          {r.category === 'system_default' && <Tag color="purple">系统默认</Tag>}
        </Space>
      ) },
    { title: '编码', dataIndex: 'code', key: 'code',
      render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text> },
    { title: '绑定', key: 'bind', width: 200,
      render: (_: unknown, r: WfDefinition) => {
        if (r.biz_type) {
          return <Tag color="geekblue">{BIZ_TYPE_LABEL[r.biz_type] || r.biz_type}</Tag>
        }
        if (r.form_template_id) return <Tag color="blue">自定义表单</Tag>
        return <Text type="secondary">—</Text>
      } },
    { title: '状态', dataIndex: 'status', key: 'status', width: 90,
      render: (s: string) => { const t = STATUS_TAG[s] || { color: 'default', text: s }; return <Tag color={t.color}>{t.text}</Tag> } },
    { title: '版本', dataIndex: 'current_version', key: 'v', width: 70,
      render: (v: number) => (v > 0 ? `v${v}` : '草稿') },
    ...(canManage ? [{
      title: '操作', key: 'op', width: 220,
      render: (_: unknown, r: WfDefinition) => (
        <Space size="small">
          <Button size="small" onClick={() => nav(`/lowcode/workflows/${r.id}/design`)}>设计</Button>
          <Popconfirm
            title={r.category === 'system_default' ? '删除系统默认流程？' : '确认删除该流程?'}
            description={r.category === 'system_default'
              ? '删除后打开本页可能自动恢复；也可在业务提交审批时自动重建。'
              : undefined}
            onConfirm={() => del(r.id, r.category === 'system_default')}
          >
            <Button size="small" type="link" danger>删除</Button>
          </Popconfirm>
        </Space>
      ),
    }] : []),
  ]

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }} className="shrink-0">
        <div>
          <Title level={4} style={{ margin: 0 }}>流程管理</Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            系统会自动补齐默认流：「合同版本」= 财务审核后按标准交付/旋振筛并行运营部门；「合同评审」= 业务部门→多部门会签→总经理/财务；「线索审核」含抄送负责人。
          </Text>
        </div>
        {canManage && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建流程</Button>}
      </div>
      <FillHeightTable rowKey="id" loading={loading} columns={columns} dataSource={items} scroll={{ x: 'max-content' }}
          pagination={{ current: pageNo, total, pageSize: 20, onChange: setPageNo, showSizeChanger: false }} />

      <Modal title="新建审批流程" open={open} onOk={handleCreate} confirmLoading={creating} onCancel={() => setOpen(false)} destroyOnClose>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="流程名称" rules={[{ required: true, message: '请输入流程名称' }]}>
            <Input placeholder="如: 合同评审会签 / 请假审批" />
          </Form.Item>
          <Form.Item name="form_template_id" label="绑定表单" tooltip="与「业务类型」二选一；绑定后该表单提交即发起此流程">
            <Select allowClear placeholder="选择已发布的表单"
              options={forms.map((f) => ({ label: f.name, value: f.id }))}
              onChange={() => form.setFieldValue('biz_type', undefined)} />
          </Form.Item>
          <Form.Item name="biz_type" label="或 绑定业务类型" tooltip="与「表单」二选一；业务单据「提交审批」时走此流程"
            dependencies={['form_template_id']}>
            <Select allowClear showSearch optionFilterProp="label" placeholder="订单 / 线索 / 合同版本 / 合同评审…"
              options={BIZ_TYPE_OPTIONS}
              onChange={() => form.setFieldValue('form_template_id', undefined)} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
