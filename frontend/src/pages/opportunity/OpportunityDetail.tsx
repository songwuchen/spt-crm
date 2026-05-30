import { useState, useEffect } from 'react'
import { Button, Space, Modal, Input, InputNumber, Select, Spin, Tabs, Table, Tag, Timeline, DatePicker, Form, message } from 'antd'
import { EditOutlined, DeleteOutlined, PlusOutlined, RobotOutlined, FilePdfOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { projectApi } from '@/api/project'
import { quoteApi } from '@/api/quote'
import { contractApi } from '@/api/contract'
import { solutionApi } from '@/api/solution'
import { deliveryApi } from '@/api/delivery'
import { paymentApi } from '@/api/payment'
import { changeApi } from '@/api/change'
import { aiApi } from '@/api/ai'
import { customerApi } from '@/api/customer'
import AttachmentPanel from '@/components/AttachmentPanel'
import ChangeHistory from '@/components/ChangeHistory'
import DetailSkeleton from '@/components/DetailSkeleton'
import ActivityTimeline from '@/components/ActivityTimeline'
import MilestoneGantt from '@/components/MilestoneGantt'
import PaymentChart from '@/components/PaymentChart'
import PaymentGantt from '@/components/PaymentGantt'
import { roleApi } from '@/api/user'
import type { OpportunityProject, ProjectStageHistory, QuoteItem, ContractItem, SolutionItem, DeliveryMilestone, ErpOrderLink, PaymentPlanItem, PaymentRecordItem, InvoiceItem, ChangeRequestItem, Customer, AclShareItem, ProjectMember } from '@/api/types'
import { stageLabels, stageColors, riskLabels, riskColors } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import DepartmentSelect from '@/components/DepartmentSelect'
import InternalNotes from '@/components/InternalNotes'

const STAGES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']

const MEMBER_ROLE_OPTIONS = [
  { value: 'presale', label: '售前' },
  { value: 'business', label: '商务' },
  { value: 'delivery', label: '交付' },
  { value: 'finance', label: '财务' },
  { value: 'pm', label: '项目经理' },
]
const MEMBER_ROLE_LABEL: Record<string, string> = Object.fromEntries(MEMBER_ROLE_OPTIONS.map(o => [o.value, o.label]))

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="py-3 border-b border-slate-50 last:border-0">
      <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1">{label}</div>
      <div className="text-sm font-semibold text-slate-700">{value || <span className="text-slate-300">-</span>}</div>
    </div>
  )
}

export default function OpportunityDetail() {
  usePageTitle('商机详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<OpportunityProject | null>(null)
  const [history, setHistory] = useState<ProjectStageHistory[]>([])
  const [quotes, setQuotes] = useState<QuoteItem[]>([])
  const [contracts, setContracts] = useState<ContractItem[]>([])
  const [solutions, setSolutions] = useState<SolutionItem[]>([])
  const [milestones, setMilestones] = useState<DeliveryMilestone[]>([])
  const [invoices, setInvoices] = useState<InvoiceItem[]>([])
  const [plans, setPlans] = useState<PaymentPlanItem[]>([])
  const [records, setRecords] = useState<PaymentRecordItem[]>([])
  const [changeRequests, setChangeRequests] = useState<ChangeRequestItem[]>([])
  const [shares, setShares] = useState<AclShareItem[]>([])
  const [shareModal, setShareModal] = useState(false)
  const [shareForm] = Form.useForm()
  const [shareRoleList, setShareRoleList] = useState<{ id: string; name: string }[]>([])

  const shareUserSelect = useUserSelect()

  // Project members (多部门 / 多人协作)
  const [members, setMembers] = useState<ProjectMember[]>([])
  const [memberModal, setMemberModal] = useState(false)
  const [editingMember, setEditingMember] = useState<ProjectMember | null>(null)
  const [memberForm] = Form.useForm()
  const memberUserSelect = useUserSelect()
  // assignee picker shared across sub-module modals
  const assigneeUserSelect = useUserSelect()

  const [customer, setCustomer] = useState<Customer | null>(null)
  const [advanceModal, setAdvanceModal] = useState(false)
  const [advanceTarget, setAdvanceTarget] = useState('')
  const [advanceNote, setAdvanceNote] = useState('')
  const [advanceDirection, setAdvanceDirection] = useState<'advance' | 'rollback'>('advance')
  const [exportingPdf, setExportingPdf] = useState<'quotes' | 'contracts' | null>(null)
  const [healthScore, setHealthScore] = useState<{ score: number; max_score: number; level: string; dimensions: Record<string, { score: number; max: number; label: string; detail: string }>; risks: string[]; stall_days: number } | null>(null)
  const [orderLinks, setOrderLinks] = useState<ErpOrderLink[]>([])

  // Milestone modal
  const [milestoneModal, setMilestoneModal] = useState(false)
  const [editingMilestone, setEditingMilestone] = useState<DeliveryMilestone | null>(null)
  const [milestoneForm] = Form.useForm()

  // Payment view toggle
  const [paymentView, setPaymentView] = useState<'chart' | 'gantt'>('chart')

  // Payment plan modal
  const [planModal, setPlanModal] = useState(false)
  const [editingPlan, setEditingPlan] = useState<PaymentPlanItem | null>(null)
  const [planForm] = Form.useForm()

  // Invoice modal
  const [invoiceModal, setInvoiceModal] = useState(false)
  const [editingInvoice, setEditingInvoice] = useState<InvoiceItem | null>(null)
  const [invoiceForm] = Form.useForm()

  // Payment record modal
  const [recordModal, setRecordModal] = useState(false)
  const [editingRecord, setEditingRecord] = useState<PaymentRecordItem | null>(null)
  const [recordForm] = Form.useForm()

  // Change request detail modal
  const [changeDetailModal, setChangeDetailModal] = useState(false)
  const [editingChange, setEditingChange] = useState<ChangeRequestItem | null>(null)
  const [changeForm] = Form.useForm()

  // ERP order link modal
  const [erpModal, setErpModal] = useState(false)
  const [erpForm] = Form.useForm()

  // Change create modal
  const [changeCreateModal, setChangeCreateModal] = useState(false)
  const [changeCreateForm] = Form.useForm()

  // AI analysis
  const [aiLoading, setAiLoading] = useState(false)
  // Similar projects
  const [similarProjects, setSimilarProjects] = useState<{ name: string; similarity_score: number; reason: string }[] | null>(null)
  const [similarInsights, setSimilarInsights] = useState('')
  const [similarLoading, setSimilarLoading] = useState(false)

  const fetchAll = async (signal?: AbortSignal) => {
    if (!id) return
    try {
      const pRes = await projectApi.get(id)
      if (signal?.aborted) return
      setProject(pRes.data)
      if (pRes.data.customer_id) {
        customerApi.get(pRes.data.customer_id).then((r) => { if (!signal?.aborted) setCustomer(r.data) }).catch(() => {})
      }
    } catch {
      if (!signal?.aborted) message.error('加载商机数据失败')
      return
    }
    const guard = (fn: (v: any) => void) => (r: any) => { if (!signal?.aborted) fn(r.data) }
    projectApi.stageHistory(id).then(guard(setHistory)).catch(() => {})
    quoteApi.listByProject(id).then(guard(setQuotes)).catch(() => {})
    contractApi.listByProject(id).then(guard(setContracts)).catch(() => {})
    solutionApi.listByProject(id).then(guard(setSolutions)).catch(() => {})
    deliveryApi.listMilestones(id).then(guard(setMilestones)).catch(() => {})
    paymentApi.listInvoices(id).then(guard(setInvoices)).catch(() => {})
    paymentApi.listPlans(id).then(guard(setPlans)).catch(() => {})
    paymentApi.listRecords(id).then(guard(setRecords)).catch(() => {})
    changeApi.listByProject(id).then(guard(setChangeRequests)).catch(() => {})
    deliveryApi.listOrderLinks(id).then(guard(setOrderLinks)).catch(() => {})
    projectApi.health(id).then(guard(setHealthScore)).catch(() => {})
    projectApi.listShares(id).then(guard(setShares)).catch(() => {})
    projectApi.listMembers(id).then(guard(setMembers)).catch(() => {})
  }

  const openMemberModal = (m: ProjectMember | null) => {
    setEditingMember(m)
    memberForm.resetFields()
    if (m) {
      memberForm.setFieldsValue({
        user_id: m.user_id, member_role: m.member_role,
        department_id: m.department_id, permission: m.permission,
      })
      if (m.user_id && m.user_name) memberUserSelect.setInitialOption({ label: m.user_name, value: m.user_id })
    } else {
      memberForm.setFieldsValue({ permission: 'edit' })
    }
    setMemberModal(true)
  }

  const handleMemberSave = async () => {
    const vals = await memberForm.validateFields()
    const userName = memberUserSelect.options.find((o) => o.value === vals.user_id)?.label
    try {
      if (editingMember) {
        await projectApi.updateMember(id!, editingMember.id, {
          member_role: vals.member_role, department_id: vals.department_id, permission: vals.permission,
        })
        message.success('成员已更新')
      } else {
        await projectApi.addMember(id!, { ...vals, user_name: userName })
        message.success('成员已添加')
      }
      setMemberModal(false)
      setEditingMember(null)
      projectApi.listMembers(id!).then((r) => setMembers(r.data))
    } catch (e: any) {
      if (e?.errorFields) return
      message.error('保存失败')
    }
  }

  useEffect(() => {
    const ac = new AbortController()
    fetchAll(ac.signal)
    return () => ac.abort()
  }, [id])

  const handleAiAnalysis = async () => {
    setAiLoading(true)
    try {
      const res = await aiApi.analyze({
        biz_type: 'project',
        biz_id: id!,
        analysis_type: 'risk',
      })
      const result = res.data?.result as Record<string, unknown> | undefined
      Modal.info({
        title: 'AI 风险分析结果',
        width: 600,
        content: (
          <div className="mt-4 space-y-3">
            {result?.overall_assessment ? (
              <div className="p-3 bg-blue-50 rounded-lg text-sm text-slate-700">{String(result.overall_assessment)}</div>
            ) : null}
            {Array.isArray(result?.risks) && (result.risks as Array<Record<string, string>>).map((r, i) => (
              <div key={i} className="flex items-start gap-3 p-3 bg-white border rounded-lg">
                <Tag color={r.severity === 'H' ? 'red' : r.severity === 'M' ? 'orange' : 'green'}>{r.severity}</Tag>
                <div>
                  <div className="font-semibold text-sm">[{r.category}] {r.description}</div>
                  <div className="text-sm text-slate-400 mt-1">缓解措施：{r.mitigation}</div>
                </div>
              </div>
            ))}
          </div>
        ),
      })
    } catch {
      message.error('AI 分析失败')
    } finally {
      setAiLoading(false)
    }
  }

  const handleStageChange = async () => {
    if (!advanceTarget) return
    try {
      if (advanceDirection === 'advance') {
        await projectApi.advance(id!, { to_stage: advanceTarget, note: advanceNote || undefined })
      } else {
        await projectApi.rollback(id!, { to_stage: advanceTarget, note: advanceNote || undefined })
      }
      message.success('阶段已更新')
      setAdvanceModal(false)
      setAdvanceNote('')
      fetchAll()
    } catch (err: unknown) {
      const gateErr = err as Error & { gateData?: { failed_rules?: { name: string; message: string; fix_action?: string }[] } }
      if (gateErr.gateData?.failed_rules) {
        const failedRules = gateErr.gateData.failed_rules
        const fixLabels: Record<string, string> = {
          link_customer: '关联客户',
          edit_project: '编辑项目',
          create_solution: '创建方案',
          approve_solution: '审批方案',
          create_quote: '创建报价',
          create_contract: '创建合同',
          upload_attachment: '上传附件',
        }
        const fixHandlers: Record<string, () => void> = {
          link_customer: () => navigate(`/opportunities/${id}/edit`),
          edit_project: () => navigate(`/opportunities/${id}/edit`),
          create_solution: () => handleCreateSolution(),
          create_quote: () => handleCreateQuote(),
          create_contract: () => handleCreateContract(),
        }
        Modal.warning({
          title: `阶段推进失败 — 缺少 ${failedRules.length} 项必要条件`,
          width: 520,
          content: (
            <div className="space-y-2 mt-2">
              <div className="text-sm text-slate-400 mb-3">
                以下条件未满足，请逐一完成后重试：
              </div>
              {failedRules.map((r: { name: string; message: string; fix_action?: string }, i: number) => (
                <div key={i} className="flex items-start gap-2 p-3 bg-amber-50 rounded-lg border border-amber-100">
                  <span className="material-symbols-outlined text-amber-500 mt-0.5" style={{ fontSize: 18 }}>warning</span>
                  <div className="flex-1">
                    <div className="text-sm font-bold text-slate-800">{r.name}</div>
                    <div className="text-sm text-slate-500 mt-0.5">{r.message}</div>
                    {r.fix_action && fixHandlers[r.fix_action] && (
                      <button
                        className="text-sm text-blue-600 hover:text-blue-800 mt-1 underline cursor-pointer bg-transparent border-0 p-0"
                        onClick={() => { Modal.destroyAll(); fixHandlers[r.fix_action!]() }}
                      >
                        → {fixLabels[r.fix_action] || '去修复'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ),
        })
      } else {
        message.error(gateErr.message || '阶段推进失败')
      }
    }
  }

  const handleCreateQuote = async () => {
    await quoteApi.create(id!, { title: 'V1' })
    message.success('报价已创建')
    quoteApi.listByProject(id!).then((r) => setQuotes(r.data))
  }

  const handleCreateContract = async () => {
    await contractApi.create(id!, { title: 'V1' })
    message.success('合同已创建')
    contractApi.listByProject(id!).then((r) => setContracts(r.data))
  }

  const handleCreateSolution = async () => {
    await solutionApi.create(id!, { title: 'V1' })
    message.success('方案已创建')
    solutionApi.listByProject(id!).then((r) => setSolutions(r.data))
  }

  // Milestone handlers
  const openMilestoneModal = (m?: DeliveryMilestone) => {
    setEditingMilestone(m || null)
    milestoneForm.setFieldsValue(m ? {
      milestone_code: m.milestone_code,
      name: m.name,
      plan_date: m.plan_date ? dayjs(m.plan_date) : null,
      actual_date: m.actual_date ? dayjs(m.actual_date) : null,
      status: m.status,
      note: m.note,
      assignee_id: m.assignee_id,
    } : { milestone_code: '', name: '', status: 'not_start' })
    if (m?.assignee_id && m.assignee_name) assigneeUserSelect.setInitialOption({ label: m.assignee_name, value: m.assignee_id })
    setMilestoneModal(true)
  }
  const handleMilestoneSave = async () => {
    const values = await milestoneForm.validateFields()
    const data = { ...values, plan_date: values.plan_date?.format('YYYY-MM-DD'), actual_date: values.actual_date?.format('YYYY-MM-DD'),
      assignee_name: assigneeUserSelect.options.find((o) => o.value === values.assignee_id)?.label }
    if (editingMilestone) {
      await deliveryApi.updateMilestone(editingMilestone.id, data)
      message.success('里程碑已更新')
    } else {
      await deliveryApi.createMilestone(id!, data)
      message.success('里程碑已创建')
    }
    setMilestoneModal(false)
    milestoneForm.resetFields()
    deliveryApi.listMilestones(id!).then((r) => setMilestones(r.data))
  }

  // Plan handlers
  const openPlanModal = (p?: PaymentPlanItem) => {
    setEditingPlan(p || null)
    planForm.setFieldsValue(p ? { plan_no: p.plan_no, due_date: p.due_date ? dayjs(p.due_date) : null, amount: p.amount, status: p.status, remark: p.remark, assignee_id: p.assignee_id }
      : { plan_no: `PP-${Date.now().toString(36).toUpperCase()}`, status: 'pending' })
    if (p?.assignee_id && p.assignee_name) assigneeUserSelect.setInitialOption({ label: p.assignee_name, value: p.assignee_id })
    setPlanModal(true)
  }
  const handlePlanSave = async () => {
    const values = await planForm.validateFields()
    const data = { ...values, due_date: values.due_date?.format('YYYY-MM-DD'),
      assignee_name: assigneeUserSelect.options.find((o) => o.value === values.assignee_id)?.label }
    if (editingPlan) {
      await paymentApi.updatePlan(editingPlan.id, data)
      message.success('回款计划已更新')
    } else {
      await paymentApi.createPlan(id!, data)
      message.success('回款计划已创建')
    }
    setPlanModal(false)
    planForm.resetFields()
    paymentApi.listPlans(id!).then((r) => setPlans(r.data))
  }

  // Invoice handlers
  const openInvoiceModal = (inv?: InvoiceItem) => {
    setEditingInvoice(inv || null)
    invoiceForm.setFieldsValue(inv ? { invoice_no: inv.invoice_no, amount: inv.amount, invoice_date: inv.invoice_date ? dayjs(inv.invoice_date) : null, status: inv.status, remark: inv.remark }
      : { invoice_no: `INV-${Date.now().toString(36).toUpperCase()}`, status: 'issued' })
    setInvoiceModal(true)
  }
  const handleInvoiceSave = async () => {
    const values = await invoiceForm.validateFields()
    const data = { ...values, invoice_date: values.invoice_date?.format('YYYY-MM-DD') }
    if (editingInvoice) {
      await paymentApi.updateInvoice(editingInvoice.id, data)
      message.success('发票已更新')
    } else {
      await paymentApi.createInvoice(id!, data)
      message.success('发票已创建')
    }
    setInvoiceModal(false)
    invoiceForm.resetFields()
    paymentApi.listInvoices(id!).then((r) => setInvoices(r.data))
  }

  // Record handlers
  const openRecordModal = (rec?: PaymentRecordItem) => {
    setEditingRecord(rec || null)
    recordForm.setFieldsValue(rec ? { received_date: rec.received_date ? dayjs(rec.received_date) : null, amount: rec.amount, channel: rec.channel, reference_no: rec.reference_no, remark: rec.remark }
      : {})
    setRecordModal(true)
  }
  const handleRecordSave = async () => {
    const values = await recordForm.validateFields()
    const data = { ...values, received_date: values.received_date?.format('YYYY-MM-DD') }
    if (editingRecord) {
      // No update endpoint — skip
      message.info('到账记录暂不支持编辑')
    } else {
      await paymentApi.createRecord(id!, data)
      message.success('到账记录已创建')
    }
    setRecordModal(false)
    recordForm.resetFields()
    paymentApi.listRecords(id!).then((r) => setRecords(r.data))
  }

  // Change detail handlers
  const openChangeDetail = async (cr: ChangeRequestItem) => {
    const res = await changeApi.get(cr.id)
    setEditingChange(res.data)
    changeForm.setFieldsValue({
      change_type: res.data.change_type,
      reason: res.data.reason,
      status: res.data.status,
    })
    setChangeDetailModal(true)
  }
  const handleChangeSave = async () => {
    if (!editingChange) return
    const values = await changeForm.validateFields()
    await changeApi.update(editingChange.id, values)
    message.success('变更单已更新')
    setChangeDetailModal(false)
    changeApi.listByProject(id!).then((r) => setChangeRequests(r.data))
  }

  // Change create handler
  const handleChangeCreate = async () => {
    const values = await changeCreateForm.validateFields()
    const data = { ...values, assignee_name: assigneeUserSelect.options.find((o) => o.value === values.assignee_id)?.label }
    await changeApi.create(id!, data)
    message.success('变更单已创建')
    setChangeCreateModal(false)
    changeCreateForm.resetFields()
    changeApi.listByProject(id!).then((r) => setChangeRequests(r.data))
  }

  // ERP link handler
  const handleErpSave = async () => {
    const values = await erpForm.validateFields()
    await deliveryApi.createOrderLink(id!, values)
    message.success('ERP 映射已创建')
    setErpModal(false)
    erpForm.resetFields()
    deliveryApi.listOrderLinks(id!).then((r) => setOrderLinks(r.data))
  }

  if (!project) return <DetailSkeleton />

  const currentIdx = STAGES.indexOf(project.stage_code)

  return (
    <div>
      {/* Header */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-xl bg-indigo-50 border border-indigo-100 shadow-sm flex items-center justify-center text-2xl font-black text-indigo-600">
              {project.name.slice(0, 2)}
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl font-bold text-slate-900">{project.name}</h1>
                <span className={`inline-flex items-center px-2.5 py-1 rounded text-[10px] font-black uppercase border ${stageColors[project.stage_code]}`}>
                  {project.stage_code} {stageLabels[project.stage_code]}
                </span>
                {project.risk_level && (
                  <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold border ${riskColors[project.risk_level]}`}>
                    风险: {riskLabels[project.risk_level]}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-sm text-slate-500">
                <span className="font-mono text-sm text-slate-400">#{project.project_code}</span>
                {customer && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">business</span> {customer.name}
                  </span>
                )}
                {project.owner_name && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">person</span> {project.owner_name}
                  </span>
                )}
              </div>
            </div>
          </div>
          <Space>
            <Button icon={<RobotOutlined />} loading={aiLoading} onClick={handleAiAnalysis}>AI 分析</Button>
            <Button icon={<EditOutlined />} onClick={() => navigate(`/opportunities/${id}/edit`)}>编辑</Button>
            <Button danger icon={<DeleteOutlined />} onClick={() => {
              Modal.confirm({
                title: '确认删除', content: `确定要删除商机「${project.name}」？`, okType: 'danger',
                onOk: async () => { await projectApi.delete(id!); message.success('已删除'); navigate('/opportunities') },
              })
            }}>删除</Button>
          </Space>
        </div>

        {/* Stage Progress Bar */}
        <div className="flex items-center gap-1 mt-4">
          {STAGES.map((s, i) => {
            const isActive = i <= currentIdx
            const isCurrent = s === project.stage_code
            return (
              <div key={s} className="flex-1 flex flex-col items-center gap-1">
                <div className={`w-full h-2 rounded-full transition-all ${isActive ? 'bg-primary' : 'bg-slate-100'} ${isCurrent ? 'ring-2 ring-primary/30' : ''}`} />
                <span className={`text-[10px] font-bold ${isActive ? 'text-primary' : 'text-slate-400'}`}>{s}</span>
              </div>
            )
          })}
        </div>
        <div className="flex gap-2 mt-3">
          {currentIdx < STAGES.length - 1 && (
            <Button size="small" type="primary" onClick={() => {
              setAdvanceDirection('advance')
              setAdvanceTarget(STAGES[currentIdx + 1])
              setAdvanceModal(true)
            }}>
              推进到 {STAGES[currentIdx + 1]}
            </Button>
          )}
          {currentIdx > 0 && (
            <Button size="small" onClick={() => {
              setAdvanceDirection('rollback')
              setAdvanceTarget(STAGES[currentIdx - 1])
              setAdvanceModal(true)
            }}>
              回退到 {STAGES[currentIdx - 1]}
            </Button>
          )}
        </div>
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Profile */}
        <div className="col-span-3">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-0">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">项目画像</h3>
            <InfoField label="预期金额" value={project.amount_expect != null ? `¥${Number(project.amount_expect).toLocaleString()}` : undefined} />
            <InfoField label="成交概率" value={project.probability != null ? `${project.probability}%` : undefined} />
            <InfoField label="预期成交日" value={project.close_date_expect} />
            <InfoField label="风险等级" value={project.risk_level ? riskLabels[project.risk_level] : undefined} />
            <InfoField label="付款方式" value={(project as any).payment_method || undefined} />
            <InfoField label="是否有保函" value={(project as any).has_guarantee == null ? undefined : ((project as any).has_guarantee ? '是' : '否')} />
            <InfoField label="是否有重量要求" value={(project as any).has_weight_requirement == null ? undefined : ((project as any).has_weight_requirement ? '是' : '否')} />
            <InfoField label="是否使用呆滞设备" value={(project as any).uses_idle_equipment == null ? undefined : ((project as any).uses_idle_equipment ? '是' : '否')} />
            <InfoField label="状态" value={project.status} />
            <InfoField label="备注" value={project.remark} />
          </div>

          {/* Health Score */}
          {healthScore && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mt-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">健康度</h3>
              <div className="flex items-center gap-3 mb-4">
                <div className={`w-14 h-14 rounded-full flex items-center justify-center text-xl font-black text-white ${
                  healthScore.level === 'healthy' ? 'bg-emerald-500' :
                  healthScore.level === 'attention' ? 'bg-blue-500' :
                  healthScore.level === 'warning' ? 'bg-amber-500' : 'bg-red-500'
                }`}>
                  {healthScore.score}
                </div>
                <div>
                  <div className={`text-sm font-bold ${
                    healthScore.level === 'healthy' ? 'text-emerald-600' :
                    healthScore.level === 'attention' ? 'text-blue-600' :
                    healthScore.level === 'warning' ? 'text-amber-600' : 'text-red-600'
                  }`}>
                    {{ healthy: '健康', attention: '关注', warning: '预警', critical: '危险' }[healthScore.level as string]}
                  </div>
                  <div className="text-[10px] text-slate-400">满分 {healthScore.max_score}</div>
                </div>
              </div>
              {/* Dimension Bars */}
              {healthScore.dimensions && (
                <div className="space-y-2.5 mb-3">
                  {Object.entries(healthScore.dimensions).map(([key, dim]) => {
                    const pct = dim.max > 0 ? Math.round((dim.score / dim.max) * 100) : 0
                    const barColor = pct >= 80 ? '#10b981' : pct >= 50 ? '#3b82f6' : pct >= 30 ? '#f59e0b' : '#ef4444'
                    return (
                      <div key={key}>
                        <div className="flex items-center justify-between mb-0.5">
                          <span className="text-[11px] font-bold text-slate-600">{dim.label}</span>
                          <span className="text-[10px] text-slate-400">{dim.score}/{dim.max}</span>
                        </div>
                        <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: barColor }} />
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5">{dim.detail}</div>
                      </div>
                    )
                  })}
                </div>
              )}
              {healthScore.risks?.length > 0 && (
                <div className="space-y-1.5 border-t border-slate-100 pt-3">
                  {healthScore.risks.map((r: string, i: number) => (
                    <div key={i} className="flex items-start gap-1.5 text-[11px] text-amber-600">
                      <span className="material-symbols-outlined" style={{ fontSize: 14, marginTop: 1 }}>warning</span>
                      {r}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Similar Projects */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mt-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">相似商机</h3>
              <Button size="small" loading={similarLoading} onClick={async () => {
                setSimilarLoading(true)
                try {
                  const res = await aiApi.findSimilarProjects(id!)
                  setSimilarProjects(res.data.similar_projects || [])
                  setSimilarInsights(res.data.insights || '')
                } catch { message.error('查询失败') }
                finally { setSimilarLoading(false) }
              }}>
                <span className="material-symbols-outlined text-sm mr-1">auto_awesome</span>
                AI 匹配
              </Button>
            </div>
            {similarProjects === null ? (
              <p className="text-sm text-slate-400 text-center py-2">点击"AI 匹配"查找相似商机</p>
            ) : similarProjects.length === 0 ? (
              <p className="text-sm text-slate-400 text-center py-2">暂无匹配结果</p>
            ) : (
              <div className="space-y-2">
                {similarProjects.map((p, i) => (
                  <div key={i} className="bg-slate-50 rounded-lg px-3 py-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-bold text-slate-700">{p.name}</span>
                      <span className="text-[10px] font-extrabold text-primary">{p.similarity_score}%</span>
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">{p.reason}</div>
                  </div>
                ))}
                {similarInsights && (
                  <div className="bg-indigo-50 rounded-lg px-3 py-2 text-[11px] text-indigo-700 border border-indigo-100">
                    <span className="font-bold">洞察: </span>{similarInsights}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Stage History */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mt-4">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">阶段历史</h3>
            {history.length === 0 ? (
              <p className="text-sm text-slate-400">暂无阶段变更</p>
            ) : (
              <Timeline items={history.map((h) => ({
                children: (
                  <div>
                    <div className="text-sm font-bold text-slate-700">
                      {h.from_stage} → {h.to_stage}
                    </div>
                    {h.note && <div className="text-[11px] text-slate-500">{h.note}</div>}
                    <div className="text-[10px] text-slate-400">
                      {h.changed_by_name} · {new Date(h.created_at).toLocaleString('zh-CN')}
                    </div>
                  </div>
                ),
              }))} />
            )}
          </div>
        </div>

        {/* Right: Tabs */}
        <div className="col-span-9">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <Tabs defaultActiveKey="solutions" className="px-6 pt-2" items={[
              {
                key: 'solutions',
                label: <span className="font-semibold">方案 ({solutions.length})</span>,
                children: (
                  <div className="pb-6">
                    <div className="flex justify-end mb-3">
                      <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleCreateSolution}>新建方案</Button>
                    </div>
                    <Table rowKey="id" dataSource={solutions} pagination={false} size="small"
                      columns={[
                        { title: '方案编号', dataIndex: 'solution_no', render: (v: string, r: SolutionItem) => (
                          <a onClick={() => navigate(`/opportunities/${id}/solutions/${r.id}`)} className="font-bold text-primary">{v}</a>
                        )},
                        { title: '版本', dataIndex: 'current_version_no', render: (v: number) => `V${v}` },
                        { title: '状态', dataIndex: 'status', render: (v: string) => {
                          const c: Record<string, string> = { draft: 'default', reviewing: 'processing', approved: 'success', obsolete: 'error' }
                          const l: Record<string, string> = { draft: '草稿', reviewing: '评审中', approved: '已批准', obsolete: '已废弃' }
                          return <Tag color={c[v]}>{l[v] || v}</Tag>
                        }},
                        { title: '创建人', dataIndex: 'created_by_name' },
                        { title: '创建时间', dataIndex: 'created_at', render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                        { title: '', key: 'actions', render: (_: unknown, r: SolutionItem) => (
                          <Space size={4}>
                            <a onClick={() => navigate(`/opportunities/${id}/solutions/${r.id}`)} className="text-primary text-sm font-bold">查看</a>
                            <a className="text-rose-500 text-sm font-bold" onClick={() => {
                              Modal.confirm({
                                title: '确认删除', content: `确定要删除方案「${r.solution_no}」？`, okType: 'danger',
                                onOk: async () => { await solutionApi.delete(r.id); message.success('已删除'); solutionApi.listByProject(id!).then((res) => setSolutions(res.data)) },
                              })
                            }}>删除</a>
                          </Space>
                        )},
                      ]}
                    />
                  </div>
                ),
              },
              {
                key: 'quotes',
                label: <span className="font-semibold">报价 ({quotes.length})</span>,
                children: (
                  <div className="pb-6">
                    <div className="flex justify-end mb-3">
                      {quotes.length > 0 && (
                        <Button size="small" icon={<FilePdfOutlined />} loading={exportingPdf === 'quotes'} onClick={async () => {
                          setExportingPdf('quotes')
                          try {
                            const res = await quoteApi.batchExportPdf(quotes.map(q => q.id)) as any
                            const url = window.URL.createObjectURL(new Blob([res]))
                            const a = document.createElement('a'); a.href = url; a.download = 'quotes_export.zip'; a.click()
                            window.URL.revokeObjectURL(url)
                          } catch { message.error('导出失败') }
                          finally { setExportingPdf(null) }
                        }}>批量导出PDF</Button>
                      )}
                      <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleCreateQuote}>新建报价</Button>
                    </div>
                    <Table rowKey="id" dataSource={quotes} pagination={false} size="small"
                      columns={[
                        { title: '报价编号', dataIndex: 'quote_no', render: (v, r) => (
                          <a onClick={() => navigate(`/opportunities/${id}/quotes/${r.id}`)} className="font-bold text-primary">{v}</a>
                        )},
                        { title: '版本', dataIndex: 'current_version_no', render: (v) => `V${v}` },
                        { title: '状态', dataIndex: 'status', render: (v) => {
                          const c: Record<string, string> = { draft: 'default', sent: 'processing', won: 'success', lost: 'error' }
                          return <Tag color={c[v]}>{v}</Tag>
                        }},
                        { title: '创建人', dataIndex: 'created_by_name' },
                        { title: '创建时间', dataIndex: 'created_at', render: (v) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                        { title: '', key: 'actions', render: (_, r) => (
                          <Space size={4}>
                            <a onClick={() => navigate(`/opportunities/${id}/quotes/${r.id}`)} className="text-primary text-sm font-bold">查看</a>
                            <a className="text-rose-500 text-sm font-bold" onClick={() => {
                              Modal.confirm({
                                title: '确认删除', content: `确定要删除报价「${r.quote_no}」？`, okType: 'danger',
                                onOk: async () => { await quoteApi.delete(r.id); message.success('已删除'); quoteApi.listByProject(id!).then((res) => setQuotes(res.data)) },
                              })
                            }}>删除</a>
                          </Space>
                        )},
                      ]}
                    />
                  </div>
                ),
              },
              {
                key: 'contracts',
                label: <span className="font-semibold">合同 ({contracts.length})</span>,
                children: (
                  <div className="pb-6">
                    <div className="flex justify-end mb-3">
                      {contracts.length > 0 && (
                        <Button size="small" icon={<FilePdfOutlined />} loading={exportingPdf === 'contracts'} onClick={async () => {
                          setExportingPdf('contracts')
                          try {
                            const res = await contractApi.batchExportPdf(contracts.map(c => c.id)) as any
                            const url = window.URL.createObjectURL(new Blob([res]))
                            const a = document.createElement('a'); a.href = url; a.download = 'contracts_export.zip'; a.click()
                            window.URL.revokeObjectURL(url)
                          } catch { message.error('导出失败') }
                          finally { setExportingPdf(null) }
                        }}>批量导出PDF</Button>
                      )}
                      <Button type="primary" size="small" icon={<PlusOutlined />} onClick={handleCreateContract}>新建合同</Button>
                    </div>
                    <Table rowKey="id" dataSource={contracts} pagination={false} size="small"
                      columns={[
                        { title: '合同编号', dataIndex: 'contract_no', render: (v, r) => (
                          <a onClick={() => navigate(`/opportunities/${id}/contracts/${r.id}`)} className="font-bold text-primary">{v}</a>
                        )},
                        { title: '版本', dataIndex: 'current_version_no', render: (v) => `V${v}` },
                        { title: '合同金额', dataIndex: 'amount_total', render: (v) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                        { title: '状态', dataIndex: 'status', render: (v) => {
                          const c: Record<string, string> = { draft: 'default', signed: 'success', terminated: 'error' }
                          return <Tag color={c[v]}>{v}</Tag>
                        }},
                        { title: '签署日期', dataIndex: 'signed_date', render: (v) => v || '-' },
                        { title: '', key: 'actions', render: (_, r) => (
                          <Space size={4}>
                            <a onClick={() => navigate(`/opportunities/${id}/contracts/${r.id}`)} className="text-primary text-sm font-bold">查看</a>
                            <a className="text-rose-500 text-sm font-bold" onClick={() => {
                              Modal.confirm({
                                title: '确认删除', content: `确定要删除合同「${r.contract_no}」？`, okType: 'danger',
                                onOk: async () => { await contractApi.delete(r.id); message.success('已删除'); contractApi.listByProject(id!).then((res) => setContracts(res.data)) },
                              })
                            }}>删除</a>
                          </Space>
                        )},
                      ]}
                    />
                  </div>
                ),
              },
              {
                key: 'delivery',
                label: <span className="font-semibold">交付 ({milestones.length})</span>,
                children: (
                  <div className="pb-6 space-y-6">
                    {/* Progress Overview */}
                    {milestones.length > 0 && (() => {
                      const done = milestones.filter((m) => m.status === 'done' || m.status === 'completed').length
                      const delayed = milestones.filter((m) => m.status === 'delayed').length
                      const doing = milestones.filter((m) => m.status === 'doing' || m.status === 'in_progress').length
                      const pct = Math.round((done / milestones.length) * 100)
                      return (
                        <div className="bg-white rounded-xl border border-slate-200 p-4">
                          <div className="flex items-center justify-between mb-3">
                            <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">交付进度</h4>
                            <span className="text-sm font-extrabold text-slate-700">{pct}%</span>
                          </div>
                          <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden mb-3">
                            <div className="h-full rounded-full transition-all"
                              style={{
                                width: `${pct}%`,
                                background: delayed > 0 ? 'linear-gradient(90deg, #10b981, #ef4444)' : '#10b981',
                              }} />
                          </div>
                          <div className="grid grid-cols-4 gap-3 text-center">
                            <div>
                              <div className="text-xl font-extrabold text-slate-700">{milestones.length}</div>
                              <div className="text-[10px] text-slate-400 font-bold">总里程碑</div>
                            </div>
                            <div>
                              <div className="text-xl font-extrabold text-emerald-600">{done}</div>
                              <div className="text-[10px] text-emerald-500 font-bold">已完成</div>
                            </div>
                            <div>
                              <div className="text-xl font-extrabold text-blue-600">{doing}</div>
                              <div className="text-[10px] text-blue-500 font-bold">进行中</div>
                            </div>
                            <div>
                              <div className="text-xl font-extrabold text-red-600">{delayed}</div>
                              <div className="text-[10px] text-red-500 font-bold">已延迟</div>
                            </div>
                          </div>
                          {delayed > 0 && (
                            <div className="mt-3 flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                              <span className="material-symbols-outlined text-sm">warning</span>
                              {delayed} 个里程碑已延迟，请关注交付风险
                            </div>
                          )}
                        </div>
                      )
                    })()}

                    {/* Gantt Chart */}
                    {milestones.length > 0 && (
                      <div>
                        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">里程碑甘特图</h4>
                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                          <MilestoneGantt milestones={milestones} />
                        </div>
                      </div>
                    )}

                    {/* Milestones */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">交付里程碑</h4>
                        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => openMilestoneModal()}>新建里程碑</Button>
                      </div>
                      <Table rowKey="id" dataSource={milestones} pagination={false} size="small"
                        columns={[
                          { title: '节点', dataIndex: 'milestone_code' },
                          { title: '名称', dataIndex: 'name' },
                          { title: '计划日期', dataIndex: 'plan_date', render: (v: string) => v || '-' },
                          { title: '实际日期', dataIndex: 'actual_date', render: (v: string) => v || '-' },
                          { title: '状态', dataIndex: 'status', render: (v: string) => {
                            const c: Record<string, string> = { not_start: 'default', doing: 'processing', done: 'success', delayed: 'error', pending: 'default', in_progress: 'processing', completed: 'success' }
                            const l: Record<string, string> = { not_start: '未开始', doing: '进行中', done: '已完成', delayed: '已延迟', pending: '待开始', in_progress: '进行中', completed: '已完成' }
                            return <Tag color={c[v]}>{l[v] || v}</Tag>
                          }},
                          { title: '负责人', dataIndex: 'assignee_name', render: (v: string) => v || '-' },
                          { title: '来源', dataIndex: 'source_type' },
                          { title: '', key: 'actions', width: 100, render: (_: unknown, r: DeliveryMilestone) => (
                            <Space size={4}>
                              <a className="text-primary text-sm font-bold" onClick={() => openMilestoneModal(r)}>编辑</a>
                              <a className="text-rose-500 text-sm font-bold" onClick={() => {
                                Modal.confirm({
                                  title: '确认删除', okType: 'danger',
                                  onOk: async () => { await deliveryApi.deleteMilestone(r.id); message.success('已删除'); deliveryApi.listMilestones(id!).then((res) => setMilestones(res.data)) },
                                })
                              }}>删除</a>
                            </Space>
                          )},
                        ]}
                      />
                    </div>

                    {/* ERP Order Links */}
                    <div>
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">ERP 订单映射</h4>
                        <Button size="small" icon={<PlusOutlined />} onClick={() => { erpForm.resetFields(); setErpModal(true) }}>新建映射</Button>
                      </div>
                      <Table rowKey="id" dataSource={orderLinks} pagination={false} size="small"
                        columns={[
                          { title: 'ERP系统', dataIndex: 'erp_system_code', render: (v: string) => v || '-' },
                          { title: '订单号', dataIndex: 'erp_order_no', render: (v: string) => <span className="font-mono font-bold">{v || '-'}</span> },
                          { title: '同步状态', dataIndex: 'sync_status', render: (v: string) => {
                            const c: Record<string, string> = { pending: 'default', synced: 'success', failed: 'error' }
                            const l: Record<string, string> = { pending: '待同步', synced: '已同步', failed: '失败' }
                            return <Tag color={c[v]}>{l[v] || v}</Tag>
                          }},
                          { title: '备注', dataIndex: 'remark', ellipsis: true },
                          { title: '创建时间', dataIndex: 'created_at', render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                          { title: '', key: 'actions', width: 60, render: (_: unknown, r: ErpOrderLink) => (
                            <a className="text-rose-500 text-sm font-bold" onClick={() => {
                              Modal.confirm({
                                title: '确认删除', okType: 'danger',
                                onOk: async () => { await deliveryApi.deleteOrderLink(r.id); message.success('已删除'); deliveryApi.listOrderLinks(id!).then((res) => setOrderLinks(res.data)) },
                              })
                            }}>删除</a>
                          )},
                        ]}
                      />
                    </div>
                  </div>
                ),
              },
              {
                key: 'payment',
                label: <span className="font-semibold">回款 ({plans.length + invoices.length})</span>,
                children: (
                  <div className="pb-6 space-y-6">
                    {/* Payment Overview Chart / Gantt */}
                    {(plans.length > 0 || records.length > 0) && (
                      <div>
                        <div className="flex items-center justify-between mb-3">
                          <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">回款概览</h4>
                          <div className="flex items-center border border-slate-200 rounded-lg overflow-hidden">
                            <button className={`px-3 py-1 text-sm font-bold ${paymentView === 'chart' ? 'bg-slate-800 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
                              onClick={() => setPaymentView('chart')}>图表</button>
                            <button className={`px-3 py-1 text-sm font-bold ${paymentView === 'gantt' ? 'bg-slate-800 text-white' : 'text-slate-500 hover:bg-slate-50'}`}
                              onClick={() => setPaymentView('gantt')}>甘特图</button>
                          </div>
                        </div>
                        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
                          {paymentView === 'chart' ? (
                            <PaymentChart plans={plans} records={records} />
                          ) : (
                            <PaymentGantt plans={plans} records={records} />
                          )}
                        </div>
                      </div>
                    )}

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">回款计划</h4>
                        <Button size="small" icon={<PlusOutlined />} onClick={() => openPlanModal()}>新建计划</Button>
                      </div>
                      <Table rowKey="id" dataSource={plans} pagination={false} size="small"
                        columns={[
                          { title: '计划编号', dataIndex: 'plan_no' },
                          { title: '到期日', dataIndex: 'due_date', render: (v: string) => v || '-' },
                          { title: '金额', dataIndex: 'amount', render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                          { title: '状态', dataIndex: 'status', render: (v: string) => {
                            const c: Record<string, string> = { pending: 'default', paid: 'success', overdue: 'error' }
                            const l: Record<string, string> = { pending: '待回款', paid: '已回款', overdue: '已逾期' }
                            return <Tag color={c[v]}>{l[v] || v}</Tag>
                          }},
                          { title: '负责人', dataIndex: 'assignee_name', render: (v: string) => v || '-' },
                          { title: '', key: 'actions', width: 60, render: (_: unknown, r: PaymentPlanItem) => (
                            <a className="text-primary text-sm font-bold" onClick={() => openPlanModal(r)}>编辑</a>
                          )},
                        ]}
                      />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">发票</h4>
                        <Button size="small" icon={<PlusOutlined />} onClick={() => openInvoiceModal()}>新建发票</Button>
                      </div>
                      <Table rowKey="id" dataSource={invoices} pagination={false} size="small"
                        columns={[
                          { title: '发票号', dataIndex: 'invoice_no' },
                          { title: '金额', dataIndex: 'amount', render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                          { title: '日期', dataIndex: 'invoice_date', render: (v: string) => v || '-' },
                          { title: '状态', dataIndex: 'status', render: (v: string) => {
                            const l: Record<string, string> = { issued: '已开票', void: '已作废' }
                            return <Tag color={v === 'issued' ? 'success' : 'error'}>{l[v] || v}</Tag>
                          }},
                          { title: '', key: 'actions', width: 60, render: (_: unknown, r: InvoiceItem) => (
                            <a className="text-primary text-sm font-bold" onClick={() => openInvoiceModal(r)}>编辑</a>
                          )},
                        ]}
                      />
                    </div>
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">到账记录</h4>
                        <Button size="small" icon={<PlusOutlined />} onClick={() => openRecordModal()}>新建记录</Button>
                      </div>
                      <Table rowKey="id" dataSource={records} pagination={false} size="small"
                        columns={[
                          { title: '到账日期', dataIndex: 'received_date', render: (v: string) => v || '-' },
                          { title: '金额', dataIndex: 'amount', render: (v: number) => v != null ? `¥${Number(v).toLocaleString()}` : '-' },
                          { title: '渠道', dataIndex: 'channel', render: (v: string) => v || '-' },
                          { title: '参考号', dataIndex: 'reference_no', render: (v: string) => v || '-' },
                          { title: '创建人', dataIndex: 'created_by_name' },
                        ]}
                      />
                    </div>
                  </div>
                ),
              },
              {
                key: 'changes',
                label: <span className="font-semibold">变更 ({changeRequests.length})</span>,
                children: (
                  <div className="pb-6">
                    <div className="flex justify-end mb-3">
                      <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
                        changeCreateForm.resetFields()
                        changeCreateForm.setFieldsValue({ change_type: 'requirement' })
                        setChangeCreateModal(true)
                      }}>新建变更单</Button>
                    </div>
                    <Table rowKey="id" dataSource={changeRequests} pagination={false} size="small"
                      columns={[
                        { title: '变更编号', dataIndex: 'change_no', render: (v: string, r: ChangeRequestItem) => (
                          <a className="font-bold text-primary cursor-pointer" onClick={() => openChangeDetail(r)}>{v}</a>
                        )},
                        { title: '类型', dataIndex: 'change_type', render: (v: string) => {
                          const l: Record<string, string> = { requirement: '需求变更', quote: '报价变更', contract: '合同变更', delivery: '交付变更' }
                          return l[v] || v
                        }},
                        { title: '原因', dataIndex: 'reason', ellipsis: true, width: 160, render: (v: string) => v || '-' },
                        { title: '状态', dataIndex: 'status', render: (v: string) => {
                          const c: Record<string, string> = { draft: 'default', reviewing: 'processing', approved: 'success', rejected: 'error', implemented: 'success' }
                          const l: Record<string, string> = { draft: '草稿', reviewing: '评审中', approved: '已通过', rejected: '已驳回', implemented: '已实施' }
                          return <Tag color={c[v]}>{l[v] || v}</Tag>
                        }},
                        { title: '负责人', dataIndex: 'assignee_name', render: (v: string) => v || '-' },
                        { title: '创建人', dataIndex: 'created_by_name' },
                        { title: '创建时间', dataIndex: 'created_at', render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
                        { title: '', key: 'actions', width: 100, render: (_: unknown, r: ChangeRequestItem) => (
                          <Space size={4}>
                            <a className="text-primary text-sm font-bold" onClick={() => openChangeDetail(r)}>查看</a>
                            <a className="text-rose-500 text-sm font-bold" onClick={() => {
                              Modal.confirm({
                                title: '确认删除', content: `确定要删除变更单「${r.change_no}」？`, okType: 'danger',
                                onOk: async () => { await changeApi.delete(r.id); message.success('已删除'); changeApi.listByProject(id!).then((res) => setChangeRequests(res.data)) },
                              })
                            }}>删除</a>
                          </Space>
                        )},
                      ]}
                    />
                  </div>
                ),
              },
              {
                key: 'activities',
                label: <span className="font-semibold">互动记录</span>,
                children: (
                  <div className="py-4">
                    <ActivityTimeline bizType="project" bizId={id!} customerId={project?.customer_id} />
                  </div>
                ),
              },
              {
                key: 'notes',
                label: <span className="font-semibold">内部备忘</span>,
                children: (
                  <div className="py-4">
                    <InternalNotes bizType="project" bizId={id!} />
                  </div>
                ),
              },
              {
                key: 'attachments',
                label: <span className="font-semibold">附件</span>,
                children: (
                  <div className="py-4">
                    <AttachmentPanel bizType="project" bizId={id!} />
                  </div>
                ),
              },
              {
                key: 'members',
                label: <span className="font-semibold">团队成员 <span className="ml-1 text-sm text-slate-400">{members.length}</span></span>,
                children: (
                  <div className="py-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="text-xs text-slate-500">多部门/多人协作：为不同部门成员分配查看或编辑权限</div>
                      <Button size="small" icon={<PlusOutlined />} onClick={() => openMemberModal(null)}>添加成员</Button>
                    </div>
                    <Table size="small" rowKey="id" dataSource={members} pagination={false} columns={[
                      { title: '成员', dataIndex: 'user_name', width: 130, render: (v: string) => <span className="font-bold text-sm">{v || '-'}</span> },
                      { title: '角色', dataIndex: 'member_role', width: 90, render: (v: string) => v ? <Tag>{MEMBER_ROLE_LABEL[v] || v}</Tag> : '-' },
                      { title: '部门', dataIndex: 'department_name', width: 120, render: (v: string) => v || '-' },
                      { title: '权限', dataIndex: 'permission', width: 80, render: (v: string) => <Tag color={v === 'edit' ? 'blue' : undefined}>{v === 'edit' ? '编辑' : '查看'}</Tag> },
                      { title: '添加人', dataIndex: 'added_by_name', width: 100, render: (v: string) => v || '-' },
                      { title: '', key: 'actions', width: 110, render: (_: unknown, record: ProjectMember) => (
                        <Space size={0}>
                          <a className="text-sm text-primary px-1" onClick={() => openMemberModal(record)}>编辑</a>
                          <a className="text-sm text-rose-500 px-1" onClick={async () => {
                            await projectApi.removeMember(id!, record.id)
                            message.success('已移除')
                            projectApi.listMembers(id!).then((r) => setMembers(r.data))
                          }}>移除</a>
                        </Space>
                      ) },
                    ]} />
                  </div>
                ),
              },
              {
                key: 'shares',
                label: <span className="font-semibold">共享 <span className="ml-1 text-sm text-slate-400">{shares.length}</span></span>,
                children: (
                  <div className="py-4">
                    <div className="flex justify-end mb-3">
                      <Button size="small" icon={<PlusOutlined />} onClick={() => {
                        shareForm.resetFields()
                        shareForm.setFieldsValue({ shared_to_type: 'user', permission: 'view' })
                        setShareModal(true)
                        if (!shareRoleList.length) {
                          roleApi.list().then((r) =>
                            setShareRoleList((r.data || []).map((role) => ({ id: role.id, name: role.name })))
                          ).catch(() => {})
                        }
                      }}>共享给</Button>
                    </div>
                    <Table size="small" rowKey="id" dataSource={shares} pagination={false} columns={[
                      { title: '共享对象', dataIndex: 'shared_to_name', width: 150, render: (v: string) => <span className="font-bold text-sm">{v}</span> },
                      { title: '类型', dataIndex: 'shared_to_type', width: 80, render: (v: string) => v === 'user' ? '用户' : v === 'role' ? '角色' : v },
                      { title: '权限', dataIndex: 'permission', width: 80, render: (v: string) => <Tag color={v === 'edit' ? 'blue' : undefined}>{v === 'edit' ? '编辑' : '查看'}</Tag> },
                      { title: '共享人', dataIndex: 'shared_by_name', width: 100 },
                      { title: '', key: 'actions', width: 60, render: (_: unknown, record: AclShareItem) => (
                        <a className="text-sm text-rose-500" onClick={async () => {
                          await projectApi.deleteShare(id!, record.id)
                          message.success('已取消共享')
                          projectApi.listShares(id!).then((r) => setShares(r.data))
                        }}>删除</a>
                      ) },
                    ]} />
                  </div>
                ),
              },
              {
                key: 'history',
                label: <span className="font-semibold">变更历史</span>,
                children: (
                  <div className="py-4">
                    <ChangeHistory resourceType="project" resourceId={id!} />
                  </div>
                ),
              },
            ]} />
          </div>
        </div>
      </div>

      {/* Advance/Rollback Modal */}
      <Modal title={advanceDirection === 'advance' ? '推进阶段' : '回退阶段'} open={advanceModal}
        onOk={handleStageChange} onCancel={() => { setAdvanceModal(false); setAdvanceNote('') }}>
        <div className="mb-3">
          <div className="text-sm text-slate-600 mb-2">
            {advanceDirection === 'advance' ? '推进' : '回退'}到阶段:
            <span className="font-bold text-primary ml-1">{advanceTarget} {stageLabels[advanceTarget]}</span>
          </div>
          <Input.TextArea rows={3} placeholder="变更说明（选填）" value={advanceNote} onChange={(e) => setAdvanceNote(e.target.value)} />
        </div>
      </Modal>

      {/* Milestone Modal */}
      <Modal title={editingMilestone ? '编辑里程碑' : '新建里程碑'} open={milestoneModal}
        onOk={handleMilestoneSave} onCancel={() => { setMilestoneModal(false); milestoneForm.resetFields() }} width={500}>
        <Form form={milestoneForm} layout="vertical">
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="milestone_code" label="节点编码" rules={[{ required: true, message: '请输入' }]}>
              <Input placeholder="如 design, delivery, acceptance" />
            </Form.Item>
            <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入' }]}>
              <Input placeholder="里程碑名称" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="plan_date" label="计划日期">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="actual_date" label="实际日期">
              <DatePicker className="w-full" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="status" label="状态">
              <Select options={[
                { value: 'not_start', label: '未开始' }, { value: 'doing', label: '进行中' },
                { value: 'done', label: '已完成' }, { value: 'delayed', label: '已延迟' },
              ]} />
            </Form.Item>
            <Form.Item name="note" label="备注">
              <Input placeholder="备注" />
            </Form.Item>
          </div>
          <Form.Item name="assignee_id" label="负责人">
            <Select showSearch filterOption={false} allowClear placeholder="搜索用户"
              options={assigneeUserSelect.options} loading={assigneeUserSelect.loading}
              onSearch={assigneeUserSelect.onSearch} onDropdownVisibleChange={assigneeUserSelect.onDropdownVisibleChange} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Payment Plan Modal */}
      <Modal title={editingPlan ? '编辑回款计划' : '新建回款计划'} open={planModal}
        onOk={handlePlanSave} onCancel={() => { setPlanModal(false); planForm.resetFields() }}>
        <Form form={planForm} layout="vertical">
          <Form.Item name="plan_no" label="计划编号" rules={[{ required: true }]}>
            <Input disabled={!!editingPlan} />
          </Form.Item>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="due_date" label="到期日">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="amount" label="金额">
              <InputNumber className="w-full" min={0} precision={2} prefix="¥" />
            </Form.Item>
          </div>
          <Form.Item name="status" label="状态">
            <Select options={[
              { value: 'pending', label: '待回款' }, { value: 'paid', label: '已回款' }, { value: 'overdue', label: '已逾期' },
            ]} />
          </Form.Item>
          <Form.Item name="assignee_id" label="负责人">
            <Select showSearch filterOption={false} allowClear placeholder="搜索用户"
              options={assigneeUserSelect.options} loading={assigneeUserSelect.loading}
              onSearch={assigneeUserSelect.onSearch} onDropdownVisibleChange={assigneeUserSelect.onDropdownVisibleChange} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Invoice Modal */}
      <Modal title={editingInvoice ? '编辑发票' : '新建发票'} open={invoiceModal}
        onOk={handleInvoiceSave} onCancel={() => { setInvoiceModal(false); invoiceForm.resetFields() }}>
        <Form form={invoiceForm} layout="vertical">
          <Form.Item name="invoice_no" label="发票号" rules={[{ required: true }]}>
            <Input disabled={!!editingInvoice} />
          </Form.Item>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="invoice_date" label="开票日期">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="amount" label="金额">
              <InputNumber className="w-full" min={0} precision={2} prefix="¥" />
            </Form.Item>
          </div>
          <Form.Item name="status" label="状态">
            <Select options={[{ value: 'issued', label: '已开票' }, { value: 'void', label: '已作废' }]} />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Payment Record Modal */}
      <Modal title="新建到账记录" open={recordModal}
        onOk={handleRecordSave} onCancel={() => { setRecordModal(false); recordForm.resetFields() }}>
        <Form form={recordForm} layout="vertical">
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="received_date" label="到账日期" rules={[{ required: true, message: '请选择' }]}>
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="amount" label="金额" rules={[{ required: true, message: '请输入' }]}>
              <InputNumber className="w-full" min={0} precision={2} prefix="¥" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="channel" label="渠道">
              <Select allowClear options={[
                { value: 'bank', label: '银行转账' }, { value: 'check', label: '支票' },
                { value: 'cash', label: '现金' }, { value: 'other', label: '其他' },
              ]} />
            </Form.Item>
            <Form.Item name="reference_no" label="参考号">
              <Input placeholder="银行流水号等" />
            </Form.Item>
          </div>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Change Request Detail Modal */}
      <Modal title="变更单详情" open={changeDetailModal}
        onOk={handleChangeSave} onCancel={() => { setChangeDetailModal(false); setEditingChange(null) }}
        okText="保存" width={600}>
        {editingChange && (
          <div>
            <div className="mb-4 p-3 bg-slate-50 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="font-mono font-bold text-primary">{editingChange.change_no}</span>
                <span className="text-sm text-slate-400">
                  {editingChange.created_by_name} · {editingChange.created_at ? new Date(editingChange.created_at).toLocaleString('zh-CN') : ''}
                </span>
              </div>
            </div>
            <Form form={changeForm} layout="vertical">
              <div className="grid grid-cols-2 gap-4">
                <Form.Item name="change_type" label="变更类型">
                  <Select options={[
                    { value: 'requirement', label: '需求变更' }, { value: 'quote', label: '报价变更' },
                    { value: 'contract', label: '合同变更' }, { value: 'delivery', label: '交付变更' },
                  ]} />
                </Form.Item>
                <Form.Item name="status" label="状态">
                  <Select options={[
                    { value: 'draft', label: '草稿' }, { value: 'reviewing', label: '评审中' },
                    { value: 'approved', label: '已通过' }, { value: 'rejected', label: '已驳回' },
                    { value: 'implemented', label: '已实施' },
                  ]} />
                </Form.Item>
              </div>
              <Form.Item name="reason" label="变更原因">
                <Input.TextArea rows={3} placeholder="描述变更原因..." />
              </Form.Item>
            </Form>
            <div className="mt-2">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">影响评估</h4>
                <Button size="small" type="primary" onClick={async () => {
                  try {
                    const res = await changeApi.estimateImpact(editingChange.id)
                    setEditingChange({ ...editingChange, impact_json: res.data })
                    message.success('影响评估已完成')
                    changeApi.listByProject(id!).then((r) => setChangeRequests(r.data))
                  } catch { message.error('评估失败') }
                }}>自动评估影响</Button>
              </div>
              {editingChange.impact_json ? (
                <div className="space-y-3">
                  {/* Summary cards */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-blue-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-extrabold text-blue-600">{(editingChange.impact_json as Record<string, unknown>).affected_milestone_count as number ?? '-'}</div>
                      <div className="text-[10px] text-blue-500 font-bold uppercase">受影响里程碑</div>
                    </div>
                    <div className="bg-slate-50 rounded-lg p-3 text-center">
                      <div className="text-2xl font-extrabold text-slate-600">{(editingChange.impact_json as Record<string, unknown>).total_milestone_count as number ?? '-'}</div>
                      <div className="text-[10px] text-slate-500 font-bold uppercase">总里程碑数</div>
                    </div>
                    <div className="bg-amber-50 rounded-lg p-3 text-center">
                      <div className="text-lg font-extrabold text-amber-600">
                        {((editingChange.impact_json as Record<string, unknown>).risk_summary as string[])?.length ?? 0}
                      </div>
                      <div className="text-[10px] text-amber-500 font-bold uppercase">风险提示</div>
                    </div>
                  </div>
                  {/* Risk warnings */}
                  {((editingChange.impact_json as Record<string, unknown>).risk_summary as string[])?.length > 0 && (
                    <div className="space-y-1">
                      {((editingChange.impact_json as Record<string, unknown>).risk_summary as string[]).map((r: string, i: number) => (
                        <div key={i} className="flex items-start gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                          <span className="material-symbols-outlined text-sm mt-px">warning</span>
                          {r}
                        </div>
                      ))}
                    </div>
                  )}
                  {/* Affected milestones list */}
                  {((editingChange.impact_json as Record<string, unknown>).affected_milestones as Array<Record<string, string>>)?.length > 0 && (
                    <div>
                      <div className="text-[10px] font-bold uppercase text-slate-400 mb-1">受影响里程碑</div>
                      <div className="space-y-1">
                        {((editingChange.impact_json as Record<string, unknown>).affected_milestones as Array<Record<string, string>>).map((m) => (
                          <div key={m.id} className="flex items-center justify-between text-sm bg-slate-50 rounded px-3 py-1.5">
                            <span className="font-semibold text-slate-700">{m.name || m.code}</span>
                            <span className="text-slate-400">{m.plan_date || '未设定日期'}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center py-6 text-sm text-slate-400">
                  点击"自动评估影响"按钮生成影响分析
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Change Create Modal */}
      <Modal title="新建变更单" open={changeCreateModal}
        onOk={handleChangeCreate} onCancel={() => { setChangeCreateModal(false); changeCreateForm.resetFields() }}>
        <Form form={changeCreateForm} layout="vertical">
          <Form.Item name="change_type" label="变更类型" rules={[{ required: true }]}>
            <Select options={[
              { value: 'requirement', label: '需求变更' }, { value: 'quote', label: '报价变更' },
              { value: 'contract', label: '合同变更' }, { value: 'delivery', label: '交付变更' },
            ]} />
          </Form.Item>
          <Form.Item name="reason" label="变更原因">
            <Input.TextArea rows={3} placeholder="描述变更原因..." />
          </Form.Item>
          <Form.Item name="assignee_id" label="负责人">
            <Select showSearch filterOption={false} allowClear placeholder="搜索用户"
              options={assigneeUserSelect.options} loading={assigneeUserSelect.loading}
              onSearch={assigneeUserSelect.onSearch} onDropdownVisibleChange={assigneeUserSelect.onDropdownVisibleChange} />
          </Form.Item>
        </Form>
      </Modal>

      {/* ERP Order Link Modal */}
      <Modal title="新建 ERP 订单映射" open={erpModal}
        onOk={handleErpSave} onCancel={() => { setErpModal(false); erpForm.resetFields() }}>
        <Form form={erpForm} layout="vertical">
          <Form.Item name="erp_system_code" label="ERP系统编码" rules={[{ required: true, message: '请输入' }]}>
            <Input placeholder="如 SAP, Oracle, 金蝶" />
          </Form.Item>
          <Form.Item name="erp_order_no" label="ERP订单号" rules={[{ required: true, message: '请输入' }]}>
            <Input placeholder="ERP 系统中的订单号" />
          </Form.Item>
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={2} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Member Modal */}
      <Modal title={editingMember ? '编辑成员' : '添加团队成员'} open={memberModal}
        onOk={handleMemberSave} onCancel={() => { setMemberModal(false); setEditingMember(null) }} width={480}>
        <Form form={memberForm} layout="vertical">
          <Form.Item name="user_id" label="成员" rules={[{ required: true, message: '请选择成员' }]}>
            <Select
              showSearch filterOption={false} placeholder="搜索用户"
              options={memberUserSelect.options} loading={memberUserSelect.loading}
              onSearch={memberUserSelect.onSearch} onDropdownVisibleChange={memberUserSelect.onDropdownVisibleChange}
              disabled={!!editingMember}
            />
          </Form.Item>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="member_role" label="角色">
              <Select allowClear options={MEMBER_ROLE_OPTIONS} placeholder="选择角色" />
            </Form.Item>
            <Form.Item name="permission" label="权限">
              <Select options={[{ value: 'view', label: '查看' }, { value: 'edit', label: '编辑' }]} />
            </Form.Item>
          </div>
          <Form.Item name="department_id" label="部门">
            <DepartmentSelect placeholder="选择部门（选填）" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Share Modal */}
      <Modal title="共享项目" open={shareModal}
        onOk={async () => {
          const vals = await shareForm.validateFields()
          const sharedToType = vals.shared_to_type
          let sharedToName = ''
          if (sharedToType === 'user') {
            sharedToName = shareUserSelect.options.find((o) => o.value === vals.shared_to_id)?.label || ''
          } else {
            sharedToName = shareRoleList.find((r) => r.id === vals.shared_to_id)?.name || ''
          }
          await projectApi.createShare(id!, { ...vals, shared_to_name: sharedToName })
          message.success('共享成功')
          setShareModal(false)
          projectApi.listShares(id!).then((r) => setShares(r.data))
        }}
        onCancel={() => setShareModal(false)}>
        <Form form={shareForm} layout="vertical" initialValues={{ shared_to_type: 'user', permission: 'view' }}>
          <Form.Item name="shared_to_type" label="共享类型">
            <Select options={[{ value: 'user', label: '用户' }, { value: 'role', label: '角色' }]}
              onChange={() => shareForm.setFieldValue('shared_to_id', undefined)} />
          </Form.Item>
          <Form.Item noStyle shouldUpdate={(prev, cur) => prev.shared_to_type !== cur.shared_to_type}>
            {({ getFieldValue }) => (
              <Form.Item name="shared_to_id" label="共享对象" rules={[{ required: true, message: '请选择' }]}>
                {getFieldValue('shared_to_type') === 'user' ? (
                  <Select showSearch filterOption={false} placeholder="选择用户"
                    loading={shareUserSelect.loading}
                    options={shareUserSelect.options}
                    onSearch={shareUserSelect.onSearch}
                    onDropdownVisibleChange={shareUserSelect.onDropdownVisibleChange} />
                ) : (
                  <Select showSearch optionFilterProp="label" placeholder="选择角色"
                    options={shareRoleList.map((r) => ({ value: r.id, label: r.name }))} />
                )}
              </Form.Item>
            )}
          </Form.Item>
          <Form.Item name="permission" label="权限级别">
            <Select options={[{ value: 'view', label: '查看' }, { value: 'edit', label: '编辑' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
