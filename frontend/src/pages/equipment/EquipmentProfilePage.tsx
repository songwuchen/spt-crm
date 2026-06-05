import { useState, useEffect } from 'react'
import {
  Tabs, Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, message, Tag, Switch,
} from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { equipmentApi } from '@/api/equipment'
import type { CustomerEquipment, CustomerProcessSurvey } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useCustomerSelect } from '@/hooks/useSelectOptions'

const INDUSTRY_OPTIONS = ['冶金', '焦化', '电力', '矿山', '砂石骨料', '煤炭', '精细物料'].map(v => ({ label: v, value: v }))

function EquipmentTab() {
  const [data, setData] = useState<CustomerEquipment[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [onlyCompetitor, setOnlyCompetitor] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<CustomerEquipment | null>(null)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()
  const [renewTarget, setRenewTarget] = useState<CustomerEquipment | null>(null)
  const [renewForm] = Form.useForm()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await equipmentApi.listEquipment({ pageNo: p, pageSize, keyword: keyword || undefined, is_competitor: onlyCompetitor || undefined })
      setData(res.data.items); setTotal(res.data.total)
    } finally { setLoading(false) }
  }
  useEffect(() => { fetchData(1); setPage(1) }, [onlyCompetitor]) // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => { setEditing(null); form.resetFields(); form.setFieldsValue({ is_competitor: false }); setModalOpen(true) }
  const openEdit = (r: CustomerEquipment) => {
    setEditing(r)
    form.setFieldsValue({ ...r, replace_plan_date: r.replace_plan_date ? dayjs(r.replace_plan_date) : undefined })
    if (r.customer_id && r.customer_name) customerSelect.setInitialOption({ label: r.customer_name, value: r.customer_id })
    setModalOpen(true)
  }
  const handleSubmit = async () => {
    let values
    try { values = await form.validateFields() } catch { return }
    const payload: Record<string, unknown> = {
      ...values, replace_plan_date: values.replace_plan_date ? values.replace_plan_date.format('YYYY-MM-DD') : undefined,
    }
    if (values.customer_id) {
      const opt = customerSelect.options.find((o) => o.value === values.customer_id)
      if (opt) payload.customer_name = opt.label
    }
    try {
      if (editing) { await equipmentApi.updateEquipment(editing.id, payload); message.success('已更新') }
      else { await equipmentApi.createEquipment(payload); message.success('已登记') }
      setModalOpen(false); fetchData()
    } catch { message.error('保存失败') }
  }
  const doDelete = (r: CustomerEquipment) => Modal.confirm({
    title: '删除设备', content: `确认删除「${r.name}」？`, okType: 'danger',
    onOk: async () => { await equipmentApi.deleteEquipment(r.id); message.success('已删除'); fetchData() },
  })
  const doRenew = async () => {
    if (!renewTarget) return
    const v = await renewForm.validateFields().catch(() => null)
    if (!v) return
    try {
      await equipmentApi.toRenewal(renewTarget.id, { ...v, close_date_expect: v.close_date_expect ? v.close_date_expect.format('YYYY-MM-DD') : undefined })
      message.success('已生成替换商机'); setRenewTarget(null)
    } catch { message.error('生成失败') }
  }

  const columns: ColumnsType<CustomerEquipment> = [
    { title: '客户', dataIndex: 'customer_name', width: 170, ellipsis: true, render: (v) => v || '-' },
    { title: '设备名称', dataIndex: 'name', width: 130 },
    { title: '规格型号', dataIndex: 'spec', width: 120, render: (v) => v || '-' },
    { title: '供货厂家', dataIndex: 'supplier', width: 130, render: (v) => v || '-' },
    { title: '竞品', dataIndex: 'is_competitor', width: 70, render: (v) => v ? <Tag color="red">竞品</Tag> : <Tag>自有</Tag> },
    { title: '使用年限', dataIndex: 'usage_years', width: 90, align: 'right', render: (v) => v != null ? `${v} 年` : '-' },
    { title: '计划更换', dataIndex: 'replace_plan_date', width: 120, render: (v) => v || '-' },
    {
      title: '', key: 'actions', width: 190, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          {r.is_competitor && <a className="text-emerald-600 text-sm font-bold px-2" onClick={() => { setRenewTarget(r); renewForm.resetFields(); renewForm.setFieldsValue({ name: `${r.customer_name || ''} ${r.name} 替换商机`.trim() }) }}>生成替换商机</a>}
          <a className="text-primary text-sm px-2" onClick={() => openEdit(r)}>编辑</a>
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
            <Input placeholder="设备 / 客户 / 厂家" prefix={<SearchOutlined className="text-slate-400" />} value={keyword}
              onChange={(e) => setKeyword(e.target.value)} onPressEnter={() => { setPage(1); fetchData(1) }} allowClear style={{ width: 220 }} />
            <Space><span className="text-sm text-slate-500">仅竞品</span><Switch checked={onlyCompetitor} onChange={setOnlyCompetitor} /></Space>
            <Button onClick={() => { setPage(1); fetchData(1) }}>筛选</Button>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>登记设备</Button>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={data} loading={loading} scroll={{ x: 1100 }}
          pagination={{ current: page, total, pageSize, showTotal: (t) => `共 ${t} 条`, onChange: (p) => { setPage(p); fetchData(p) } }} />
      </div>

      <Modal title={editing ? '编辑设备' : '登记设备'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} okText="保存" destroyOnClose width={600}>
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="customer_id" label="客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select showSearch filterOption={false} placeholder="搜索客户" options={customerSelect.options} loading={customerSelect.loading}
              onSearch={customerSelect.onSearch} onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} disabled={!!editing} />
          </Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="name" label="设备名称" rules={[{ required: true }]}><Input /></Form.Item>
            <Form.Item name="category" label="类型"><Input placeholder="如：振动筛/给料机" /></Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="spec" label="规格型号"><Input /></Form.Item>
            <Form.Item name="supplier" label="供货厂家"><Input /></Form.Item>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <Form.Item name="usage_years" label="使用年限"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="quantity" label="数量"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="replace_plan_date" label="计划更换"><DatePicker style={{ width: '100%' }} /></Form.Item>
          </div>
          <Form.Item name="is_competitor" label="是否竞品设备" valuePropName="checked"><Switch /></Form.Item>
          <Form.Item name="condition" label="现状描述"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="spare_usage" label="备件使用情况"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      <Modal title={`生成替换商机 — ${renewTarget?.name || ''}`} open={!!renewTarget} onOk={doRenew} onCancel={() => setRenewTarget(null)} okText="生成" destroyOnClose width={480}>
        <Form form={renewForm} layout="vertical">
          <Form.Item name="name" label="商机名称"><Input /></Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="amount_expect" label="预期金额"><InputNumber min={0} style={{ width: '100%' }} prefix="¥" /></Form.Item>
            <Form.Item name="close_date_expect" label="预计成交"><DatePicker style={{ width: '100%' }} /></Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  )
}

function SurveyTab() {
  const [data, setData] = useState<CustomerProcessSurvey[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [industry, setIndustry] = useState<string | undefined>()
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<CustomerProcessSurvey | null>(null)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await equipmentApi.listSurveys({ pageNo: p, pageSize, keyword: keyword || undefined, industry })
      setData(res.data.items); setTotal(res.data.total)
    } finally { setLoading(false) }
  }
  useEffect(() => { fetchData(1); setPage(1) }, [industry]) // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => { setEditing(null); form.resetFields(); setModalOpen(true) }
  const openEdit = (r: CustomerProcessSurvey) => {
    setEditing(r)
    form.setFieldsValue({ ...r, survey_date: r.survey_date ? dayjs(r.survey_date) : undefined })
    if (r.customer_id && r.customer_name) customerSelect.setInitialOption({ label: r.customer_name, value: r.customer_id })
    setModalOpen(true)
  }
  const handleSubmit = async () => {
    let values
    try { values = await form.validateFields() } catch { return }
    const payload: Record<string, unknown> = { ...values, survey_date: values.survey_date ? values.survey_date.format('YYYY-MM-DD') : undefined }
    if (values.customer_id) {
      const opt = customerSelect.options.find((o) => o.value === values.customer_id)
      if (opt) payload.customer_name = opt.label
    }
    try {
      if (editing) { await equipmentApi.updateSurvey(editing.id, payload); message.success('已更新') }
      else { await equipmentApi.createSurvey(payload); message.success('已创建') }
      setModalOpen(false); fetchData()
    } catch { message.error('保存失败') }
  }
  const doDelete = (r: CustomerProcessSurvey) => Modal.confirm({
    title: '删除调研', content: `确认删除「${r.customer_name}」的工艺调研？`, okType: 'danger',
    onOk: async () => { await equipmentApi.deleteSurvey(r.id); message.success('已删除'); fetchData() },
  })

  const columns: ColumnsType<CustomerProcessSurvey> = [
    { title: '客户', dataIndex: 'customer_name', width: 180, ellipsis: true, render: (v) => v || '-' },
    { title: '行业', dataIndex: 'industry', width: 100, render: (v) => v ? <Tag>{v}</Tag> : '-' },
    { title: '主要产品', dataIndex: 'main_products', width: 150, ellipsis: true, render: (v) => v || '-' },
    { title: '年产量', dataIndex: 'annual_output', width: 110, render: (v) => v || '-' },
    { title: '工艺描述', dataIndex: 'process_desc', ellipsis: true, render: (v) => v || '-' },
    { title: '调研日期', dataIndex: 'survey_date', width: 120, render: (v) => v || '-' },
    {
      title: '', key: 'actions', width: 120, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          <a className="text-primary text-sm px-2" onClick={() => openEdit(r)}>编辑</a>
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
            <Input placeholder="客户 / 产品" prefix={<SearchOutlined className="text-slate-400" />} value={keyword}
              onChange={(e) => setKeyword(e.target.value)} onPressEnter={() => { setPage(1); fetchData(1) }} allowClear style={{ width: 220 }} />
            <Select placeholder="行业" allowClear style={{ width: 140 }} value={industry} onChange={setIndustry} options={INDUSTRY_OPTIONS} />
            <Button onClick={() => { setPage(1); fetchData(1) }}>筛选</Button>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建调研</Button>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={data} loading={loading} scroll={{ x: 1100 }}
          pagination={{ current: page, total, pageSize, showTotal: (t) => `共 ${t} 条`, onChange: (p) => { setPage(p); fetchData(p) } }} />
      </div>

      <Modal title={editing ? '编辑工艺调研' : '新建工艺调研'} open={modalOpen} onOk={handleSubmit} onCancel={() => setModalOpen(false)} okText="保存" destroyOnClose width={620}>
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="customer_id" label="客户" rules={[{ required: true, message: '请选择客户' }]}>
            <Select showSearch filterOption={false} placeholder="搜索客户" options={customerSelect.options} loading={customerSelect.loading}
              onSearch={customerSelect.onSearch} onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} disabled={!!editing} />
          </Form.Item>
          <div className="grid grid-cols-3 gap-3">
            <Form.Item name="industry" label="行业"><Select options={INDUSTRY_OPTIONS} allowClear /></Form.Item>
            <Form.Item name="main_products" label="主要产品"><Input /></Form.Item>
            <Form.Item name="annual_output" label="年产量"><Input /></Form.Item>
          </div>
          <Form.Item name="branch_info" label="下属分厂情况"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="process_desc" label="客户工艺描述"><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="pain_points" label="痛点/机会"><Input.TextArea rows={2} /></Form.Item>
          <Form.Item name="survey_date" label="调研日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default function EquipmentProfilePage() {
  usePageTitle('工艺设备档案')
  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">工艺设备档案</h1>
        <p className="text-sm text-slate-500 mt-0.5">客户设备台账与工艺调研（精细化营销）；竞品设备可一键转替换商机</p>
      </div>
      <Tabs items={[
        { key: 'equipment', label: '设备台账', children: <EquipmentTab /> },
        { key: 'survey', label: '工艺调研', children: <SurveyTab /> },
      ]} />
    </div>
  )
}
