import { useState, useEffect, useRef } from 'react'
import { Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, Tag, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, DeleteOutlined, AuditOutlined, SendOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { orderApi } from '@/api/order'
import { customerApi } from '@/api/customer'
import type { Order, OrderLine } from '@/api/types'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useCustomerSelect, useUserSelect } from '@/hooks/useSelectOptions'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'
import AttachmentPanel from '@/components/AttachmentPanel'
import EntityCustomFields from '@/components/lowcode/EntityCustomFields'

const STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '已确认', value: 'confirmed' },
  { label: '生产中', value: 'producing' },
  { label: '已发货', value: 'shipped' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'cancelled' },
]
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS_OPTIONS.map(o => [o.value, o.label]))
const STATUS_COLOR: Record<string, string> = { draft: 'default', confirmed: 'blue', producing: 'gold', shipped: 'cyan', completed: 'green', cancelled: 'red' }
const SHIP_LABEL: Record<string, { t: string; c: string }> = {
  none: { t: '未发货', c: 'default' }, partial: { t: '部分发货', c: 'orange' }, full: { t: '已发货', c: 'green' },
}
const money = (v?: number | null) => (v != null ? `¥${Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}` : '-')

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
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)
  const [form] = Form.useForm()
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customerSelect = useCustomerSelect()
  const ownerSelect = useUserSelect()

  // 明细合计（随数量/单价实时变化）
  const watchedLines = Form.useWatch('lines', form) as { quantity?: number; unit_price?: number }[] | undefined
  const linesTotal = (watchedLines || []).reduce((s, l) => s + (Number(l?.quantity) || 0) * (Number(l?.unit_price) || 0), 0)

  // 发货
  const [shipOpen, setShipOpen] = useState(false)
  const [shipOrder, setShipOrder] = useState<Order | null>(null)
  const [shipQty, setShipQty] = useState<Record<string, number>>({})
  const [shipping, setShipping] = useState(false)

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await orderApi.list({ pageNo: p, pageSize, keyword: keyword || undefined, status, ...view.buildParams() })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData(1); setPage(1) }, [status]) // eslint-disable-line react-hooks/exhaustive-deps

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取（reload 在 state 更新后再触发，避免读到旧值）
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload]) // eslint-disable-line react-hooks/exhaustive-deps

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    setCustomFields({})
    form.setFieldsValue({ status: 'draft', currency: 'CNY', lines: [{ product_name: '', quantity: 1, unit_price: 0 }] })
    setModalOpen(true)
  }

  const openEdit = async (record: Order) => {
    setEditing(record)
    // 拉取完整订单（含明细）回填
    let full = record
    try { full = (await orderApi.get(record.id)).data } catch { /* fall back to row */ }
    setCustomFields((full as unknown as { custom_fields_json?: Record<string, unknown> }).custom_fields_json || {})
    form.setFieldsValue({
      ...full,
      order_date: full.order_date ? dayjs(full.order_date) : undefined,
      delivery_date: full.delivery_date ? dayjs(full.delivery_date) : undefined,
      lines: (full.lines || []).map((l) => ({
        product_name: l.product_name, spec: l.spec, unit: l.unit,
        quantity: l.quantity, unit_price: l.unit_price,
      })),
    })
    // 关联客户：按 id 回查客户名再播种，否则会直接显示客户 id
    if (full.customer_id) {
      const cid = full.customer_id
      customerApi.get(cid).then((r) => {
        if (r.data?.name) customerSelect.setInitialOption({ label: r.data.name, value: cid })
      }).catch(() => {})
    }
    if (full.owner_id && full.owner_name) ownerSelect.setInitialOption({ label: full.owner_name, value: full.owner_id })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    let values
    try { values = await form.validateFields() } catch { return }
    const lines = (values.lines || []).filter((l: OrderLine) => l && l.product_name)
    const payload: Record<string, unknown> = {
      ...values,
      order_date: values.order_date ? values.order_date.format('YYYY-MM-DD') : undefined,
      delivery_date: values.delivery_date ? values.delivery_date.format('YYYY-MM-DD') : undefined,
      lines,
      custom_fields_json: customFields,
    }
    delete payload.amount // 合计金额由明细汇总，后端计算
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
      if (e?.errorFields) return
      message.error('保存失败')
    }
  }

  const handleSubmitApproval = (record: Order) => {
    Modal.confirm({
      title: '提交订单审批', content: `确认提交订单 ${record.order_no} 进入审批流程？`,
      onOk: async () => {
        try { await orderApi.submit(record.id); message.success('已提交审批，请在审批中心查看进度') }
        catch { message.error('提交失败，请确认已在「系统设置→审批策略」配置订单审批') }
        fetchData()
      },
    })
  }

  const openShip = async (record: Order) => {
    try {
      const full = (await orderApi.get(record.id)).data
      if (!full.lines || full.lines.length === 0) { message.warning('订单无明细，无法发货'); return }
      setShipOrder(full); setShipQty({}); setShipOpen(true)
    } catch { message.error('加载订单失败') }
  }

  const doShip = async (full: boolean) => {
    if (!shipOrder) return
    setShipping(true)
    try {
      if (full) {
        await orderApi.ship(shipOrder.id, { full: true })
      } else {
        const items = Object.entries(shipQty).filter(([, q]) => q > 0).map(([line_id, q]) => ({ line_id, ship_quantity: q }))
        if (!items.length) { message.warning('请填写本次发货数量，或点击全部发货'); setShipping(false); return }
        await orderApi.ship(shipOrder.id, { items })
      }
      message.success('发货已登记')
      setShipOpen(false); fetchData()
    } catch { message.error('发货失败') } finally { setShipping(false) }
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
    { title: '合计金额', dataIndex: 'amount', width: 130, render: (v, r) => v != null ? `${r.currency || ''} ${Number(v).toLocaleString()}` : '-' },
    { title: '状态', dataIndex: 'status', width: 90, render: (v) => <Tag color={STATUS_COLOR[v] || 'default'}>{STATUS_LABEL[v] || v}</Tag> },
    { title: '下单日期', dataIndex: 'order_date', width: 110, render: (v) => v || '-' },
    { title: '交付日期', dataIndex: 'delivery_date', width: 110, render: (v) => v || '-' },
    { title: '负责人', dataIndex: 'owner_name', width: 90, render: (v) => v || '-' },
    {
      title: '', key: 'actions', width: 240, fixed: 'right',
      render: (_, record) => (
        <Space size={4}>
          <a className="text-primary text-sm font-bold" onClick={() => openEdit(record)}>编辑</a>
          {(record.status === 'draft' || record.status === 'confirmed') && (
            <a className="text-amber-600 text-sm font-bold" onClick={() => handleSubmitApproval(record)}>
              <AuditOutlined /> 提交审批
            </a>
          )}
          {record.status !== 'draft' && record.status !== 'cancelled' && (
            <a className="text-cyan-600 text-sm font-bold" onClick={() => openShip(record)}>
              <SendOutlined /> 发货
            </a>
          )}
          <a className="text-rose-500 text-sm font-bold" onClick={() => handleDelete(record)}>删除</a>
        </Space>
      ),
    },
  ]

  const view = useListView<Order>('order', columns, { pageKey: 'orders' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">订单管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理客户成交订单（含产品明细、审批与发货），可关联商机与合同</p>
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
          <ListToolbar resource="order" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={view.columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 1100 }}
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
        width={860}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="customer_id" label="客户" rules={[{ required: true, message: '请选择客户' }]}>
              <Select
                showSearch filterOption={false} placeholder="搜索客户"
                options={customerSelect.options} loading={customerSelect.loading}
                onSearch={customerSelect.onSearch} onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
                disabled={!!editing}
              />
            </Form.Item>
            <Form.Item name="title" label="标题"><Input placeholder="订单标题" /></Form.Item>
          </div>

          {/* 产品明细 */}
          <div className="border border-slate-200 rounded-lg p-3 mb-4 bg-slate-50/50">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-slate-700">产品明细</span>
              <span className="text-sm text-slate-500">合计金额：<span className="font-bold text-slate-900">{money(linesTotal)}</span></span>
            </div>
            <div className="grid grid-cols-12 gap-2 text-[13px] font-bold text-slate-400 px-1 mb-1">
              <div className="col-span-3">产品名称</div>
              <div className="col-span-2">规格型号</div>
              <div className="col-span-1">单位</div>
              <div className="col-span-2">数量</div>
              <div className="col-span-2">单价</div>
              <div className="col-span-1 text-right">金额</div>
              <div className="col-span-1" />
            </div>
            <Form.List name="lines">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name }) => {
                    const ln = watchedLines?.[name]
                    const amt = (Number(ln?.quantity) || 0) * (Number(ln?.unit_price) || 0)
                    return (
                      <div key={key} className="grid grid-cols-12 gap-2 items-start mb-1">
                        <Form.Item name={[name, 'product_name']} className="col-span-3 !mb-1" rules={[{ required: true, message: '必填' }]}>
                          <Input size="small" placeholder="产品名称" />
                        </Form.Item>
                        <Form.Item name={[name, 'spec']} className="col-span-2 !mb-1"><Input size="small" placeholder="规格型号" /></Form.Item>
                        <Form.Item name={[name, 'unit']} className="col-span-1 !mb-1"><Input size="small" placeholder="台" /></Form.Item>
                        <Form.Item name={[name, 'quantity']} className="col-span-2 !mb-1"><InputNumber size="small" min={0} className="w-full" /></Form.Item>
                        <Form.Item name={[name, 'unit_price']} className="col-span-2 !mb-1"><InputNumber size="small" min={0} className="w-full" /></Form.Item>
                        <div className="col-span-1 text-right text-sm pt-1 font-medium text-slate-700">{amt.toLocaleString()}</div>
                        <div className="col-span-1 pt-1">
                          <a className="text-rose-500" onClick={() => remove(name)}><DeleteOutlined /></a>
                        </div>
                      </div>
                    )
                  })}
                  <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => add({ product_name: '', quantity: 1, unit_price: 0 })} block>
                    添加明细行
                  </Button>
                </>
              )}
            </Form.List>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="status" label="状态"><Select options={STATUS_OPTIONS} /></Form.Item>
            <Form.Item name="currency" label="币种"><Input /></Form.Item>
          </div>
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
          <EntityCustomFields entityType="order" value={customFields} onChange={setCustomFields} />
        </Form>
        {editing ? (
          <div className="border-t border-slate-100 pt-3 mt-1">
            <div className="text-sm font-semibold text-slate-600 mb-2">附件（合同扫描件、技术图纸、发货单等）</div>
            <AttachmentPanel bizType="order" bizId={editing.id} />
          </div>
        ) : (
          <div className="text-[12px] text-slate-400 mt-1">保存订单后，可在编辑里上传附件。</div>
        )}
      </Modal>

      {/* 发货 */}
      <Modal
        title={`发货 · ${shipOrder?.order_no || ''}`}
        open={shipOpen}
        onCancel={() => setShipOpen(false)}
        width={680}
        footer={[
          <Button key="cancel" onClick={() => setShipOpen(false)}>取消</Button>,
          <Button key="full" onClick={() => doShip(true)} loading={shipping}>全部发货</Button>,
          <Button key="partial" type="primary" onClick={() => doShip(false)} loading={shipping}>登记本次发货</Button>,
        ]}
      >
        <div className="text-sm text-slate-500 mb-2">
          当前发货状态：{shipOrder?.ship_status ? <Tag color={SHIP_LABEL[shipOrder.ship_status].c}>{SHIP_LABEL[shipOrder.ship_status].t}</Tag> : '-'}
          支持部分发货（填本次发货数量）或一键全部发货。
        </div>
        <Table
          rowKey="id" size="small" pagination={false}
          dataSource={shipOrder?.lines || []}
          columns={[
            { title: '产品', dataIndex: 'product_name' },
            { title: '规格', dataIndex: 'spec', render: (v: string) => v || '-' },
            { title: '数量', dataIndex: 'quantity', width: 80, align: 'right' },
            { title: '已发', dataIndex: 'shipped_quantity', width: 80, align: 'right', render: (v: number) => v || 0 },
            { title: '待发', key: 'pending', width: 80, align: 'right',
              render: (_: unknown, r: OrderLine) => Math.max(0, Number(r.quantity || 0) - Number(r.shipped_quantity || 0)) },
            { title: '本次发货', key: 'ship', width: 130,
              render: (_: unknown, r: OrderLine) => {
                const pending = Math.max(0, Number(r.quantity || 0) - Number(r.shipped_quantity || 0))
                return (
                  <InputNumber size="small" min={0} max={pending} disabled={pending <= 0}
                    value={shipQty[r.id!] ?? 0}
                    onChange={(v) => setShipQty((m) => ({ ...m, [r.id!]: Number(v) || 0 }))} />
                )
              } },
          ]}
        />
      </Modal>
    </div>
  )
}
