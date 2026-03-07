import { useState, useEffect } from 'react'
import { Button, Select, Table, Modal, Form, Input, InputNumber, Tag, Space, Descriptions, message, Timeline, Tabs, Progress, Spin } from 'antd'
import { PlusOutlined, CopyOutlined, SwapOutlined, CameraOutlined, HistoryOutlined, AuditOutlined, FileProtectOutlined, SendOutlined, RobotOutlined, FilePdfOutlined, PrinterOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import { quoteApi } from '@/api/quote'
import { downloadFile } from '@/utils/download'
import { productApi } from '@/api/product'
import { contractApi } from '@/api/contract'
import { approvalApi } from '@/api/approval'
import { userApi } from '@/api/user'
import { aiApi } from '@/api/ai'
import type { QuoteItem, QuoteVersion, QuoteLine, CostSnapshotItem, QuoteSendLogItem } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { quoteLineItemTypeLabels as itemTypeLabels, quoteStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'

const BREAKDOWN_LABELS: Record<string, string> = {
  material: '材料费', processing: '加工费', outsource: '外协费',
  install: '安装费', transport: '运输费', admin: '管理费', risk: '风险费',
}

const CHANNEL_LABELS: Record<string, string> = {
  email: '邮件', wechat: '微信', print: '打印', other: '其他',
}

export default function QuoteDetail() {
  usePageTitle('报价详情')
  const { id: projectId, qid } = useParams<{ id: string; qid: string }>()
  const navigate = useNavigate()
  const [quote, setQuote] = useState<QuoteItem | null>(null)
  const [versions, setVersions] = useState<QuoteVersion[]>([])
  const [currentVersion, setCurrentVersion] = useState<QuoteVersion | null>(null)
  const [lines, setLines] = useState<QuoteLine[]>([])
  const [selectedVersionId, setSelectedVersionId] = useState<string>('')
  const [lineModal, setLineModal] = useState(false)
  const [editingLine, setEditingLine] = useState<QuoteLine | null>(null)
  const [form] = Form.useForm()

  // Version comparison
  const [compareModal, setCompareModal] = useState(false)
  const [compareA, setCompareA] = useState<string>('')
  const [compareB, setCompareB] = useState<string>('')
  const [compareResult, setCompareResult] = useState<{ header_changes: Record<string, { old: unknown; new: unknown }>; line_diffs: { key: string; item_name: string; status: string; changes?: Record<string, unknown> }[] } | null>(null)
  const [compareLoading, setCompareLoading] = useState(false)

  // Cost snapshots
  const [snapshotModal, setSnapshotModal] = useState(false)
  const [snapshots, setSnapshots] = useState<CostSnapshotItem[]>([])
  const [snapshotForm] = Form.useForm()
  const [snapshotCreateModal, setSnapshotCreateModal] = useState(false)

  // Send logs
  const [sendLogs, setSendLogs] = useState<QuoteSendLogItem[]>([])
  const [sendModal, setSendModal] = useState(false)
  const [sendForm] = Form.useForm()

  // Submit approval
  const [approvalModal, setApprovalModal] = useState(false)
  const [selectedApprovers, setSelectedApprovers] = useState<string[]>([])
  const [approvalSubmitting, setApprovalSubmitting] = useState(false)

  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  // Product picker
  const [productPickerOpen, setProductPickerOpen] = useState(false)
  const [productSearch, setProductSearch] = useState('')
  const [productResults, setProductResults] = useState<{ id: string; product_code: string; name: string; item_type: string | null; spec: string | null; unit: string | null; unit_price: number | null; cost_price: number | null; leadtime_days: number | null }[]>([])
  const [productLoading, setProductLoading] = useState(false)

  const searchProducts = async (kw: string) => {
    setProductLoading(true)
    try {
      const res = await productApi.list({ pageNo: 1, pageSize: 20, keyword: kw || undefined, is_active: true })
      setProductResults(res.data?.items || [])
    } finally { setProductLoading(false) }
  }

  const handlePickProduct = (p: typeof productResults[0]) => {
    form.setFieldsValue({
      item_type: p.item_type || undefined,
      item_code: p.product_code,
      item_name: p.name,
      spec: p.spec || undefined,
      unit: p.unit || undefined,
      unit_price: p.unit_price,
      cost_est: p.cost_price,
      leadtime_days: p.leadtime_days,
    })
    setProductPickerOpen(false)
    message.success(`已选择: ${p.name}`)
  }

  // AI analysis
  const [aiResult, setAiResult] = useState<{
    risk_level?: string
    review_items?: { item: string; status: string; detail: string }[]
    overall_comment?: string
  } | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  const fetchQuote = async () => {
    const res = await quoteApi.get(qid!)
    const d = res.data
    setQuote(d)
    setVersions(d.versions || [])
    setCurrentVersion(d.current_version || null)
    setLines(d.lines || [])
    if (d.current_version) {
      setSelectedVersionId(d.current_version.id)
    }
  }

  const fetchVersion = async (vid: string) => {
    const res = await quoteApi.getVersion(vid)
    setCurrentVersion(res.data)
    setLines(res.data.lines || [])
    setSelectedVersionId(vid)
  }

  const fetchSendLogs = async () => {
    if (!qid) return
    const res = await quoteApi.listSendLogs(qid)
    setSendLogs(res.data)
  }

  useEffect(() => { fetchQuote(); fetchSendLogs() }, [qid])

  const handleVersionChange = (vid: string) => {
    fetchVersion(vid)
  }

  const handleNewVersion = async () => {
    await quoteApi.newVersion(qid!)
    message.success('新版本已创建')
    fetchQuote()
  }

  const handleCompare = async () => {
    if (!compareA || !compareB) { message.warning('请选择两个版本'); return }
    if (compareA === compareB) { message.warning('请选择不同的版本'); return }
    setCompareLoading(true)
    try {
      const res = await quoteApi.compareVersions(qid!, compareA, compareB)
      setCompareResult(res.data)
    } finally {
      setCompareLoading(false)
    }
  }

  const handleCreateSnapshot = async () => {
    const values = await snapshotForm.validateFields()
    const breakdown: Record<string, number> = {}
    Object.keys(BREAKDOWN_LABELS).forEach((k) => {
      if (values[`bd_${k}`] != null) breakdown[k] = values[`bd_${k}`]
    })
    await quoteApi.createCostSnapshot(selectedVersionId, {
      note: values.note,
      breakdown_json: Object.keys(breakdown).length > 0 ? breakdown : undefined,
    })
    message.success('成本快照已创建')
    snapshotForm.resetFields()
    setSnapshotCreateModal(false)
    fetchSnapshots()
  }

  const fetchSnapshots = async () => {
    if (!selectedVersionId) return
    const res = await quoteApi.listCostSnapshots(selectedVersionId)
    setSnapshots(res.data)
  }

  const openSnapshotModal = () => {
    fetchSnapshots()
    setSnapshotModal(true)
  }

  const handleSendQuote = async () => {
    const values = await sendForm.validateFields()
    const toList = values.to_contacts
      ? values.to_contacts.split(',').map((c: string) => {
          const parts = c.trim().split('/')
          return { name: parts[0] || '', contact: parts[1] || parts[0] || '' }
        })
      : []
    await quoteApi.sendQuote(selectedVersionId, {
      channel: values.channel,
      to_list_json: toList,
      subject: values.subject,
      body: values.body,
    })
    message.success('发送记录已保存')
    sendForm.resetFields()
    setSendModal(false)
    fetchSendLogs()
  }

  const openApprovalModal = () => {
    setSelectedApprovers([])
    setApprovalModal(true)
  }

  const handleSubmitApproval = async () => {
    setApprovalSubmitting(true)
    try {
      const approverNames = selectedApprovers.map((id) => userSelect.options.find((o) => o.value === id)?.label || '')
      const res = await approvalApi.submit({
        biz_type: 'quote_version',
        biz_id: selectedVersionId,
        title: `报价审批 - ${quote?.quote_no} V${currentVersion?.version_no || ''}`,
        assignee_ids: selectedApprovers,
        assignee_names: approverNames.length > 0 ? approverNames : undefined,
      })
      if (res.data?.approval_mode && res.data.approval_mode !== 'sequential') {
        message.success(`审批已自动发起（${res.data.approval_mode === 'parallel' ? '并行模式' : '任一通过模式'}）`)
      } else {
        message.success('审批已提交')
      }
      setApprovalModal(false)
    } catch (err: any) {
      if (err?.response?.data?.message) {
        message.error(err.response.data.message)
      }
    } finally {
      setApprovalSubmitting(false)
    }
  }

  const handleLineSubmit = async () => {
    const values = await form.validateFields()
    if (editingLine) {
      await quoteApi.updateLine(editingLine.id, values)
      message.success('行项目已更新')
    } else {
      await quoteApi.addLine(selectedVersionId, values)
      message.success('行项目已添加')
    }
    setLineModal(false)
    form.resetFields()
    setEditingLine(null)
    fetchVersion(selectedVersionId)
  }

  const handleAiAnalyze = async () => {
    if (!selectedVersionId) return
    setAiLoading(true)
    try {
      const res = await aiApi.analyze({ biz_type: 'quote_version', biz_id: selectedVersionId, analysis_type: 'quote_review' })
      setAiResult(res.data?.result || null)
    } catch {
      message.error('AI 分析失败')
    } finally {
      setAiLoading(false)
    }
  }

  const lineColumns: ColumnsType<QuoteLine> = [
    { title: '#', dataIndex: 'line_no', width: 50 },
    { title: '类型', dataIndex: 'item_type', width: 80,
      render: (v) => v ? <Tag>{itemTypeLabels[v] || v}</Tag> : '-' },
    { title: '品名', dataIndex: 'item_name', width: 160,
      render: (v) => <span className="font-semibold text-slate-800">{v || '-'}</span> },
    { title: '编码', dataIndex: 'item_code', width: 100 },
    { title: '规格', dataIndex: 'spec', width: 140 },
    { title: '数量', dataIndex: 'qty', width: 80, align: 'right',
      render: (v, r) => v != null ? `${v} ${r.unit || ''}` : '-' },
    { title: '单价', dataIndex: 'unit_price', width: 100, align: 'right',
      render: (v) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
    { title: '行合计', dataIndex: 'line_total', width: 110, align: 'right',
      render: (v) => v != null ? <span className="font-bold">¥{Number(v).toLocaleString()}</span> : '-' },
    { title: '估计成本', dataIndex: 'cost_est', width: 100, align: 'right',
      render: (v) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
    { title: '交期(天)', dataIndex: 'leadtime_days', width: 80 },
    { title: '', key: 'actions', width: 100,
      render: (_, r) => (
        <Space size={4}>
          <a className="text-primary text-xs font-bold" onClick={() => {
            setEditingLine(r); form.setFieldsValue(r); setLineModal(true)
          }}>编辑</a>
          <a className="text-rose-500 text-xs font-bold" onClick={() => {
            Modal.confirm({
              title: '确认删除', content: `确定要删除行项目 #${r.line_no}？`, okType: 'danger',
              onOk: async () => { await quoteApi.deleteLine(r.id); message.success('已删除'); fetchVersion(selectedVersionId) },
            })
          }}>删除</a>
        </Space>
      ),
    },
  ]

  if (!quote) return <DetailSkeleton />

  const statusColors = quoteStatusColors

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-slate-900">{quote.quote_no}</h1>
            <Tag color={statusColors[quote.status]}>{quote.status}</Tag>
          </div>
          <p className="text-sm text-slate-500">
            创建人: {quote.created_by_name || '-'} · {quote.created_at ? new Date(quote.created_at).toLocaleDateString('zh-CN') : ''}
          </p>
        </div>
        <Space wrap>
          {versions.length >= 2 && (
            <Button icon={<SwapOutlined />} onClick={() => {
              setCompareA(versions[versions.length - 2]?.id || '')
              setCompareB(versions[versions.length - 1]?.id || '')
              setCompareResult(null)
              setCompareModal(true)
            }}>版本对比</Button>
          )}
          <Button icon={<FileProtectOutlined />} type="primary" onClick={() => {
            Modal.confirm({
              title: '从报价生成合同', content: `确认从报价「${quote?.quote_no}」生成合同？将自动带入金额和条款。`,
              onOk: async () => {
                const res = await contractApi.fromQuote(qid!)
                message.success('合同已生成')
                navigate(`/opportunities/${projectId}/contracts/${res.data.contract.id}`)
              },
            })
          }}>生成合同</Button>
          <Button icon={<SendOutlined />} onClick={() => { sendForm.resetFields(); setSendModal(true) }}>发送报价</Button>
          <Button icon={<AuditOutlined />} onClick={openApprovalModal}>提交审批</Button>
          <Button icon={<FilePdfOutlined />} onClick={() => {
            const versionParam = currentVersion ? `?version_id=${currentVersion.id}` : ''
            downloadFile(`/api/v1/quotes/${qid}/export/pdf${versionParam}`, `quote_${quote?.quote_no || ''}.pdf`)
          }}>导出PDF</Button>
          <Button icon={<HistoryOutlined />} onClick={openSnapshotModal}>成本快照</Button>
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>打印</Button>
          <Button onClick={() => navigate(`/opportunities/${projectId}`)}>返回商机</Button>
        </Space>
      </div>

      {/* Version Selector + Info Card */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-400">版本</span>
            <Select
              value={selectedVersionId}
              onChange={handleVersionChange}
              style={{ width: 200 }}
              options={versions.map((v) => ({ label: `${v.title || `V${v.version_no}`} (V${v.version_no})`, value: v.id }))}
            />
          </div>
          <Space>
            <Button icon={<CameraOutlined />} onClick={() => { snapshotForm.resetFields(); setSnapshotCreateModal(true) }} size="small">保存快照</Button>
            <Button icon={<CopyOutlined />} onClick={handleNewVersion}>创建新版本</Button>
          </Space>
        </div>

        {currentVersion && (
          <Descriptions size="small" column={4} bordered>
            <Descriptions.Item label="总价">
              <span className="font-bold text-lg">{currentVersion.price_total != null ? `¥${Number(currentVersion.price_total).toLocaleString()}` : '-'}</span>
            </Descriptions.Item>
            <Descriptions.Item label="税率">{currentVersion.tax_rate != null ? `${(Number(currentVersion.tax_rate) * 100).toFixed(1)}%` : '-'}</Descriptions.Item>
            <Descriptions.Item label="税额">{currentVersion.tax_total != null ? `¥${Number(currentVersion.tax_total).toLocaleString()}` : '-'}</Descriptions.Item>
            <Descriptions.Item label="折扣">{currentVersion.discount_total != null ? `¥${Number(currentVersion.discount_total).toLocaleString()}` : '-'}</Descriptions.Item>
            <Descriptions.Item label="毛利率">{currentVersion.margin_rate != null ? `${(Number(currentVersion.margin_rate) * 100).toFixed(1)}%` : '-'}</Descriptions.Item>
            <Descriptions.Item label="交期承诺">{currentVersion.delivery_promise_date || '-'}</Descriptions.Item>
            <Descriptions.Item label="有效天数">{currentVersion.validity_days ?? '-'}</Descriptions.Item>
            <Descriptions.Item label="版本状态"><Tag>{currentVersion.status}</Tag></Descriptions.Item>
          </Descriptions>
        )}
      </div>

      {/* Tabs: Line Items + Send Logs */}
      <Tabs defaultActiveKey="lines" items={[
        {
          key: 'lines',
          label: '行项目',
          children: (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-slate-100">
                <h3 className="text-sm font-bold text-slate-900">行项目</h3>
                <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
                  setEditingLine(null); form.resetFields(); setLineModal(true)
                }}>添加行</Button>
              </div>
              <Table rowKey="id" columns={lineColumns} dataSource={lines} pagination={false} size="small" scroll={{ x: 1200 }} />
              {lines.length > 0 && (
                <div className="border-t border-slate-200 p-4 bg-slate-50 flex justify-end gap-8">
                  <div className="text-right">
                    <div className="text-[10px] text-slate-400 uppercase font-bold">行合计</div>
                    <div className="text-lg font-black text-slate-900">
                      ¥{lines.reduce((sum, l) => sum + (l.line_total || 0), 0).toLocaleString()}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-slate-400 uppercase font-bold">行数</div>
                    <div className="text-lg font-black text-slate-700">{lines.length}</div>
                  </div>
                </div>
              )}
            </div>
          ),
        },
        {
          key: 'send_logs',
          label: `发送记录 (${sendLogs.length})`,
          children: (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-slate-100">
                <h3 className="text-sm font-bold text-slate-900">发送记录</h3>
                <Button type="primary" size="small" icon={<SendOutlined />} onClick={() => { sendForm.resetFields(); setSendModal(true) }}>
                  记录发送
                </Button>
              </div>
              {sendLogs.length === 0 ? (
                <div className="text-center py-12 text-slate-400 text-sm">暂无发送记录</div>
              ) : (
                <Table rowKey="id" dataSource={sendLogs} pagination={false} size="small"
                  columns={[
                    { title: '渠道', dataIndex: 'channel', width: 80,
                      render: (v: string) => <Tag color={v === 'email' ? 'blue' : v === 'wechat' ? 'green' : 'default'}>{CHANNEL_LABELS[v] || v}</Tag> },
                    { title: '收件人', dataIndex: 'to_list_json', width: 200,
                      render: (v: { name: string; contact: string }[]) => v?.map((t, i) => (
                        <Tag key={i} className="mb-1">{t.name}{t.contact ? ` (${t.contact})` : ''}</Tag>
                      )) || '-' },
                    { title: '主题', dataIndex: 'subject', width: 200 },
                    { title: '状态', dataIndex: 'status', width: 80,
                      render: (v: string) => <Tag color={v === 'sent' ? 'success' : v === 'failed' ? 'error' : 'default'}>{v === 'sent' ? '已发送' : v === 'failed' ? '失败' : v}</Tag> },
                    { title: '发送人', dataIndex: 'sent_by_name', width: 100 },
                    { title: '发送时间', dataIndex: 'created_at', width: 160,
                      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
                  ]}
                />
              )}
            </div>
          ),
        },
        {
          key: 'ai_analysis',
          label: <span className="font-semibold flex items-center gap-1"><RobotOutlined /> AI分析</span>,
          children: (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
              <div className="flex items-center justify-between p-4 border-b border-slate-100">
                <h3 className="text-sm font-bold text-slate-900">AI 报价风险分析</h3>
                <Button type="primary" size="small" icon={<RobotOutlined />} onClick={handleAiAnalyze} loading={aiLoading}>
                  {aiResult ? '重新分析' : '开始分析'}
                </Button>
              </div>
              {aiLoading ? (
                <div className="flex items-center justify-center py-16">
                  <Spin tip="AI 正在分析报价..." />
                </div>
              ) : aiResult ? (
                <div className="p-5 space-y-4">
                  {/* Risk Level */}
                  {aiResult.risk_level && (
                    <div className="flex items-center gap-3 mb-2">
                      <span className="text-xs font-bold uppercase text-slate-400">风险等级</span>
                      <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                        aiResult.risk_level === 'H' ? 'bg-red-50 text-red-600 border border-red-200' :
                        aiResult.risk_level === 'M' ? 'bg-amber-50 text-amber-600 border border-amber-200' :
                        'bg-emerald-50 text-emerald-600 border border-emerald-200'
                      }`}>
                        {aiResult.risk_level === 'H' ? '高风险' : aiResult.risk_level === 'M' ? '中风险' : '低风险'}
                      </span>
                    </div>
                  )}

                  {/* Review Items */}
                  {Array.isArray(aiResult.review_items) && (
                    <div>
                      <h4 className="text-xs font-bold uppercase text-slate-400 mb-2">审核项目</h4>
                      <div className="space-y-2">
                        {aiResult.review_items.map((ri, i) => (
                          <div key={i} className={`p-3 rounded-lg border ${
                            ri.status === 'warning' ? 'bg-amber-50 border-amber-200' :
                            ri.status === 'fail' ? 'bg-red-50 border-red-200' :
                            'bg-emerald-50 border-emerald-200'
                          }`}>
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`material-symbols-outlined text-sm ${
                                ri.status === 'warning' ? 'text-amber-500' :
                                ri.status === 'fail' ? 'text-red-500' : 'text-emerald-500'
                              }`}>
                                {ri.status === 'pass' ? 'check_circle' : ri.status === 'warning' ? 'warning' : 'cancel'}
                              </span>
                              <span className="text-sm font-bold text-slate-800">{ri.item}</span>
                              <Tag color={ri.status === 'pass' ? 'success' : ri.status === 'warning' ? 'warning' : 'error'}>
                                {ri.status === 'pass' ? '通过' : ri.status === 'warning' ? '警告' : '不通过'}
                              </Tag>
                            </div>
                            <div className="text-sm text-slate-600 ml-6">{ri.detail}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Overall Comment */}
                  {aiResult.overall_comment && (
                    <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                      <div className="text-xs font-bold uppercase text-blue-400 mb-1">AI 综合评价</div>
                      <div className="text-sm text-blue-800">{String(aiResult.overall_comment)}</div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-16 text-slate-400 text-sm">
                  <RobotOutlined className="text-3xl mb-3 block text-slate-300" />
                  点击"开始分析"让 AI 审核当前报价版本的定价、利润率和条款风险
                </div>
              )}
            </div>
          ),
        },
      ]} />

      {/* Line Modal */}
      <Modal title={editingLine ? '编辑行项目' : '添加行项目'} open={lineModal}
        onOk={handleLineSubmit} onCancel={() => { setLineModal(false); setEditingLine(null); form.resetFields() }}
        width={600}>
        <Form form={form} layout="vertical">
          {!editingLine && (
            <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100 flex items-center justify-between">
              <span className="text-sm text-blue-700">从产品目录快速选择，自动填充编码、价格等信息</span>
              <Button size="small" type="primary" onClick={() => { setProductSearch(''); searchProducts(''); setProductPickerOpen(true) }}>
                从目录选择
              </Button>
            </div>
          )}
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="item_type" label="类型">
              <Select placeholder="请选择类型" allowClear
                options={Object.entries(itemTypeLabels).map(([k, v]) => ({ label: v, value: k }))} />
            </Form.Item>
            <Form.Item name="item_code" label="编码">
              <Input placeholder="品目编码" />
            </Form.Item>
          </div>
          <Form.Item name="item_name" label="品名" rules={[{ required: true, message: '请输入品名' }]}>
            <Input placeholder="请输入品名" />
          </Form.Item>
          <Form.Item name="spec" label="规格">
            <Input placeholder="请输入规格描述" />
          </Form.Item>
          <div className="grid grid-cols-3 gap-4">
            <Form.Item name="qty" label="数量">
              <InputNumber className="w-full" min={0} precision={2} />
            </Form.Item>
            <Form.Item name="unit" label="单位">
              <Input placeholder="台/套/件" />
            </Form.Item>
            <Form.Item name="unit_price" label="单价">
              <InputNumber className="w-full" min={0} precision={2} />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="cost_est" label="估计成本">
              <InputNumber className="w-full" min={0} precision={2} />
            </Form.Item>
            <Form.Item name="leadtime_days" label="交期(天)">
              <InputNumber className="w-full" min={0} />
            </Form.Item>
          </div>
        </Form>
      </Modal>

      {/* Version Comparison Modal */}
      <Modal title="版本对比" open={compareModal} onCancel={() => setCompareModal(false)} footer={null} width={900}>
        <div className="mb-4 flex items-center gap-3">
          <Select value={compareA} onChange={setCompareA} style={{ width: 200 }}
            options={versions.map((v) => ({ label: `${v.title || `V${v.version_no}`}`, value: v.id }))} />
          <span className="text-slate-400 font-bold">VS</span>
          <Select value={compareB} onChange={setCompareB} style={{ width: 200 }}
            options={versions.map((v) => ({ label: `${v.title || `V${v.version_no}`}`, value: v.id }))} />
          <Button type="primary" onClick={handleCompare} loading={compareLoading}>对比</Button>
        </div>

        {compareResult && (
          <div>
            {Object.keys(compareResult.header_changes || {}).length > 0 && (
              <div className="mb-4">
                <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">汇总变更</h4>
                <div className="grid grid-cols-3 gap-2">
                  {Object.entries(compareResult.header_changes).map(([field, change]: [string, any]) => {
                    const fieldLabels: Record<string, string> = {
                      price_total: '总价', tax_rate: '税率', margin_rate: '毛利率',
                      discount_total: '折扣', delivery_promise_date: '交期承诺', validity_days: '有效天数',
                    }
                    const formatVal = (v: any, f: string) => {
                      if (v == null) return '-'
                      if (f === 'tax_rate' || f === 'margin_rate') return `${(Number(v) * 100).toFixed(1)}%`
                      if (f === 'price_total' || f === 'discount_total') return `¥${Number(v).toLocaleString()}`
                      return String(v)
                    }
                    const diff = (f: string) => {
                      if (f === 'price_total' || f === 'discount_total') {
                        const d = (change.b || 0) - (change.a || 0)
                        return d > 0 ? `+¥${d.toLocaleString()}` : d < 0 ? `-¥${Math.abs(d).toLocaleString()}` : ''
                      }
                      if (f === 'margin_rate') {
                        const d = ((change.b || 0) - (change.a || 0)) * 100
                        return d > 0 ? `+${d.toFixed(1)}pp` : d < 0 ? `${d.toFixed(1)}pp` : ''
                      }
                      return ''
                    }
                    return (
                      <div key={field} className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                        <div className="text-[10px] text-slate-400 font-bold uppercase">{fieldLabels[field] || field}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-sm text-slate-500">{formatVal(change.a, field)}</span>
                          <span className="material-symbols-outlined text-slate-300" style={{ fontSize: 14 }}>arrow_forward</span>
                          <span className="text-sm font-bold text-slate-800">{formatVal(change.b, field)}</span>
                        </div>
                        {diff(field) && (
                          <div className={`text-[10px] font-bold mt-0.5 ${diff(field).startsWith('+') || diff(field).startsWith('-') ? (diff(field).startsWith('+') ? 'text-emerald-500' : 'text-rose-500') : 'text-slate-400'}`}>
                            {diff(field)}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            <h4 className="text-xs font-bold text-slate-500 uppercase mb-2">行项目变更</h4>
            <Table rowKey="key" dataSource={compareResult.line_diffs} size="small" pagination={false}
              columns={[
                { title: '品名', dataIndex: 'item_name', width: 160,
                  render: (v: string, r: any) => (
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${
                        r.status === 'added' ? 'bg-emerald-500' :
                        r.status === 'removed' ? 'bg-rose-500' :
                        r.status === 'changed' ? 'bg-amber-500' : 'bg-slate-300'
                      }`} />
                      <span className="font-semibold text-slate-800">{v || '-'}</span>
                    </div>
                  ),
                },
                { title: '状态', dataIndex: 'status', width: 80,
                  render: (v: string) => ({
                    added: <Tag color="success">新增</Tag>,
                    removed: <Tag color="error">删除</Tag>,
                    changed: <Tag color="warning">变更</Tag>,
                    unchanged: <Tag>不变</Tag>,
                  }[v]),
                },
                { title: '数量', key: 'qty', width: 120,
                  render: (_: unknown, r: any) => r.changes?.qty ? (
                    <span className="text-xs">{r.changes.qty.a} → <b>{r.changes.qty.b}</b></span>
                  ) : <span className="text-slate-300">{r.a?.qty || r.b?.qty || '-'}</span>,
                },
                { title: '单价', key: 'unit_price', width: 130,
                  render: (_: unknown, r: any) => r.changes?.unit_price ? (
                    <span className="text-xs">¥{r.changes.unit_price.a} → <b>¥{r.changes.unit_price.b}</b></span>
                  ) : <span className="text-slate-300">{r.a?.unit_price != null ? `¥${r.a.unit_price}` : (r.b?.unit_price != null ? `¥${r.b.unit_price}` : '-')}</span>,
                },
                { title: '行合计', key: 'line_total', width: 130,
                  render: (_: unknown, r: any) => r.changes?.line_total ? (
                    <span className="text-xs">¥{Number(r.changes.line_total.a).toLocaleString()} → <b>¥{Number(r.changes.line_total.b).toLocaleString()}</b></span>
                  ) : <span className="text-slate-300">{r.a?.line_total != null ? `¥${Number(r.a.line_total).toLocaleString()}` : '-'}</span>,
                },
                { title: '成本', key: 'cost_est', width: 130,
                  render: (_: unknown, r: any) => r.changes?.cost_est ? (
                    <span className="text-xs">¥{r.changes.cost_est.a} → <b>¥{r.changes.cost_est.b}</b></span>
                  ) : <span className="text-slate-300">{r.a?.cost_est != null ? `¥${r.a.cost_est}` : '-'}</span>,
                },
              ]}
            />
          </div>
        )}
      </Modal>

      {/* Submit Approval Modal */}
      <Modal title="提交报价审批" open={approvalModal} onOk={handleSubmitApproval}
        onCancel={() => setApprovalModal(false)} confirmLoading={approvalSubmitting} okText="提交审批">
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            将报价 <b>{quote?.quote_no}</b> 当前版本 V{currentVersion?.version_no} 提交审批
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">选择审批人（按顺序）</label>
            <Select mode="multiple" className="w-full" placeholder="请选择审批人" showSearch filterOption={false}
              value={selectedApprovers} onChange={setSelectedApprovers}
              loading={userSelect.loading}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            <div className="text-xs text-slate-400 mt-1">多选时将按选择顺序依次审批</div>
          </div>
        </div>
      </Modal>

      {/* Cost Snapshot List Modal */}
      <Modal title="成本快照记录" open={snapshotModal} onCancel={() => setSnapshotModal(false)} footer={null} width={800}>
        {snapshots.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm">暂无快照，点击"保存快照"创建</div>
        ) : (
          <Timeline className="mt-4">
            {snapshots.map((s) => (
              <Timeline.Item key={s.id} color={s.snapshot_type === 'approval' ? 'green' : 'blue'}>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="text-sm font-bold text-slate-800">
                      总价: ¥{s.price_total != null ? Number(s.price_total).toLocaleString() : '-'} ·
                      成本: ¥{s.cost_total != null ? Number(s.cost_total).toLocaleString() : '-'} ·
                      毛利率: {s.margin_rate != null ? `${(Number(s.margin_rate) * 100).toFixed(1)}%` : '-'}
                    </div>
                    {/* Cost Breakdown */}
                    {s.breakdown_json && Object.keys(s.breakdown_json).length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(s.breakdown_json).map(([k, v]) => (
                          <div key={k} className="bg-slate-50 border border-slate-200 rounded px-2 py-1 text-[11px]">
                            <span className="text-slate-400">{BREAKDOWN_LABELS[k] || k}: </span>
                            <span className="font-bold text-slate-700">¥{Number(v).toLocaleString()}</span>
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="text-[11px] text-slate-400 mt-1">
                      {s.snapshot_type === 'manual' ? '手动' : s.snapshot_type === 'approval' ? '审批' : s.snapshot_type} ·
                      {s.created_by_name || '系统'} · {s.created_at ? new Date(s.created_at).toLocaleString('zh-CN') : ''}
                    </div>
                    {s.note && <div className="text-xs text-slate-500 mt-1">{s.note}</div>}
                  </div>
                  <Tag>{(s.line_snapshot_json as unknown[])?.length || 0} 行</Tag>
                </div>
              </Timeline.Item>
            ))}
          </Timeline>
        )}
      </Modal>

      {/* Create Snapshot Modal with Breakdown */}
      <Modal title="创建成本快照" open={snapshotCreateModal} onOk={handleCreateSnapshot}
        onCancel={() => { setSnapshotCreateModal(false); snapshotForm.resetFields() }} width={600}>
        <Form form={snapshotForm} layout="vertical">
          <Form.Item name="note" label="备注">
            <Input.TextArea placeholder="快照备注说明" rows={2} />
          </Form.Item>
          <div className="mb-2 text-xs font-bold text-slate-500 uppercase">成本分解（可选）</div>
          <div className="grid grid-cols-3 gap-3">
            {Object.entries(BREAKDOWN_LABELS).map(([k, label]) => (
              <Form.Item key={k} name={`bd_${k}`} label={label}>
                <InputNumber className="w-full" min={0} precision={2} placeholder="0.00" />
              </Form.Item>
            ))}
          </div>
        </Form>
      </Modal>

      {/* Product Picker Modal */}
      <Modal title="从产品目录选择" open={productPickerOpen} onCancel={() => setProductPickerOpen(false)} footer={null} width={700}>
        <Input.Search placeholder="搜索产品编码/名称/规格" value={productSearch}
          onChange={(e) => setProductSearch(e.target.value)}
          onSearch={(v) => searchProducts(v)} enterButton allowClear className="mb-3" />
        <Table rowKey="id" dataSource={productResults} loading={productLoading} size="small" pagination={false}
          scroll={{ y: 320 }}
          columns={[
            { title: '编码', dataIndex: 'product_code', width: 100,
              render: (v: string) => <span className="font-mono text-xs">{v}</span> },
            { title: '名称', dataIndex: 'name', width: 160,
              render: (v: string) => <span className="font-semibold">{v}</span> },
            { title: '规格', dataIndex: 'spec', width: 120, ellipsis: true },
            { title: '单价', dataIndex: 'unit_price', width: 100, align: 'right' as const,
              render: (v: number | null) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
            { title: '', key: 'pick', width: 70,
              render: (_: unknown, r: typeof productResults[0]) => (
                <Button size="small" type="link" onClick={() => handlePickProduct(r)}>选择</Button>
              ),
            },
          ]}
        />
      </Modal>

      {/* Send Quote Modal */}
      <Modal title="记录报价发送" open={sendModal} onOk={handleSendQuote}
        onCancel={() => { setSendModal(false); sendForm.resetFields() }} width={550}>
        <Form form={sendForm} layout="vertical" initialValues={{ channel: 'email' }}>
          <Form.Item name="channel" label="发送渠道" rules={[{ required: true }]}>
            <Select options={Object.entries(CHANNEL_LABELS).map(([k, v]) => ({ label: v, value: k }))} />
          </Form.Item>
          <Form.Item name="to_contacts" label="收件人" extra="多个收件人用逗号分隔，格式：姓名/联系方式">
            <Input placeholder="张三/zhangsan@example.com, 李四/lisi@example.com" />
          </Form.Item>
          <Form.Item name="subject" label="主题">
            <Input placeholder={`报价单 - ${quote?.quote_no} V${currentVersion?.version_no || ''}`} />
          </Form.Item>
          <Form.Item name="body" label="正文">
            <Input.TextArea rows={3} placeholder="发送说明" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
