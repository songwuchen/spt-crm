import { useState, useEffect, useRef } from 'react'
import {
  Table, Button, Input, Space, Select, Modal, Form, InputNumber, DatePicker, message,
  Tag, Drawer, Statistic, Tooltip, Empty, Upload, Alert, Radio,
} from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, DollarOutlined, UploadOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import { commissionApi } from '@/api/commission'
import type { Commission, CommissionPayout, CommissionSummary } from '@/api/types'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'

const STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '待审', value: 'submitted' },
  { label: '已核准', value: 'approved' },
  { label: '已结清', value: 'paid' },
]
const STATUS_LABEL: Record<string, string> = Object.fromEntries(STATUS_OPTIONS.map(o => [o.value, o.label]))
const STATUS_COLOR: Record<string, string> = { draft: 'default', submitted: 'gold', approved: 'blue', paid: 'green' }

const money = (v?: number) => (v != null ? `¥${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '-')
const pct = (v?: number) => (v != null ? `${(Number(v) * 100).toFixed(2)}%` : '-')

export default function CommissionPage() {
  usePageTitle('业务提成')
  const [data, setData] = useState<Commission[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [summary, setSummary] = useState<CommissionSummary[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<Commission | null>(null)
  const [form] = Form.useForm()
  const ownerSelect = useUserSelect()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  // 批量导入提成单
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ created: number; skipped: number; errors: string[] } | null>(null)
  const doImport = async () => {
    if (!importFile) { message.warning('请选择文件'); return }
    setImporting(true); setImportResult(null)
    try {
      const res = await commissionApi.importRecords(importFile)
      setImportResult(res.data)
      if (res.data.errors.length === 0) {
        message.success(`成功导入 ${res.data.created} 条`)
        setImportOpen(false); setImportFile(null); fetchData()
      }
    } catch { message.error('导入失败') } finally { setImporting(false) }
  }
  // payout drawer
  const [payoutOpen, setPayoutOpen] = useState(false)
  const [payoutTarget, setPayoutTarget] = useState<Commission | null>(null)
  const [payouts, setPayouts] = useState<CommissionPayout[]>([])
  const [payoutForm] = Form.useForm()

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await commissionApi.list({ pageNo: p, pageSize, keyword: keyword || undefined, status, ...view.buildParams() })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  const fetchSummary = async () => {
    try {
      const res = await commissionApi.summary()
      setSummary(res.data || [])
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchData(1); setPage(1); fetchSummary() }, [status]) // eslint-disable-line react-hooks/exhaustive-deps

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取（reload 在 state 更新后再触发，避免读到旧值）
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload]) // eslint-disable-line react-hooks/exhaustive-deps

  const totals = summary.reduce((acc, s) => ({
    accrued: acc.accrued + s.accrued_total,
    paid: acc.paid + s.paid_total,
    payable: acc.payable + s.payable_total,
  }), { accrued: 0, paid: 0, payable: 0 })

  const openCreate = () => {
    setEditing(null)
    form.resetFields()
    form.setFieldsValue({
      contract_amount: 0, received_amount: 0,
      commission_mode: 'rate', commission_rate: 0.01, commission_amount: 0,
      deduction_freight: 0, deduction_service: 0, deduction_entertain: 0, deduction_rebate: 0,
    })
    setModalOpen(true)
  }

  const openEdit = (r: Commission) => {
    setEditing(r)
    form.setFieldsValue({ ...r, commission_mode: r.commission_mode || 'rate', signed_date: r.signed_date ? dayjs(r.signed_date) : undefined })
    if (r.owner_id && r.owner_name) ownerSelect.setInitialOption({ label: r.owner_name, value: r.owner_id })
    setModalOpen(true)
  }

  const handleSubmit = async () => {
    let values
    try { values = await form.validateFields() } catch { return }
    const payload: Record<string, unknown> = {
      ...values,
      signed_date: values.signed_date ? values.signed_date.format('YYYY-MM-DD') : undefined,
    }
    if (values.owner_id) {
      const opt = ownerSelect.options.find((o) => o.value === values.owner_id)
      if (opt) payload.owner_name = opt.label
    }
    try {
      if (editing) { await commissionApi.update(editing.id, payload); message.success('已更新') }
      else { await commissionApi.create(payload); message.success('已创建') }
      setModalOpen(false)
      fetchData(); fetchSummary()
    } catch { message.error('保存失败') }
  }

  const handleDelete = (r: Commission) => {
    Modal.confirm({
      title: '删除提成单', content: `确认删除 ${r.record_no}？`, okType: 'danger',
      onOk: async () => { await commissionApi.remove(r.id); message.success('已删除'); fetchData(); fetchSummary() },
    })
  }

  const handleRecalc = async (r: Commission) => {
    try {
      await commissionApi.recalc(r.id)
      message.success('已按回款重算')
      fetchData(); fetchSummary()
    } catch { message.error('重算失败') }
  }

  const openPayout = async (r: Commission) => {
    setPayoutTarget(r)
    payoutForm.resetFields()
    payoutForm.setFieldsValue({ amount: r.current_amount, paid_at: dayjs() })
    setPayoutOpen(true)
    try { const res = await commissionApi.listPayouts(r.id); setPayouts(res.data || []) } catch { setPayouts([]) }
  }

  const submitPayout = async () => {
    if (!payoutTarget) return
    let values
    try { values = await payoutForm.validateFields() } catch { return }
    try {
      await commissionApi.addPayout(payoutTarget.id, {
        ...values, paid_at: values.paid_at ? values.paid_at.format('YYYY-MM-DD') : undefined,
      })
      message.success('已登记支付')
      const res = await commissionApi.listPayouts(payoutTarget.id)
      setPayouts(res.data || [])
      payoutForm.resetFields()
      fetchData(); fetchSummary()
    } catch { message.error('支付登记失败') }
  }

  const handleExport = () => {
    const qs = new URLSearchParams()
    if (keyword) qs.set('keyword', keyword)
    if (status) qs.set('status', status)
    const q = qs.toString()
    downloadFile(`/api/v1/commissions/export/excel${q ? `?${q}` : ''}`, 'commissions.xlsx')
  }

  const columns: ColumnsType<Commission> = [
    { title: '提成单号', dataIndex: 'record_no', width: 150, fixed: 'left', render: (v) => <span className="font-mono text-xs">{v}</span> },
    { title: '客户', dataIndex: 'customer_name', width: 180, render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '业务员', dataIndex: 'owner_name', width: 90, render: (v) => v || '-' },
    { title: '合同额', dataIndex: 'contract_amount', width: 130, align: 'right', render: money },
    { title: '累计回款', dataIndex: 'received_amount', width: 130, align: 'right', render: money },
    { title: '结算比例', dataIndex: 'settle_rate', width: 90, align: 'right', render: pct },
    { title: '提成', dataIndex: 'commission_rate', width: 110, align: 'right',
      render: (_, r) => (r.commission_mode === 'amount'
        ? <Tooltip title="按固定金额"><span>{money(r.commission_amount)}</span></Tooltip>
        : pct(r.commission_rate)) },
    { title: '应计奖金', dataIndex: 'accrued_amount', width: 130, align: 'right', render: (v) => <span className="font-semibold text-slate-800">{money(v)}</span> },
    { title: '已提', dataIndex: 'paid_amount', width: 120, align: 'right', render: money },
    { title: '本次可提', dataIndex: 'current_amount', width: 130, align: 'right', render: (v) => <span className="font-semibold text-emerald-600">{money(v)}</span> },
    { title: '状态', dataIndex: 'status', width: 90, render: (v) => <Tag color={STATUS_COLOR[v] || 'default'}>{STATUS_LABEL[v] || v}</Tag> },
    {
      title: '', key: 'actions', width: 200, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          <Tooltip title="按项目回款重算"><a className="text-slate-500 text-sm px-2" onClick={() => handleRecalc(r)}>重算</a></Tooltip>
          <a className="text-emerald-600 text-sm font-bold px-2" onClick={() => openPayout(r)}>支付</a>
          <a className="text-primary text-sm px-2" onClick={() => openEdit(r)}>编辑</a>
          <a className="text-rose-500 text-sm px-2" onClick={() => handleDelete(r)}>删除</a>
        </Space>
      ),
    },
  ]

  const view = useListView<Commission>('commission', columns, { pageKey: 'commissions' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">业务提成</h1>
          <p className="text-sm text-slate-500 mt-0.5">回款驱动的业务奖金核算：按比例 应计奖金 = (合同额 − 扣减) × 提成比例 × 回款结算比例；按金额 应计奖金 = 提成金额 × 回款结算比例</p>
        </div>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出台账</Button>
          <Button icon={<UploadOutlined />} onClick={() => { setImportFile(null); setImportResult(null); setImportOpen(true) }}>批量导入</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建提成单</Button>
        </Space>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <Statistic title="应计奖金合计" value={totals.accrued} precision={2} prefix="¥" valueStyle={{ color: '#0f172a' }} />
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <Statistic title="已支付合计" value={totals.paid} precision={2} prefix="¥" valueStyle={{ color: '#64748b' }} />
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <Statistic title="待支付合计" value={totals.payable} precision={2} prefix="¥" valueStyle={{ color: '#059669' }} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="提成单号 / 客户 / 业务员"
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPage(1); fetchData(1) }} allowClear style={{ width: 240 }}
          />
          <Select placeholder="状态" allowClear style={{ width: 140 }} value={status} onChange={setStatus} options={STATUS_OPTIONS} />
          <Button onClick={() => { setPage(1); fetchData(1) }}>筛选</Button>
          <ListToolbar resource="commission" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id" columns={view.columns} dataSource={data} loading={loading}
          scroll={{ x: 1500 }}
          pagination={{
            current: page, total, pageSize, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPage(p); fetchData(p) },
          }}
        />
      </div>

      {/* Create / Edit modal */}
      <Modal
        title={editing ? '编辑提成单' : '新建提成单'} open={modalOpen}
        onOk={handleSubmit} onCancel={() => setModalOpen(false)} okText="保存" destroyOnClose width={640}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="customer_name" label="客户名称"><Input placeholder="客户名称" /></Form.Item>
            <Form.Item name="owner_id" label="业务员">
              <Select showSearch filterOption={false} allowClear placeholder="搜索用户"
                options={ownerSelect.options} loading={ownerSelect.loading}
                onSearch={ownerSelect.onSearch} onDropdownVisibleChange={ownerSelect.onDropdownVisibleChange} />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="contract_amount" label="合同额" rules={[{ required: true }]}>
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="received_amount" label="累计回款"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="commission_mode" label="提成方式">
              <Radio.Group optionType="button" buttonStyle="solid"
                options={[{ label: '按比例', value: 'rate' }, { label: '按金额', value: 'amount' }]} />
            </Form.Item>
            <Form.Item noStyle shouldUpdate={(p, c) => p.commission_mode !== c.commission_mode}>
              {() => (form.getFieldValue('commission_mode') === 'amount' ? (
                <Form.Item name="commission_amount" label="提成金额(元)" tooltip="固定提成金额，应计奖金 = 提成金额 × 回款结算比例">
                  <InputNumber min={0} style={{ width: '100%' }} />
                </Form.Item>
              ) : (
                <Form.Item name="commission_rate" label="提成比例(0-1)">
                  <InputNumber min={0} max={1} step={0.001} style={{ width: '100%' }} />
                </Form.Item>
              ))}
            </Form.Item>
          </div>
          <div className="grid grid-cols-4 gap-3">
            <Form.Item name="deduction_freight" label="运费"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="deduction_service" label="服务费"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="deduction_entertain" label="招待费"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
            <Form.Item name="deduction_rebate" label="返还款"><InputNumber min={0} style={{ width: '100%' }} /></Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="signed_date" label="签订日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
            {editing && (
              <Form.Item name="status" label="状态"><Select options={STATUS_OPTIONS} /></Form.Item>
            )}
          </div>
          <Form.Item name="remark" label="备注"><Input.TextArea rows={2} /></Form.Item>
          <p className="text-xs text-slate-400">保存后系统自动计算结算比例、应计奖金与本次可提金额。</p>
        </Form>
      </Modal>

      {/* Payout drawer */}
      <Drawer
        title={`提成支付 — ${payoutTarget?.record_no || ''}`} open={payoutOpen}
        onClose={() => setPayoutOpen(false)} width={460}
      >
        {payoutTarget && (
          <div className="mb-4 grid grid-cols-2 gap-3">
            <Statistic title="应计奖金" value={payoutTarget.accrued_amount} precision={2} prefix="¥" />
            <Statistic title="本次可提" value={payoutTarget.current_amount} precision={2} prefix="¥" valueStyle={{ color: '#059669' }} />
          </div>
        )}
        <Form form={payoutForm} layout="vertical">
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="amount" label="支付金额" rules={[{ required: true, message: '请输入金额' }]}>
              <InputNumber min={0} style={{ width: '100%' }} prefix="¥" />
            </Form.Item>
            <Form.Item name="paid_at" label="支付日期"><DatePicker style={{ width: '100%' }} /></Form.Item>
          </div>
          <Form.Item name="method" label="支付方式"><Input placeholder="如：工资发放 / 银行转账" /></Form.Item>
          <Form.Item name="remark" label="备注"><Input.TextArea rows={2} /></Form.Item>
          <Button type="primary" icon={<DollarOutlined />} block onClick={submitPayout}>登记支付</Button>
        </Form>
        <div className="mt-6">
          <div className="text-sm font-semibold text-slate-700 mb-2">支付记录</div>
          {payouts.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无支付" /> : (
            <div className="space-y-2">
              {payouts.map((p) => (
                <div key={p.id} className="flex items-center justify-between border border-slate-100 rounded-lg px-3 py-2">
                  <div>
                    <div className="font-semibold text-emerald-600">{money(p.amount)}</div>
                    <div className="text-xs text-slate-400">{p.paid_at || '-'} · {p.method || '—'}</div>
                  </div>
                  <div className="text-xs text-slate-400">{p.created_by_name}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </Drawer>

      {/* 批量导入提成单 */}
      <Modal title="批量导入提成单" open={importOpen} onOk={doImport} confirmLoading={importing}
        onCancel={() => { setImportOpen(false); setImportFile(null); setImportResult(null) }} okText="开始导入" width={580}>
        <div className="space-y-4 py-1">
          <div className="text-sm text-slate-500">
            支持 Excel(.xlsx) 或 CSV，第一行为表头。列顺序：
            <div className="mt-2 bg-slate-50 rounded p-2 text-sm text-slate-700 break-all">客户名称、负责人、部门、签约日期、合同金额、回款金额、运费扣减、服务扣减、招待扣减、返利扣减、提成比例(0-1)、备注</div>
            <div className="mt-1 text-sm text-slate-400">提成比例填小数（如 0.05 表示 5%），留空则按提成政策自动套用；应计奖金由系统计算。</div>
            <Button type="link" size="small" className="px-0 mt-1" icon={<DownloadOutlined />}
              onClick={() => downloadFile('/api/v1/commissions/import/template', 'commissions_template.xlsx')}>下载导入模板</Button>
          </div>
          <Upload.Dragger maxCount={1} accept=".xlsx,.xls,.csv" beforeUpload={(f) => { setImportFile(f as File); setImportResult(null); return false }}
            onRemove={() => setImportFile(null)} fileList={importFile ? [{ uid: '1', name: importFile.name } as any] : []}>
            <p className="text-slate-500"><UploadOutlined className="mr-1" />点击或拖拽文件到此处</p>
          </Upload.Dragger>
          {importResult && (
            <div className="space-y-2">
              <Alert type={importResult.errors.length === 0 ? 'success' : 'warning'} showIcon
                message={`导入完成：成功 ${importResult.created} 条，跳过 ${importResult.skipped} 条，失败 ${importResult.errors.length} 条`} />
              {importResult.errors.length > 0 && (
                <div className="max-h-40 overflow-y-auto bg-red-50 rounded p-2">
                  {importResult.errors.map((e, i) => (<div key={i} className="text-sm text-red-600">{e}</div>))}
                </div>
              )}
            </div>
          )}
        </div>
      </Modal>
    </div>
  )
}
