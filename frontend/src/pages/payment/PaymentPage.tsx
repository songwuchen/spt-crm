import { useState, useEffect } from 'react'
import { Table, Tabs, Tag, Select, Input, Button, Popconfirm, Modal, Form, InputNumber, DatePicker, Upload, Alert, message } from 'antd'
import { SearchOutlined, DownloadOutlined, DeleteOutlined, PlusOutlined, UploadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { downloadFile } from '@/utils/download'
import { paymentApi } from '@/api/payment'
import { projectApi } from '@/api/project'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'

interface PlanRow {
  id: string; project_id: string; plan_no: string; due_date?: string | null
  amount?: number | null; status: string; remark?: string
  project_name?: string; project_code?: string; created_at: string
}

interface RecordRow {
  id: string; project_id: string; received_date?: string | null
  amount?: number | null; channel?: string; reference_no?: string
  remark?: string; created_by_name?: string
  project_name?: string; project_code?: string; created_at: string
}

interface InvoiceRow {
  id: string; project_id: string; invoice_no: string
  amount?: number | null; invoice_date?: string | null; status: string
  remark?: string; created_by_name?: string
  project_name?: string; project_code?: string; created_at: string
}

interface PaymentOv {
  total_planned: number; total_received: number
  overdue_count: number; overdue_amount: number
  upcoming_30d_amount: number; collection_rate: number
}

const planStatusConfig: Record<string, { label: string; color: string }> = {
  pending: { label: '待回款', color: 'blue' },
  paid: { label: '已回款', color: 'green' },
  overdue: { label: '逾期', color: 'red' },
}

export default function PaymentPage() {
  usePageTitle('回款管理')
  const navigate = useNavigate()
  const [overview, setOverview] = useState<PaymentOv | null>(null)

  // Plans
  const [plans, setPlans] = useState<PlanRow[]>([])
  const [planTotal, setPlanTotal] = useState(0)
  const [planPage, setPlanPage] = useState(1)
  const [planLoading, setPlanLoading] = useState(false)
  const [planStatus, setPlanStatus] = useState<string | undefined>()
  const [planKeyword, setPlanKeyword] = useState('')

  // Records
  const [records, setRecords] = useState<RecordRow[]>([])
  const [recordTotal, setRecordTotal] = useState(0)
  const [recordPage, setRecordPage] = useState(1)
  const [recordLoading, setRecordLoading] = useState(false)
  const [recordKeyword, setRecordKeyword] = useState('')

  // Invoices
  const [invoices, setInvoices] = useState<InvoiceRow[]>([])
  const [invoiceTotal, setInvoiceTotal] = useState(0)
  const [invoicePage, setInvoicePage] = useState(1)
  const [invoiceLoading, setInvoiceLoading] = useState(false)
  const [invoiceKeyword, setInvoiceKeyword] = useState('')

  const { hasPermission } = usePermission()
  const canEdit = hasPermission('payment:edit')

  // 商机搜索（新增回款时需指定关联商机）
  const [projOpts, setProjOpts] = useState<{ label: string; value: string }[]>([])
  const [projLoading, setProjLoading] = useState(false)
  const searchProjects = async (kw?: string) => {
    setProjLoading(true)
    try {
      const r = await projectApi.list({ pageNo: 1, pageSize: 20, keyword: kw || undefined })
      setProjOpts((r.data.items || []).map((p) => ({ label: `${p.name}（${p.project_code}）`, value: p.id })))
    } catch { /* ignore */ } finally { setProjLoading(false) }
  }

  // 新增回款（计划/到账/发票），复用按商机的创建端点
  const [createType, setCreateType] = useState<'plan' | 'record' | 'invoice'>('record')
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm] = Form.useForm()
  const [creating, setCreating] = useState(false)
  const createTitle = { plan: '新增回款计划', record: '新增到账记录', invoice: '新增发票' }[createType]
  const openCreate = (type: 'plan' | 'record' | 'invoice') => {
    setCreateType(type); createForm.resetFields(); setProjOpts([]); searchProjects(); setCreateOpen(true)
  }
  const handleCreate = async () => {
    let v
    try { v = await createForm.validateFields() } catch { return }
    const pid = v.project_id as string
    setCreating(true)
    try {
      if (createType === 'plan') {
        await paymentApi.createPlan(pid, { due_date: v.due_date ? v.due_date.format('YYYY-MM-DD') : undefined, amount: v.amount, status: v.status || 'pending', remark: v.remark })
      } else if (createType === 'record') {
        await paymentApi.createRecord(pid, { received_date: v.received_date ? v.received_date.format('YYYY-MM-DD') : undefined, amount: v.amount, channel: v.channel, reference_no: v.reference_no, remark: v.remark })
      } else {
        await paymentApi.createInvoice(pid, { invoice_no: v.invoice_no, amount: v.amount, invoice_date: v.invoice_date ? v.invoice_date.format('YYYY-MM-DD') : undefined, remark: v.remark })
      }
      message.success('已新增')
      setCreateOpen(false)
      fetchOverview()
      if (createType === 'plan') fetchPlans()
      else if (createType === 'record') fetchRecords()
      else fetchInvoices()
    } catch { message.error('新增失败') } finally { setCreating(false) }
  }

  // 批量导入到账记录
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ created: number; skipped: number; errors: string[] } | null>(null)
  const doImport = async () => {
    if (!importFile) { message.warning('请选择文件'); return }
    setImporting(true); setImportResult(null)
    try {
      const res = await paymentApi.importRecords(importFile)
      setImportResult(res.data)
      if (res.data.errors.length === 0) {
        message.success(`成功导入 ${res.data.created} 条`)
        setImportOpen(false); setImportFile(null); fetchRecords(); fetchOverview()
      }
    } catch { message.error('导入失败') } finally { setImporting(false) }
  }

  const fetchOverview = () => {
    dashboardApi.paymentOverview().then((r: any) => {
      if (r.data) setOverview(r.data)
    }).catch(() => {})
  }

  const fetchPlans = async (page = planPage, st = planStatus, kw = planKeyword) => {
    setPlanLoading(true)
    try {
      const r = await paymentApi.listAllPlans({ pageNo: page, pageSize: 20, status: st, keyword: kw || undefined }) as any
      setPlans(r.data?.items || [])
      setPlanTotal(r.data?.total || 0)
    } finally { setPlanLoading(false) }
  }

  const fetchRecords = async (page = recordPage, kw = recordKeyword) => {
    setRecordLoading(true)
    try {
      const r = await paymentApi.listAllRecords({ pageNo: page, pageSize: 20, keyword: kw || undefined }) as any
      setRecords(r.data?.items || [])
      setRecordTotal(r.data?.total || 0)
    } finally { setRecordLoading(false) }
  }

  const fetchInvoices = async (page = invoicePage, kw = invoiceKeyword) => {
    setInvoiceLoading(true)
    try {
      const r = await paymentApi.listAllInvoices({ pageNo: page, pageSize: 20, keyword: kw || undefined }) as any
      setInvoices(r.data?.items || [])
      setInvoiceTotal(r.data?.total || 0)
    } finally { setInvoiceLoading(false) }
  }

  const handleDeletePlan = async (id: string) => {
    try {
      await paymentApi.deletePlan(id)
      message.success('删除成功')
      fetchPlans(); fetchOverview()
    } catch { message.error('删除失败') }
  }

  const handleDeleteRecord = async (id: string) => {
    try {
      await paymentApi.deleteRecord(id)
      message.success('删除成功')
      fetchRecords(); fetchOverview()
    } catch { message.error('删除失败') }
  }

  const handleDeleteInvoice = async (id: string) => {
    try {
      await paymentApi.deleteInvoice(id)
      message.success('删除成功')
      fetchInvoices()
    } catch { message.error('删除失败') }
  }

  useEffect(() => { fetchOverview(); fetchPlans(); fetchRecords(); fetchInvoices() }, [])

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">回款管理</h1>
          <p className="text-sm text-slate-500 mt-1">跨项目的回款计划、到账记录和发票管理</p>
        </div>
        <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/payment/export/excel', 'payments.xlsx')}>导出</Button>
      </div>

      {/* Overview Cards */}
      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
            <div className="text-sm font-bold text-slate-400 uppercase">计划总额</div>
            <div className="text-xl font-black text-slate-900 mt-1">¥{(overview.total_planned / 10000).toFixed(1)}万</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
            <div className="text-sm font-bold text-slate-400 uppercase">已回款</div>
            <div className="text-xl font-black text-emerald-600 mt-1">¥{(overview.total_received / 10000).toFixed(1)}万</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
            <div className="text-sm font-bold text-slate-400 uppercase">回款率</div>
            <div className={`text-xl font-black mt-1 ${overview.collection_rate >= 80 ? 'text-emerald-600' : overview.collection_rate >= 50 ? 'text-amber-600' : 'text-red-500'}`}>
              {overview.collection_rate}%
            </div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
            <div className="text-sm font-bold text-slate-400 uppercase">逾期笔数</div>
            <div className={`text-xl font-black mt-1 ${overview.overdue_count > 0 ? 'text-red-500' : 'text-slate-900'}`}>{overview.overdue_count}</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
            <div className="text-sm font-bold text-slate-400 uppercase">逾期金额</div>
            <div className="text-xl font-black text-red-500 mt-1">¥{(overview.overdue_amount / 10000).toFixed(1)}万</div>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 text-center">
            <div className="text-sm font-bold text-slate-400 uppercase">30天内到期</div>
            <div className="text-xl font-black text-amber-600 mt-1">¥{(overview.upcoming_30d_amount / 10000).toFixed(1)}万</div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <Tabs defaultActiveKey="plans" className="px-4 pt-2" items={[
          {
            key: 'plans',
            label: `回款计划 (${planTotal})`,
            children: (
              <div>
                <div className="flex items-center gap-3 mb-4 flex-wrap">
                  <Input prefix={<SearchOutlined />} placeholder="搜索计划编号..." allowClear
                    value={planKeyword} onChange={(e) => setPlanKeyword(e.target.value)}
                    onPressEnter={() => { setPlanPage(1); fetchPlans(1, planStatus, planKeyword) }}
                    style={{ width: 200 }} />
                  <Select placeholder="状态" allowClear style={{ width: 120 }}
                    value={planStatus}
                    onChange={(v) => { setPlanStatus(v); setPlanPage(1); fetchPlans(1, v, planKeyword) }}
                    options={Object.entries(planStatusConfig).map(([k, v]) => ({ value: k, label: v.label }))} />
                  {canEdit && <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate('plan')} className="ml-auto">新增计划</Button>}
                </div>
                <Table rowKey="id" dataSource={plans} loading={planLoading} size="small" scroll={{ x: 800 }}
                  pagination={{ current: planPage, total: planTotal, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
                    onChange: (p) => { setPlanPage(p); fetchPlans(p) } }}
                  columns={[
                    { title: '计划编号', dataIndex: 'plan_no', width: 120,
                      render: (v: string) => <span className="font-mono font-bold text-sm">{v}</span> },
                    { title: '关联商机', key: 'project', width: 180,
                      render: (_: unknown, r: PlanRow) => (
                        <a className="text-primary text-sm cursor-pointer" onClick={() => navigate(`/opportunities/${r.project_id}`)}>
                          {r.project_name || r.project_code || '查看'}
                        </a>
                      ) },
                    { title: '到期日', dataIndex: 'due_date', width: 110,
                      render: (v: string | null) => {
                        if (!v) return '-'
                        const isOverdue = new Date(v) < new Date(new Date().toDateString())
                        return <span className={`text-sm ${isOverdue ? 'text-red-500 font-bold' : ''}`}>{v}</span>
                      } },
                    { title: '金额', dataIndex: 'amount', width: 120,
                      render: (v: number | null) => v != null ? <span className="font-bold">¥{v.toLocaleString()}</span> : '-' },
                    { title: '状态', dataIndex: 'status', width: 90,
                      render: (v: string) => {
                        const cfg = planStatusConfig[v]
                        return cfg ? <Tag color={cfg.color}>{cfg.label}</Tag> : v
                      } },
                    { title: '备注', dataIndex: 'remark', ellipsis: true, responsive: ['lg'] as any },
                    { title: '操作', key: 'action', width: 70, render: (_: unknown, r: PlanRow) => (
                      <Popconfirm title="确认删除此计划？" onConfirm={() => handleDeletePlan(r.id)} okText="删除" cancelText="取消">
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ) },
                  ]}
                />
              </div>
            ),
          },
          {
            key: 'records',
            label: `到账记录 (${recordTotal})`,
            children: (
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <Input prefix={<SearchOutlined />} placeholder="搜索凭证号..." allowClear
                    value={recordKeyword} onChange={(e) => setRecordKeyword(e.target.value)}
                    onPressEnter={() => { setRecordPage(1); fetchRecords(1, recordKeyword) }}
                    style={{ width: 200 }} />
                  {canEdit && <div className="ml-auto flex gap-2">
                    <Button icon={<UploadOutlined />} onClick={() => { setImportFile(null); setImportResult(null); setImportOpen(true) }}>导入</Button>
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate('record')}>新增到账</Button>
                  </div>}
                </div>
                <Table rowKey="id" dataSource={records} loading={recordLoading} size="small" scroll={{ x: 800 }}
                  pagination={{ current: recordPage, total: recordTotal, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
                    onChange: (p) => { setRecordPage(p); fetchRecords(p) } }}
                  columns={[
                    { title: '到账日期', dataIndex: 'received_date', width: 110 },
                    { title: '关联商机', key: 'project', width: 180,
                      render: (_: unknown, r: RecordRow) => (
                        <a className="text-primary text-sm cursor-pointer" onClick={() => navigate(`/opportunities/${r.project_id}`)}>
                          {r.project_name || r.project_code || '查看'}
                        </a>
                      ) },
                    { title: '金额', dataIndex: 'amount', width: 120,
                      render: (v: number | null) => v != null ? <span className="font-bold text-emerald-600">¥{v.toLocaleString()}</span> : '-' },
                    { title: '渠道', dataIndex: 'channel', width: 100 },
                    { title: '凭证号', dataIndex: 'reference_no', width: 140,
                      render: (v: string) => v ? <span className="font-mono text-sm">{v}</span> : '-' },
                    { title: '记录人', dataIndex: 'created_by_name', width: 90, responsive: ['lg'] as any },
                    { title: '备注', dataIndex: 'remark', ellipsis: true, responsive: ['lg'] as any },
                    { title: '操作', key: 'action', width: 70, render: (_: unknown, r: RecordRow) => (
                      <Popconfirm title="确认删除此记录？" onConfirm={() => handleDeleteRecord(r.id)} okText="删除" cancelText="取消">
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ) },
                  ]}
                />
              </div>
            ),
          },
          {
            key: 'invoices',
            label: `发票 (${invoiceTotal})`,
            children: (
              <div>
                <div className="flex items-center gap-3 mb-4">
                  <Input prefix={<SearchOutlined />} placeholder="搜索发票号..." allowClear
                    value={invoiceKeyword} onChange={(e) => setInvoiceKeyword(e.target.value)}
                    onPressEnter={() => { setInvoicePage(1); fetchInvoices(1, invoiceKeyword) }}
                    style={{ width: 200 }} />
                  {canEdit && <Button type="primary" icon={<PlusOutlined />} onClick={() => openCreate('invoice')} className="ml-auto">新增发票</Button>}
                </div>
                <Table rowKey="id" dataSource={invoices} loading={invoiceLoading} size="small" scroll={{ x: 800 }}
                  pagination={{ current: invoicePage, total: invoiceTotal, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
                    onChange: (p) => { setInvoicePage(p); fetchInvoices(p) } }}
                  columns={[
                    { title: '发票号', dataIndex: 'invoice_no', width: 140,
                      render: (v: string) => <span className="font-mono font-bold text-sm">{v}</span> },
                    { title: '关联商机', key: 'project', width: 180,
                      render: (_: unknown, r: InvoiceRow) => (
                        <a className="text-primary text-sm cursor-pointer" onClick={() => navigate(`/opportunities/${r.project_id}`)}>
                          {r.project_name || r.project_code || '查看'}
                        </a>
                      ) },
                    { title: '金额', dataIndex: 'amount', width: 120,
                      render: (v: number | null) => v != null ? <span className="font-bold">¥{v.toLocaleString()}</span> : '-' },
                    { title: '开票日期', dataIndex: 'invoice_date', width: 110 },
                    { title: '状态', dataIndex: 'status', width: 80,
                      render: (v: string) => <Tag color={v === 'issued' ? 'blue' : 'default'}>{v === 'issued' ? '已开' : '作废'}</Tag> },
                    { title: '记录人', dataIndex: 'created_by_name', width: 90, responsive: ['lg'] as any },
                    { title: '备注', dataIndex: 'remark', ellipsis: true, responsive: ['lg'] as any },
                    { title: '操作', key: 'action', width: 70, render: (_: unknown, r: InvoiceRow) => (
                      <Popconfirm title="确认删除此发票？" onConfirm={() => handleDeleteInvoice(r.id)} okText="删除" cancelText="取消">
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ) },
                  ]}
                />
              </div>
            ),
          },
        ]} />
      </div>

      {/* 新增回款（计划/到账/发票） */}
      <Modal title={createTitle} open={createOpen} onOk={handleCreate} confirmLoading={creating}
        onCancel={() => setCreateOpen(false)} okText="保存" width={520} destroyOnClose>
        <Form form={createForm} layout="vertical" className="mt-3">
          <Form.Item name="project_id" label="关联商机" rules={[{ required: true, message: '请选择关联商机' }]}>
            <Select showSearch filterOption={false} placeholder="搜索商机名称 / 编号"
              options={projOpts} loading={projLoading} onSearch={searchProjects}
              onDropdownVisibleChange={(o) => { if (o && projOpts.length === 0) searchProjects() }} />
          </Form.Item>
          {createType === 'plan' && (<>
            <div className="grid grid-cols-2 gap-3">
              <Form.Item name="due_date" label="到期日"><DatePicker className="w-full" /></Form.Item>
              <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]}><InputNumber className="w-full" min={0} /></Form.Item>
            </div>
            <Form.Item name="status" label="状态" initialValue="pending">
              <Select options={[{ value: 'pending', label: '待回款' }, { value: 'paid', label: '已回款' }, { value: 'overdue', label: '逾期' }]} />
            </Form.Item>
          </>)}
          {createType === 'record' && (<>
            <div className="grid grid-cols-2 gap-3">
              <Form.Item name="received_date" label="到账日期" rules={[{ required: true, message: '请选择到账日期' }]}><DatePicker className="w-full" /></Form.Item>
              <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]}><InputNumber className="w-full" min={0} /></Form.Item>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Form.Item name="channel" label="渠道"><Input placeholder="如 电汇 / 承兑" /></Form.Item>
              <Form.Item name="reference_no" label="凭证号"><Input /></Form.Item>
            </div>
          </>)}
          {createType === 'invoice' && (<>
            <div className="grid grid-cols-2 gap-3">
              <Form.Item name="invoice_no" label="发票号"><Input placeholder="留空自动生成" /></Form.Item>
              <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入金额' }]}><InputNumber className="w-full" min={0} /></Form.Item>
            </div>
            <Form.Item name="invoice_date" label="开票日期"><DatePicker className="w-full" /></Form.Item>
          </>)}
          <Form.Item name="remark" label="备注"><Input.TextArea rows={2} /></Form.Item>
        </Form>
      </Modal>

      {/* 批量导入到账记录 */}
      <Modal title="批量导入到账记录" open={importOpen} onOk={doImport} confirmLoading={importing}
        onCancel={() => { setImportOpen(false); setImportFile(null); setImportResult(null) }} okText="开始导入" width={560}>
        <div className="space-y-4 py-1">
          <div className="text-sm text-slate-500">
            支持 Excel(.xlsx) 或 CSV，第一行为表头。列顺序：
            <div className="mt-2 bg-slate-50 rounded p-2 text-sm text-slate-700 break-all">商机编号、到账日期、金额、渠道、凭证号、备注</div>
            <div className="mt-1 text-sm text-slate-400">每行按「商机编号」关联到对应商机；编号不存在的行会列入错误。</div>
            <Button type="link" size="small" className="px-0 mt-1" icon={<DownloadOutlined />}
              onClick={() => downloadFile('/api/v1/payment/records/import/template', 'payment_records_template.xlsx')}>下载导入模板</Button>
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
