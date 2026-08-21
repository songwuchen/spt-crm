import { useState, useEffect } from 'react'
import { Button, Select, Tag, Space, Spin, Descriptions, Modal, DatePicker, InputNumber, Input, Table, Alert, Checkbox, Tabs, Steps, Form, message } from 'antd'
import { CopyOutlined, CheckCircleOutlined, AuditOutlined, RobotOutlined, PrinterOutlined, FilePdfOutlined, EditOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useParams, useNavigate } from 'react-router-dom'
import { contractApi } from '@/api/contract'
import { paymentApi } from '@/api/payment'
import { deliveryApi } from '@/api/delivery'
import { approvalApi } from '@/api/approval'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { aiApi } from '@/api/ai'
import AttachmentPanel from '@/components/AttachmentPanel'
import ContractAttachmentSlots from '@/components/ContractAttachmentSlots'
import AiAnalysisButton from '@/components/ai/AiAnalysisButton'
import SignaturePad from '@/components/SignaturePad'
import DataView, { formatMoney } from '@/components/DataView'
import {
  PaymentTermsView, ClauseTermsView, PaymentTermsEditor, LineItemsEditor,
  toCanonicalRows, sumLineAmounts, resolveLineColumns, resolvePayColumns,
  ContractSubtableTitle,
} from '@/components/ContractTerms'
import { LINE_ITEMS_FIELD_ID, PAYMENT_TERMS_FIELD_ID } from '@/constants/contractDetailTables'
import ContractRegistrationFields, { DATE_KEYS } from '@/components/ContractRegistrationFields'
import type { ContractItem, ContractVersion } from '@/api/types'
import { riskLabels, riskColors } from '@/api/types'
import { contractDisplayStatusColors, contractDisplayStatusLabels, resolveContractDisplayStatus, isContractDraftDeletable, contractVersionStatusColors, contractVersionStatusLabels } from '@/constants/labels'
import type { WfInstanceDetail } from '@/types/lowcode'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import { CONTRACT_REGISTRATION_SECTIONS, formatChangeType, formatRegFieldValue } from '@/constants/contractRegistration'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition } from '@/types/lowcode'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'
import DetailSkeleton from '@/components/DetailSkeleton'
import RecordPrevNextNav from '@/components/RecordPrevNextNav'
import { useSiblingRecordNav } from '@/hooks/useSiblingRecordNav'
import { useUserSelect, useCustomerSelect } from '@/hooks/useSelectOptions'
import { customerApi } from '@/api/customer'
import dayjs from 'dayjs'
import { formatFormDate, isValidFormDate } from '@/utils/formDate'

async function loadContractDetailColumns(): Promise<{
  lineCols: FieldDefinition[]
  payCols: FieldDefinition[]
}> {
  try {
    const r = await lowcodeApi.entityFormSchema('contract')
    const native = r.data.native_fields || []
    return {
      lineCols: resolveLineColumns(native),
      payCols: resolvePayColumns(native),
    }
  } catch {
    return { lineCols: resolveLineColumns(), payCols: resolvePayColumns() }
  }
}

import Icon from '@/components/Icon'
export default function ContractDetail() {
  usePageTitle('合同详情')
  const { id: projectIdParam, cid } = useParams<{ id?: string; cid: string }>()
  const navigate = useNavigate()
  const { hasPermission } = usePermission()
  const canDeleteContract = hasPermission('contract:delete')
  const siblingNav = useSiblingRecordNav('contracts', cid, {
    pathForId: (rid) => `/contracts/${rid}`,
    fetchPage: async (pageNo, snap) => {
      const q = snap.listQuery || {}
      const r = await contractApi.list({
        pageNo,
        pageSize: snap.pageSize,
        keyword: q.keyword as string | undefined,
        status: q.status as string | undefined,
      }) as { data?: { items?: ContractItem[]; total?: number } }
      return {
        ids: (r.data?.items || []).map((x) => x.id),
        total: r.data?.total || 0,
      }
    },
  })
  const [contract, setContract] = useState<ContractItem | null>(null)
  const [versions, setVersions] = useState<ContractVersion[]>([])
  const [currentVersion, setCurrentVersion] = useState<ContractVersion | null>(null)
  const [selectedVersionId, setSelectedVersionId] = useState<string>('')
  const [signModal, setSignModal] = useState(false)
  const [signDate, setSignDate] = useState<dayjs.Dayjs | null>(dayjs())
  const [signatureImage, setSignatureImage] = useState<string | null>(null)
  const [showSignPad, setShowSignPad] = useState(false)

  const [renewLoading, setRenewLoading] = useState(false)
  const projectId = projectIdParam || contract?.project_id || undefined

  // 条款 / 登记编辑
  const [editModal, setEditModal] = useState(false)
  const [editForm] = Form.useForm()
  const [editPay, setEditPay] = useState<Record<string, unknown>[]>([])
  const [editLines, setEditLines] = useState<Record<string, unknown>[]>([])
  const [editSaving, setEditSaving] = useState(false)

  // 详情页内联编辑明细 / 收款计划
  const [detailLines, setDetailLines] = useState<Record<string, unknown>[]>([{}])
  const [detailPay, setDetailPay] = useState<Record<string, unknown>[]>([{}])
  const [linesSaving, setLinesSaving] = useState(false)
  const [paySaving, setPaySaving] = useState(false)

  // 联动数据
  const [related, setRelated] = useState<{
    payment_plans: Array<Record<string, unknown>>
    payment_records: Array<Record<string, unknown>>
    invoices: Array<Record<string, unknown>>
    invoice_applications: Array<Record<string, unknown>>
    milestones: Array<Record<string, unknown>>
  } | null>(null)

  const openEditModal = async () => {
    const reg = { ...(contract?.registration_json || {}) } as Record<string, unknown>
    // 多选字段历史可能是字符串，规整为数组供 Checkbox.Group
    for (const k of ['missing_items', 'payment_forms', 'smart_points']) {
      const v = reg[k]
      if (typeof v === 'string' && v) reg[k] = v.split(/[,，、]/).map((s) => s.trim()).filter(Boolean)
    }
    // DatePicker 需要 dayjs
    const nativeDates: Record<string, unknown> = {}
    for (const k of ['end_date', 'delivery_date', 'order_date', 'card_date'] as const) {
      const v = contract?.[k]
      nativeDates[k] = v ? dayjs(v) : null
    }
    for (const k of Object.keys(reg)) {
      if (DATE_KEYS.has(k) && typeof reg[k] === 'string' && reg[k]) {
        reg[k] = dayjs(reg[k] as string)
      }
    }
    // 合同状态兼容简道云「新增/变动」文案
    let changeType = contract?.change_type || undefined
    if (changeType === '新增') changeType = 'new'
    if (changeType === '变动') changeType = 'change'
    delete reg.number_lookup
    // 无历史编号属性时从图纸号前缀推断，便于编辑回显
    if (!reg.number_attr && contract?.drawing_no) {
      const dn = String(contract.drawing_no).trim().toUpperCase()
      if (dn.startsWith('SY')) reg.number_attr = 'SY'
      else if (dn.startsWith('WMGF')) reg.number_attr = 'WMGF'
    }
    editForm.setFieldsValue({
      amount_total: typeof contract?.amount_total === 'number' ? contract.amount_total : undefined,
      contract_no: contract?.contract_no || undefined,
      drawing_no: contract?.drawing_no || undefined,
      peer_contract_no: contract?.peer_contract_no || undefined,
      acquire_method: contract?.acquire_method || undefined,
      change_type: changeType,
      customer_id: contract?.customer_id || undefined,
      assignee_id: contract?.assignee_id || undefined,
      assignee_name: contract?.assignee_name || undefined,
      department_id: contract?.department_id || undefined,
      department_name: contract?.department_name || undefined,
      ...nativeDates,
      registration_json: reg,
    })
    if (contract?.customer_id) {
      const cidCust = contract.customer_id
      if (contract.customer_name) {
        customerSelect.setInitialOption({ label: contract.customer_name, value: cidCust })
      } else {
        customerApi.get(cidCust).then((r) => {
          if (r.data?.name) customerSelect.setInitialOption({ label: r.data.name, value: cidCust })
        }).catch(() => {})
      }
    }
    const { lineCols, payCols } = await loadContractDetailColumns()
    const pays = toCanonicalRows(contract?.payment_terms_json, payCols)
    setEditPay(pays.length ? pays : [{}])
    const lines = toCanonicalRows(currentVersion?.key_clauses_json, lineCols)
    setEditLines(lines.length ? lines : [{}])
    setEditModal(true)
  }

  const handleEditSave = async (andSubmit: boolean) => {
    setEditSaving(true)
    try {
      let v: Record<string, unknown>
      if (andSubmit) {
        try {
          v = await editForm.validateFields()
        } catch (err: unknown) {
          const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
          const first = fields[0]?.errors?.[0]
          message.warning(first || '请完善必填项后再保存')
          const name = fields[0]?.name
          if (name?.length) {
            editForm.scrollToField(name, { behavior: 'smooth', block: 'center' })
          }
          return
        }
      } else {
        const stale = editForm.getFieldsError().filter((f) => f.errors?.length)
        if (stale.length) {
          editForm.setFields(stale.map((f) => ({ name: f.name, errors: [] })))
        }
        v = editForm.getFieldsValue(true) as Record<string, unknown>
      }
      const nativeDates: { name: string; label: string; value: unknown }[] = [
        { name: 'card_date', label: '下卡日期', value: v.card_date },
        { name: 'order_date', label: '订货日期', value: v.order_date },
        { name: 'delivery_date', label: '合同交货期', value: v.delivery_date },
        { name: 'end_date', label: '到期日期', value: v.end_date },
      ]
      const badNative = nativeDates.filter((d) => !isValidFormDate(d.value))
      if (badNative.length) {
        editForm.setFields(badNative.map((d) => ({
          name: d.name,
          errors: [`请选择或输入有效的${d.label}`],
        })))
        message.warning(`请修正日期：${badNative.map((d) => d.label).join('、')}`)
        return
      }
      const regRaw = { ...(v.registration_json || {}) } as Record<string, unknown>
      delete regRaw.number_lookup
      const numberAttr = String(regRaw.number_attr || 'WMGF').trim().toUpperCase()
      regRaw.number_attr = numberAttr === 'SY' ? 'SY' : 'WMGF'
      for (const [k, val] of Object.entries(regRaw)) {
        if (val && typeof val === 'object' && dayjs.isDayjs(val)) {
          if (!val.isValid()) {
            message.warning('登记信息中存在无效日期，请重新选择')
            return
          }
          regRaw[k] = val.format('YYYY-MM-DD')
        }
      }
      const toDateOrNull = (d: unknown) => {
        const s = formatFormDate(d)
        return s === undefined ? null : s
      }
      const contractNo = String(v.contract_no || '').trim()
      const payload: Record<string, unknown> = {
        as_draft: !andSubmit,
        payment_terms_json: editPay,
        registration_json: regRaw,
        // 图纸编号系统生成后不可在编辑里清空；有值才回写
        ...(v.drawing_no ? { drawing_no: v.drawing_no } : {}),
        ...(contractNo ? { contract_no: contractNo } : {}),
        peer_contract_no: v.peer_contract_no || null,
        acquire_method: v.acquire_method || null,
        change_type: v.change_type || null,
        customer_id: v.customer_id || null,
        assignee_id: v.assignee_id || null,
        assignee_name: v.assignee_name || null,
        department_id: v.department_id || null,
        department_name: v.department_name || null,
        end_date: toDateOrNull(v.end_date),
        delivery_date: toDateOrNull(v.delivery_date),
        order_date: toDateOrNull(v.order_date),
        card_date: toDateOrNull(v.card_date),
      }
      if (v.amount_total != null) payload.amount_total = v.amount_total
      await contractApi.update(cid!, payload)
      if (currentVersion) await contractApi.updateVersion(currentVersion.id, { key_clauses_json: editLines })
      message.success(andSubmit ? '合同登记信息已保存' : '已存为草稿')
      setEditModal(false)
      fetchContract()
    } catch (e: unknown) {
      if (e && typeof e === 'object' && 'errorFields' in e) return
      const msg = e instanceof Error ? e.message : ''
      if (msg) {
        message.warning(msg)
        if (msg.includes('合同号')) {
          editForm.setFields([{ name: 'contract_no', errors: [msg] }])
          editForm.scrollToField('contract_no', { behavior: 'smooth', block: 'center' })
        }
      }
    } finally {
      setEditSaving(false)
    }
  }

  // 根据付款条款生成回款计划
  type DraftPlan = { remark?: string; amount: number | null; due_date: dayjs.Dayjs | null; trigger_milestone_code?: string }
  const [genModal, setGenModal] = useState(false)
  const [genRows, setGenRows] = useState<DraftPlan[]>([])
  const [genSaving, setGenSaving] = useState(false)
  const [sameContractCount, setSameContractCount] = useState(0)  // 本合同上次生成的计划数
  const [otherPlanCount, setOtherPlanCount] = useState(0)        // 其它来源（手工/其它合同）计划数
  const [replaceExisting, setReplaceExisting] = useState(true)
  const [milestoneOpts, setMilestoneOpts] = useState<{ label: string; value: string }[]>([])

  /** 把合同付款条款映射成回款计划草稿（兼容简道云旧 _widget_ 字段） */
  const deriveDraftPlans = (): DraftPlan[] => {
    const terms = toCanonicalRows(contract?.payment_terms_json, resolvePayColumns())
    const total = typeof contract?.amount_total === 'number' ? contract.amount_total : null
    let allRatio = terms.length > 0
    const rows: DraftPlan[] = terms.map((t) => {
      const explicit = t.amount != null && t.amount !== '' ? Number(t.amount) : null
      const ratio = t.ratio != null && t.ratio !== '' ? Number(t.ratio) : null
      if (explicit != null) allRatio = false
      let amount: number | null = Number.isFinite(explicit as number) ? explicit : null
      if (amount == null && ratio != null && total != null) amount = Math.round(ratio * total * 100) / 100
      const remark = [t.kind, t.note].filter((x) => x != null && x !== '').map(String).join(' · ') || undefined
      return { remark, amount, due_date: t.due_date ? dayjs(t.due_date as string) : null }
    })
    // 末行兜底差额：仅当全部按比例反算且合同总额已知时，吸收凑整误差
    if (allRatio && total != null && rows.length > 0 && rows.every((r) => r.amount != null)) {
      const sumExceptLast = rows.slice(0, -1).reduce((s, r) => s + (r.amount as number), 0)
      rows[rows.length - 1].amount = Math.round((total - sumExceptLast) * 100) / 100
    }
    return rows
  }

  const openGenModal = async () => {
    if (!projectId) {
      message.warning('该合同未关联商机，无法生成回款计划（请先挂接商机）')
      return
    }
    setGenRows(deriveDraftPlans())
    setReplaceExisting(true)
    setGenModal(true)
    try {
      const [plansRes, msRes] = await Promise.all([
        paymentApi.listPlans(projectId),
        deliveryApi.listMilestones(projectId),
      ])
      const plans = plansRes.data || []
      setSameContractCount(plans.filter((p) => p.source_contract_id === cid).length)
      setOtherPlanCount(plans.filter((p) => p.source_contract_id !== cid).length)
      setMilestoneOpts((msRes.data || []).map((m) => ({
        label: `${m.milestone_code}${m.name ? ' · ' + m.name : ''}`, value: m.milestone_code,
      })))
    } catch {
      setSameContractCount(0); setOtherPlanCount(0); setMilestoneOpts([])
    }
  }

  const updateGenRow = (i: number, key: keyof DraftPlan, val: unknown) =>
    setGenRows((rows) => rows.map((r, j) => (j === i ? { ...r, [key]: val } : r)))
  const delGenRow = (i: number) => setGenRows((rows) => rows.filter((_, j) => j !== i))
  const addGenRow = () => setGenRows((rows) => [...rows, { remark: undefined, amount: null, due_date: null }])

  const handleGenerate = async () => {
    const valid = genRows.filter((r) => r.amount != null || r.remark || r.due_date)
    if (!valid.length) { message.warning('没有可生成的回款计划'); return }
    setGenSaving(true)
    try {
      const plans = valid.map((r) => ({
        amount: r.amount ?? undefined,
        due_date: r.due_date ? r.due_date.format('YYYY-MM-DD') : undefined,
        remark: r.remark || undefined,
        trigger_milestone_code: r.trigger_milestone_code || undefined,
      }))
      await paymentApi.bulkCreatePlans(projectId!, plans, {
        source_contract_id: cid,
        replace_existing: sameContractCount > 0 ? replaceExisting : false,
      })
      message.success(`已生成 ${plans.length} 条回款计划`)
      setGenModal(false)
      fetchRelated()
      Modal.confirm({
        title: '回款计划已生成',
        content: `已为该商机生成 ${plans.length} 条回款计划，是否前往「回款」查看？`,
        okText: '前往查看', cancelText: '留在本页',
        onOk: () => navigate(`/opportunities/${projectId}`),
      })
    } catch {
      message.error('生成失败')
    } finally {
      setGenSaving(false)
    }
  }

  // Approval
  const [approvalModal, setApprovalModal] = useState(false)
  const [selectedApprovers, setSelectedApprovers] = useState<string[]>([])
  const [approvalSubmitting, setApprovalSubmitting] = useState(false)

  const userSelect = useUserSelect()
  const customerSelect = useCustomerSelect()

  // Signing workflow
  const [approvalFlow, setApprovalFlow] = useState<import('@/api/types').ApprovalFlowItem | null>(null)
  const [wfInstance, setWfInstance] = useState<WfInstanceDetail | null>(null)
  const [wfCommenting, setWfCommenting] = useState(false)

  // AI analysis
  const [aiResult, setAiResult] = useState<{
    risk_level?: string
    clauses?: { clause: string; risk: string; detail: string }[]
    overall_comment?: string
  } | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  const handleAiAnalyze = async () => {
    if (!selectedVersionId) return
    setAiLoading(true)
    try {
      const res = await aiApi.analyze({ biz_type: 'contract_version', biz_id: selectedVersionId, analysis_type: 'contract_review' })
      setAiResult(res.data?.result || null)
    } catch {
      message.error('AI 分析失败')
    } finally {
      setAiLoading(false)
    }
  }

  const fetchContract = async () => {
    const res = await contractApi.get(cid!)
    const d = res.data
    setContract(d)
    setVersions(d.versions || [])
    const curVer = d.versions?.find((v) => v.version_no === d.current_version_no)
    setCurrentVersion(curVer || null)
    const { lineCols, payCols } = await loadContractDetailColumns()
    const lines = toCanonicalRows(curVer?.key_clauses_json, lineCols)
    setDetailLines(lines.length ? lines : [{}])
    const pays = toCanonicalRows(d.payment_terms_json, payCols)
    setDetailPay(pays.length ? pays : [{}])
    if (curVer) {
      setSelectedVersionId(curVer.id)
      fetchApprovalFlow(curVer.id)
    }
    fetchRelated()
  }

  const saveDetailLines = async () => {
    if (!currentVersion) { message.warning('无合同版本，无法保存明细'); return }
    setLinesSaving(true)
    try {
      const rows = detailLines.filter((r) => Object.values(r).some((x) => x != null && x !== ''))
      await contractApi.updateVersion(currentVersion.id, { key_clauses_json: rows })
      const total = sumLineAmounts(rows)
      if (total > 0) {
        await contractApi.update(cid!, { amount_total: total })
      }
      message.success('合同明细已保存')
      fetchContract()
    } catch { message.error('保存明细失败') }
    finally { setLinesSaving(false) }
  }

  const saveDetailPay = async () => {
    setPaySaving(true)
    try {
      const rows = detailPay.filter((r) => Object.values(r).some((x) => x != null && x !== ''))
      await contractApi.update(cid!, { payment_terms_json: rows })
      message.success('收款计划已保存')
      fetchContract()
    } catch { message.error('保存收款计划失败') }
    finally { setPaySaving(false) }
  }

  const fetchRelated = async () => {
    try {
      const res = await contractApi.related(cid!)
      setRelated(res.data || null)
    } catch {
      setRelated(null)
    }
  }

  const fetchVersion = async (vid: string) => {
    const res = await contractApi.getVersion(vid)
    setCurrentVersion(res.data)
    setSelectedVersionId(vid)
    fetchApprovalFlow(vid)
  }

  const fetchApprovalFlow = async (versionId: string) => {
    // 合同版本审批已切新引擎；旧 approvalApi 仅作兼容回退
    try {
      const wfRes = await workflowApi.byBiz({ biz_type: 'contract_version', biz_id: versionId })
      if (wfRes.data) {
        setWfInstance(wfRes.data)
        setApprovalFlow(null)
        return
      }
      setWfInstance(null)
    } catch {
      setWfInstance(null)
    }
    try {
      const res = await approvalApi.list({ biz_type: 'contract_version', biz_id: versionId })
      const flows = res.data?.items || []
      setApprovalFlow(flows.length > 0 ? flows[0] : null)
    } catch { setApprovalFlow(null) }
  }

  useEffect(() => { fetchContract() }, [cid])

  const handleNewVersion = async () => {
    await contractApi.newVersion(cid!)
    message.success('新版本已创建')
    fetchContract()
  }

  const handleSign = async () => {
    if (!signDate) return
    try {
      await contractApi.sign(cid!, {
        signed_date: signDate.format('YYYY-MM-DD'),
        ...(signatureImage ? { signature_image: signatureImage } : {}),
      })
      message.success('合同已签署')
      setSignModal(false)
      setSignatureImage(null)
      setShowSignPad(false)
      fetchContract()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      if (msg) message.error(msg)
    }
  }

  const openApprovalModal = () => {
    setSelectedApprovers([])
    setApprovalModal(true)
  }

  const handleSubmitApproval = async (withAssignees = false) => {
    if (!selectedVersionId) {
      message.warning('无合同版本，无法提交审批')
      return
    }
    setApprovalSubmitting(true)
    try {
      const payload = withAssignees && selectedApprovers.length > 0
        ? {
            assignee_ids: selectedApprovers,
            assignee_names: selectedApprovers.map(
              (id) => userSelect.options.find((o) => o.value === id)?.label || '',
            ),
          }
        : {}
      await contractApi.submitVersion(selectedVersionId, payload)
      message.success('已提交审批，请在「审批中心」处理待办')
      setApprovalModal(false)
      fetchContract()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      if (!withAssignees && msg && msg.includes('审批人')) {
        openApprovalModal()
        message.info('未匹配到流程/策略，请手动选择审批人')
      } else if (msg) {
        message.error(msg)
      }
    } finally {
      setApprovalSubmitting(false)
    }
  }

  const handleWfComment = async (content: string) => {
    if (!wfInstance?.id) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfInstance.id, content)
      message.success('评论已发表')
      const refreshed = await workflowApi.byBiz({
        biz_type: 'contract_version',
        biz_id: selectedVersionId,
      })
      if (refreshed.data) setWfInstance(refreshed.data)
    } catch {
      message.error('发表评论失败')
    } finally {
      setWfCommenting(false)
    }
  }

  if (!contract) return <DetailSkeleton />

  const verStatus = currentVersion?.status || 'draft'
  // 主合同签署前 status 一直是 draft；展示态以版本审批进度 + 新引擎实例为准
  const displayStatus = (() => {
    if (contract.status === 'signed' || contract.status === 'terminated') return contract.status
    if (verStatus === 'approved' || wfInstance?.status === 'completed') return 'pending_sign'
    if (verStatus === 'submitted' || wfInstance?.status === 'running') return 'approving'
    if (verStatus === 'rejected' || wfInstance?.status === 'rejected') return 'rejected'
    if (approvalFlow?.status === 'approved') return 'pending_sign'
    if (approvalFlow?.status === 'pending') return 'approving'
    if (approvalFlow?.status === 'rejected') return 'rejected'
    return resolveContractDisplayStatus(contract.status, verStatus)
  })()
  const canSubmitApproval = contract.status === 'draft'
    && (verStatus === 'draft' || verStatus === 'rejected')
    && wfInstance?.status !== 'running'
    && approvalFlow?.status !== 'pending'
  // 提交后不可改；仅草稿/驳回（且无进行中流程）可编辑
  const canEdit = canSubmitApproval
    && contract.status !== 'signed'
    && contract.status !== 'terminated'
  const canSign = contract.status === 'draft'
  const canDelete = canDeleteContract
    && isContractDraftDeletable(contract.status, verStatus)
  const stepCurrent = (() => {
    if (contract.status === 'signed' || contract.status === 'terminated') return 3
    if (verStatus === 'approved' || verStatus === 'signed') return 2
    if (verStatus === 'submitted' || verStatus === 'rejected') return 1
    if (wfInstance?.status === 'running' || approvalFlow?.status === 'pending') return 1
    if (wfInstance?.status === 'completed' || approvalFlow?.status === 'approved') return 2
    return 0
  })()
  const stepStatus: 'error' | undefined =
    contract.status === 'terminated' || verStatus === 'rejected' || wfInstance?.status === 'rejected' || approvalFlow?.status === 'rejected'
      ? 'error'
      : undefined
  const approvalDesc = (() => {
    if (wfInstance) {
      if (wfInstance.status === 'completed') return '已通过'
      if (wfInstance.status === 'rejected') return '已驳回'
      if (wfInstance.status === 'running') return wfInstance.flow_steps?.find((s) => s.is_current)?.node_name
        ? `审批中 · ${wfInstance.flow_steps.find((s) => s.is_current)!.node_name}`
        : '审批中'
      if (wfInstance.status === 'withdrawn' || wfInstance.status === 'cancelled') return '已撤回'
      return wfInstance.status
    }
    if (approvalFlow) {
      if (approvalFlow.status === 'pending') return `${approvalFlow.current_node}/${approvalFlow.total_nodes} 审批中`
      if (approvalFlow.status === 'approved') return '已通过'
      if (approvalFlow.status === 'rejected') return '已驳回'
      if (approvalFlow.status === 'withdrawn') return '已撤回'
      return approvalFlow.status
    }
    if (verStatus === 'submitted') return '审批中'
    if (verStatus === 'approved' || verStatus === 'signed') return '已通过'
    if (verStatus === 'rejected') return '已驳回'
    return '待提交'
  })()
  // 只有结构化（行数组）付款条款才能生成回款计划；非行结构（如 {method:"分期"}）不展示按钮
  const canGenerate = toCanonicalRows(contract.payment_terms_json, resolvePayColumns()).length > 0 && contract.status !== 'terminated'
  const genTotal = genRows.reduce((s, r) => s + (r.amount || 0), 0)
  const contractTotal = typeof contract.amount_total === 'number' ? contract.amount_total : null
  const genMismatch = contractTotal != null && Math.abs(genTotal - contractTotal) > 0.01

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-slate-900">{contract.contract_no}</h1>
            <Tag color={contractDisplayStatusColors[displayStatus] || 'default'}>
              {contractDisplayStatusLabels[displayStatus] || displayStatus}
            </Tag>
          </div>
          <p className="text-sm text-slate-500">
            创建人: {contract.created_by_name || '-'} · {contract.created_at ? new Date(contract.created_at).toLocaleDateString('zh-CN') : ''}
          </p>
        </div>
        <Space>
          {siblingNav.hasNav && (
            <RecordPrevNextNav
              index={siblingNav.index}
              total={siblingNav.total}
              disabled={siblingNav.busy}
              onPrev={siblingNav.goPrev}
              onNext={siblingNav.goNext}
            />
          )}
          <AiAnalysisButton bizType="contract" bizId={cid!} />
          {canEdit && (
            <Button icon={<EditOutlined />} onClick={openEditModal}>编辑登记信息</Button>
          )}
          {canSubmitApproval && (
            <Button icon={<AuditOutlined />} loading={approvalSubmitting}
              onClick={() => handleSubmitApproval(false)}>提交审批</Button>
          )}
          {canSign && (
            <Button type="primary" icon={<CheckCircleOutlined />} onClick={() => setSignModal(true)}>签署合同</Button>
          )}
          {contract.status === 'signed' && (
            <Button type="primary" loading={renewLoading} onClick={async () => {
              setRenewLoading(true)
              try {
                await contractApi.renew(contract.id)
                message.success('续约机会已创建，请前往续约管理查看')
              } catch { message.error('创建续约失败') }
              finally { setRenewLoading(false) }
            }}>发起续约</Button>
          )}
          <Button icon={<FilePdfOutlined />} onClick={() => downloadFile(`/api/v1/contracts/${cid}/export/pdf`, `contract_${contract.contract_no}.pdf`)}>导出PDF</Button>
          <Button icon={<PrinterOutlined />} onClick={() => window.print()}>打印</Button>
          {canDelete && (
            <Button danger icon={<DeleteOutlined />} onClick={() => {
              Modal.confirm({
                title: '确认删除',
                content: `确定删除合同「${contract.contract_no}」？仅草稿可删除，删除后不可恢复。`,
                okType: 'danger',
                okText: '删除',
                onOk: async () => {
                  await contractApi.delete(cid!)
                  message.success('已删除')
                  if (projectIdParam) navigate(`/opportunities/${projectIdParam}`)
                  else navigate('/contracts')
                },
              })
            }}>删除</Button>
          )}
          {projectIdParam ? (
            <Button onClick={() => navigate(`/opportunities/${projectIdParam}`)}>返回商机</Button>
          ) : (
            <Button onClick={() => navigate('/contracts')}>返回合同列表</Button>
          )}
        </Space>
      </div>

      <div className="flex gap-4 items-start">
        <div className="flex-1 min-w-0">

      {/* 编辑合同登记 */}
      <Modal
        title="编辑合同登记"
        open={editModal}
        onCancel={() => setEditModal(false)}
        width={980}
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
        footer={[
          <Button key="cancel" htmlType="button" onClick={() => setEditModal(false)}>取消</Button>,
          <Button key="draft" htmlType="button" loading={editSaving} onClick={() => void handleEditSave(false)}>存草稿</Button>,
          <Button key="save" type="primary" htmlType="button" loading={editSaving} onClick={() => void handleEditSave(true)}>保存</Button>,
        ]}
      >
        <FieldPolicyProvider entityType="contract" form={editForm}>
        <Form form={editForm} layout="vertical" className="py-2">
          <Form.Item name="customer_id" label="关联客户">
            <Select
              allowClear showSearch filterOption={false}
              placeholder="搜索客户管理中的客户"
              options={customerSelect.options}
              loading={customerSelect.loading}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
              onChange={async (id?: string) => {
                if (!id) return
                try {
                  const c = (await customerApi.get(id)).data
                  if (!c) return
                  const reg = { ...(editForm.getFieldValue('registration_json') || {}) } as Record<string, unknown>
                  if (c.customer_code) reg.customer_code = c.customer_code
                  const patch: Record<string, unknown> = { registration_json: reg }
                  if (c.department_id) patch.department_id = c.department_id
                  if (c.department_name) patch.department_name = c.department_name
                  if (c.owner_id) {
                    patch.assignee_id = c.owner_id
                    if (c.owner_name) patch.assignee_name = c.owner_name
                  }
                  editForm.setFieldsValue(patch)
                } catch { /* ignore */ }
              }}
            />
          </Form.Item>
          <ContractRegistrationFields
            form={editForm}
            mode="edit"
            slots={{
              line_items: (
                <div>
                  <ContractSubtableTitle fieldId={LINE_ITEMS_FIELD_ID} fallback="合同明细" />
                  <LineItemsEditor
                    value={editLines}
                    onChange={setEditLines}
                    onTotalChange={(t) => editForm.setFieldsValue({ amount_total: t || undefined })}
                  />
                </div>
              ),
              payment_terms: (
                <div>
                  <ContractSubtableTitle fieldId={PAYMENT_TERMS_FIELD_ID} fallback="收款计划" />
                  <Form.Item noStyle shouldUpdate={(prev, cur) => prev.amount_total !== cur.amount_total}>
                    {() => (
                      <PaymentTermsEditor
                        value={editPay}
                        onChange={setEditPay}
                        contractTotal={Number(editForm.getFieldValue('amount_total')) || 0}
                      />
                    )}
                  </Form.Item>
                </div>
              ),
              contract_files: <ContractAttachmentSlots slot="contract_files" contractId={cid} />,
              accept_files: <ContractAttachmentSlots slot="accept_files" contractId={cid} />,
            }}
          />
          <div className="text-[12px] text-slate-400">
            「保存」会校验必填项；「存草稿」仅保存当前已填内容，可稍后补全再保存或提交审批。
          </div>
        </Form>
        </FieldPolicyProvider>
      </Modal>

      {/* 生成回款计划 Modal */}
      <Modal title="生成回款计划" open={genModal} onOk={handleGenerate} confirmLoading={genSaving}
        onCancel={() => setGenModal(false)} width={920}
        okText={genRows.length ? `确认生成 ${genRows.length} 条` : '确认生成'}
        okButtonProps={{ disabled: genRows.length === 0 }} cancelText="取消">
        <div className="py-2 space-y-3">
          <div className="text-sm text-slate-500">
            已根据合同付款条款预填，请核对金额、到期日期与关联里程碑后确认。生成的计划可在商机「回款」中继续编辑。
          </div>
          {sameContractCount > 0 && (
            <div className="p-3 bg-amber-50 border border-amber-100 rounded-lg">
              <Checkbox checked={replaceExisting} onChange={(e) => setReplaceExisting(e.target.checked)}>
                覆盖本合同上次生成的 {sameContractCount} 条计划（取消勾选则追加）
              </Checkbox>
            </div>
          )}
          {otherPlanCount > 0 && (
            <Alert type="info" showIcon
              message={`该商机另有 ${otherPlanCount} 条非本合同生成的计划（手工录入或其它合同），不受影响。`} />
          )}
          <Table size="small" rowKey={(_, i) => String(i)} pagination={false} dataSource={genRows}
            locale={{ emptyText: '无付款条款可生成，点击下方「添加一行」手动录入' }}
            columns={[
              {
                title: '款项说明', key: 'remark',
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <Input size="small" value={genRows[i].remark}
                    placeholder="如：预付款 / 进度款"
                    onChange={(e) => updateGenRow(i, 'remark', e.target.value)} />
                ),
              },
              {
                title: '金额', key: 'amount', width: 160,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <InputNumber size="small" style={{ width: '100%' }} min={0} addonBefore="¥"
                    value={genRows[i].amount} onChange={(v) => updateGenRow(i, 'amount', v)} />
                ),
              },
              {
                title: '到期日期', key: 'due_date', width: 150,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <DatePicker size="small" style={{ width: '100%' }} value={genRows[i].due_date}
                    onChange={(d) => updateGenRow(i, 'due_date', d)} />
                ),
              },
              {
                title: '关联里程碑', key: 'milestone', width: 190,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <Select size="small" style={{ width: '100%' }} allowClear showSearch optionFilterProp="label"
                    placeholder={milestoneOpts.length ? '进度款挂里程碑（可选）' : '暂无里程碑'}
                    value={genRows[i].trigger_milestone_code} options={milestoneOpts}
                    onChange={(v) => updateGenRow(i, 'trigger_milestone_code', v)} />
                ),
              },
              {
                title: '', key: '__op', width: 44,
                render: (_: unknown, _r: DraftPlan, i: number) => (
                  <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => delGenRow(i)} />
                ),
              },
            ]} />
          <div className="flex items-center justify-between">
            <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={addGenRow}>添加一行</Button>
            <div className="text-sm">
              <span className="text-slate-400">合计 </span>
              <span className="font-bold text-primary">{formatMoney(genTotal)}</span>
              {contractTotal != null && (
                <>
                  <span className="text-slate-400"> / 合同金额 </span>
                  <span className="font-semibold text-slate-600">{formatMoney(contractTotal)}</span>
                  {genMismatch && <Tag color="warning" className="ml-2">与合同金额不一致</Tag>}
                </>
              )}
            </div>
          </div>
        </div>
      </Modal>

      {/* Signing Workflow Stepper */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <div className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-4">签章流程</div>
        <Steps
          size="small"
          current={stepCurrent}
          status={stepStatus}
          items={[
            {
              title: '草稿',
              description: stepCurrent === 0 ? '当前' : '完成',
              icon: <Icon name="edit_document" style={{ fontSize: 20 }} />,
            },
            {
              title: '审批',
              description: approvalDesc,
              icon: <Icon name="approval" style={{ fontSize: 20 }} />,
            },
            {
              title: '签章',
              description: contract.status === 'signed' ? '已签署' :
                (verStatus === 'approved' || wfInstance?.status === 'completed' || approvalFlow?.status === 'approved')
                  ? '待签署' : '等待中',
              icon: <Icon name="draw" style={{ fontSize: 20 }} />,
            },
            {
              title: contract.status === 'terminated' ? '已终止' : '生效',
              description: contract.status === 'signed'
                ? `${contract.signed_date || ''}`
                : contract.status === 'terminated' ? '合同已终止' : '等待中',
              icon: <Icon name={contract.status === 'terminated' ? 'cancel' : 'verified'} style={{ fontSize: 20 }} />,
            },
          ]}
        />
        {/* 旧引擎审批记录（新引擎改右侧「流程动态」） */}
        {!wfInstance && approvalFlow?.tasks && approvalFlow.tasks.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <div className="text-sm font-bold text-slate-400 mb-2">审批记录</div>
            <div className="flex flex-wrap gap-2">
              {approvalFlow.tasks.map((t) => (
                <div key={t.id} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium border ${
                  t.status === 'approved' ? 'bg-emerald-50 border-emerald-200 text-emerald-700' :
                  t.status === 'rejected' ? 'bg-red-50 border-red-200 text-red-700' :
                  t.status === 'pending' ? 'bg-blue-50 border-blue-200 text-blue-700' :
                  'bg-slate-50 border-slate-200 text-slate-500'
                }`}>
                  <Icon name={t.status === 'approved' ? 'check_circle' : t.status === 'rejected' ? 'cancel' : t.status === 'pending' ? 'schedule' : 'more_horiz'} style={{ fontSize: 14 }} />
                  {t.assignee_name || '审批人'}
                  {t.comment && <span className="text-slate-400 ml-1">"{t.comment}"</span>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Contract Info — 简道云合同登记全部分区（空值也展示，便于对照） */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4 space-y-6">
        {CONTRACT_REGISTRATION_SECTIONS.map((sec) => {
          const reg = (contract.registration_json || {}) as Record<string, unknown>
          const depOk = (f: (typeof sec.fields)[0]) => {
            if (!f.showWhen) return true
            const sw = f.showWhen
            const raw = (sw.source || 'reg') === 'native'
              ? (contract as unknown as Record<string, unknown>)[sw.field]
              : reg[sw.field]
            if (!sw.equals?.length) return raw != null && raw !== ''
            return sw.equals.includes(raw == null ? '' : String(raw))
          }
          const resolve = (f: (typeof sec.fields)[0]) => {
            // 组织架构字段详情展示名称，不展示裸 id
            if (f.key === 'assignee_id') {
              return contract.assignee_name || contract.assignee_id || '-'
            }
            if (f.key === 'department_id') {
              return contract.department_name || contract.department_id || '-'
            }
            const raw = f.source === 'native'
              ? (contract as unknown as Record<string, unknown>)[f.key]
              : reg[f.key]
            if (f.key === 'amount_total') return raw != null && raw !== '' ? formatMoney(raw as number | string) : '-'
            if (f.key === 'change_type') return formatChangeType(raw as string)
            if (typeof raw === 'number' && (f.widget === 'money' || f.key.includes('amount'))) {
              return formatMoney(raw)
            }
            return formatRegFieldValue(f, raw)
          }
          const renderDesc = (fields: typeof sec.fields) => {
            const visibleFields = fields.filter((f) => depOk(f))
            if (!visibleFields.length) return null
            return (
              <Descriptions size="small" column={3} bordered className="mb-3">
                {visibleFields.map((f) => {
                  const value = resolve(f)
                  return (
                    <Descriptions.Item key={f.key} label={f.label}>
                      {f.key === 'amount_total' && value !== '-' ? (
                        <span className="font-bold text-lg">{value}</span>
                      ) : f.key === 'change_type' && value !== '-' ? (
                        <Tag>{value}</Tag>
                      ) : (
                        value
                      )}
                    </Descriptions.Item>
                  )
                })}
              </Descriptions>
            )
          }
          return (
            <div key={sec.key}>
              <ContractSectionTitle title={sec.title} />
              {renderDesc(sec.fields)}
              {sec.afterSlot === 'line_items' && (
                <div className="mb-4">
                  <div className="flex items-center gap-3 mb-2">
                    <ContractSubtableTitle fieldId={LINE_ITEMS_FIELD_ID} fallback="合同明细" className="flex-1 mb-0" />
                    {canEdit && (
                      <Button type="primary" size="small" loading={linesSaving} onClick={saveDetailLines}>保存明细</Button>
                    )}
                  </div>
                  {canEdit ? (
                    <LineItemsEditor value={detailLines} onChange={setDetailLines} />
                  ) : (
                    <ClauseTermsView value={currentVersion?.key_clauses_json} />
                  )}
                </div>
              )}
              {sec.afterSlot === 'payment_terms' && (
                <div className="mb-4">
                  <div className="flex items-center gap-3 mb-2">
                    <ContractSubtableTitle fieldId={PAYMENT_TERMS_FIELD_ID} fallback="收款计划" className="flex-1 mb-0" />
                    <Space>
                      {canGenerate && (
                        <Button size="small" icon={<Icon name="savings" style={{ fontSize: 16 }} />}
                          onClick={openGenModal}>生成回款计划</Button>
                      )}
                      {canEdit && (
                        <Button type="primary" size="small" loading={paySaving} onClick={saveDetailPay}>保存收款计划</Button>
                      )}
                    </Space>
                  </div>
                  {canEdit ? (
                    <PaymentTermsEditor
                      value={detailPay}
                      onChange={setDetailPay}
                      contractTotal={Number(contract.amount_total) || 0}
                    />
                  ) : (
                    contract.payment_terms_json
                      ? <PaymentTermsView value={contract.payment_terms_json} />
                      : <div className="text-sm text-slate-400">暂无收款计划</div>
                  )}
                </div>
              )}
              {sec.afterSlot === 'contract_files' && (
                <div className="mb-4">
                  <ContractAttachmentSlots slot="contract_files" contractId={cid} />
                </div>
              )}
              {sec.afterSlot === 'accept_files' && (
                <div className="mb-4">
                  <ContractAttachmentSlots slot="accept_files" contractId={cid} />
                </div>
              )}
              {sec.fieldsAfterSlot?.length ? renderDesc(sec.fieldsAfterSlot) : null}
              {sec.key === 'accept' && Array.isArray((contract.registration_json as any)?.accept_uploads) &&
                (contract.registration_json as any).accept_uploads.length > 0 && (
                <div className="mt-2">
                  <div className="text-[12px] font-medium text-slate-500 mb-2 text-center">验收资料（历史同步）</div>
                  <Table size="small" pagination={false} rowKey={(_, i) => String(i)}
                    dataSource={(contract.registration_json as any).accept_uploads}
                    columns={[
                      { title: '验收日期', dataIndex: 'accept_date', width: 140, render: (v: string) => v || '-' },
                      { title: '含图片', dataIndex: 'has_image', width: 90, render: (v: boolean) => v ? '是' : '否' },
                      { title: '含附件', dataIndex: 'has_file', width: 90, render: (v: boolean) => v ? '是' : '否' },
                    ]}
                  />
                </div>
              )}
            </div>
          )
        })}

        {contract.delivery_terms_json && (
          <div>
            <ContractSectionTitle title="交付条款" />
            <DataView value={contract.delivery_terms_json} />
          </div>
        )}
      </div>

      {/* Version Selector + Version Detail */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold uppercase tracking-wider text-slate-400">版本</span>
            <Select
              value={selectedVersionId}
              onChange={fetchVersion}
              style={{ width: 200 }}
              options={versions.map((v) => ({ label: `${v.title || `V${v.version_no}`} (V${v.version_no})`, value: v.id }))}
            />
          </div>
          <Button icon={<CopyOutlined />} onClick={handleNewVersion}>创建新版本</Button>
        </div>

        {currentVersion && (
          <Descriptions size="small" column={3} bordered>
            <Descriptions.Item label="版本标题">{currentVersion.title || '-'}</Descriptions.Item>
            <Descriptions.Item label="版本状态">
              <Tag color={contractVersionStatusColors[currentVersion.status] || 'default'}>
                {contractVersionStatusLabels[currentVersion.status] || currentVersion.status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="风险等级">
              {currentVersion.risk_level ? (
                <span className={`inline-flex px-2 py-0.5 rounded text-[12px] font-bold border ${riskColors[currentVersion.risk_level] || ''}`}>
                  {riskLabels[currentVersion.risk_level]}
                </span>
              ) : '-'}
            </Descriptions.Item>
          </Descriptions>
        )}
      </div>

      {/* Attachments + AI Analysis */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Tabs defaultActiveKey="attachments" className="px-6 pt-2" items={[
          {
            key: 'attachments',
            label: <span className="font-semibold">合同附件</span>,
            children: (
              <div className="pb-6 space-y-4">
                <ContractAttachmentSlots slot="contract_files" contractId={cid!} />
                <ContractAttachmentSlots slot="accept_files" contractId={cid!} />
                <AttachmentPanel bizType="contract" bizId={cid!} title="其它附件（历史）" compact />
              </div>
            ),
          },
          {
            key: 'payment_plans',
            label: <span className="font-semibold">回款计划 ({related?.payment_plans?.length ?? 0})</span>,
            children: (
              <div className="pb-6">
                <Table size="small" rowKey="id" pagination={false}
                  dataSource={related?.payment_plans || []}
                  locale={{ emptyText: '暂无本合同生成的回款计划' }}
                  columns={[
                    { title: '计划编号', dataIndex: 'plan_no', width: 140 },
                    { title: '到期日', dataIndex: 'due_date', width: 120, render: (v: string) => v || '-' },
                    { title: '金额', dataIndex: 'amount', width: 120, align: 'right' as const, render: (v: number) => formatMoney(v) },
                    { title: '状态', dataIndex: 'status', width: 90 },
                    { title: '里程碑', dataIndex: 'trigger_milestone_code', width: 120, render: (v: string) => v || '-' },
                    { title: '说明', dataIndex: 'remark', ellipsis: true, render: (v: string) => v || '-' },
                  ]}
                />
              </div>
            ),
          },
          {
            key: 'payments',
            label: <span className="font-semibold">回款记录 ({related?.payment_records?.length ?? 0})</span>,
            children: (
              <div className="pb-6">
                <Table size="small" rowKey="id" pagination={false}
                  dataSource={related?.payment_records || []}
                  locale={{ emptyText: projectId ? '暂无回款记录' : '无关联商机，无法展示回款' }}
                  columns={[
                    { title: '来款日期', dataIndex: 'received_date', width: 120, render: (v: string) => v || '-' },
                    { title: '金额', dataIndex: 'amount', width: 120, align: 'right' as const, render: (v: number) => formatMoney(v) },
                    { title: '渠道', dataIndex: 'channel', width: 100, render: (v: string) => v || '-' },
                    { title: '参考号', dataIndex: 'reference_no', width: 140, render: (v: string) => v || '-' },
                    { title: '备注', dataIndex: 'remark', ellipsis: true, render: (v: string) => v || '-' },
                  ]}
                />
              </div>
            ),
          },
          {
            key: 'invoices',
            label: <span className="font-semibold">开票 ({
              (related?.invoice_applications?.length ?? 0) + (related?.invoices?.length ?? 0)
            })</span>,
            children: (
              <div className="pb-6 space-y-6">
                <div>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="font-medium">开票申请</span>
                    <Button
                      type="link"
                      size="small"
                      onClick={() => navigate('/invoice-applications')}
                    >
                      打开开票申请列表
                    </Button>
                  </div>
                  <Table
                    size="small"
                    rowKey="id"
                    pagination={false}
                    dataSource={related?.invoice_applications || []}
                    locale={{ emptyText: '暂无关联开票申请（按合同号/图纸号匹配）' }}
                    columns={[
                      { title: '流水号', dataIndex: 'serial_no', width: 140, render: (v: string) => v || '-' },
                      {
                        title: '状态', dataIndex: 'status_label', width: 90,
                        render: (v: string, r: Record<string, unknown>) => v || String(r.status || '-'),
                      },
                      {
                        title: '金额', dataIndex: 'total_amount', width: 120, align: 'right' as const,
                        render: (v: number) => (v == null ? '-' : formatMoney(v)),
                      },
                      { title: '发票号', dataIndex: 'invoice_no', width: 140, render: (v: string) => v || '-' },
                      {
                        title: '开票时间', dataIndex: 'invoice_datetime', width: 160,
                        render: (v: string) => v || '-',
                      },
                      {
                        title: '创建时间', dataIndex: 'created_at', width: 170,
                        render: (v: string) => (v ? String(v).replace('T', ' ').slice(0, 19) : '-'),
                      },
                    ]}
                  />
                </div>
                <div>
                  <div className="mb-2 font-medium text-slate-600">商机发票登记（收款模块）</div>
                  <Table size="small" rowKey="id" pagination={false}
                    dataSource={related?.invoices || []}
                    locale={{ emptyText: projectId ? '暂无发票登记' : '无关联商机，无法展示发票登记' }}
                    columns={[
                      { title: '发票号', dataIndex: 'invoice_no', width: 160 },
                      { title: '开票日', dataIndex: 'invoice_date', width: 120, render: (v: string) => v || '-' },
                      { title: '金额', dataIndex: 'amount', width: 120, align: 'right' as const, render: (v: number) => formatMoney(v) },
                      { title: '状态', dataIndex: 'status', width: 90 },
                      { title: '备注', dataIndex: 'remark', ellipsis: true, render: (v: string) => v || '-' },
                    ]}
                  />
                </div>
              </div>
            ),
          },
          {
            key: 'milestones',
            label: <span className="font-semibold">交付里程碑 ({related?.milestones?.length ?? 0})</span>,
            children: (
              <div className="pb-6">
                <Table size="small" rowKey="id" pagination={false}
                  dataSource={related?.milestones || []}
                  locale={{ emptyText: projectId ? '暂无里程碑' : '无关联商机，无法展示里程碑' }}
                  columns={[
                    { title: '编码', dataIndex: 'milestone_code', width: 100 },
                    { title: '名称', dataIndex: 'name', width: 160, render: (v: string) => v || '-' },
                    { title: '计划日', dataIndex: 'plan_date', width: 120, render: (v: string) => v || '-' },
                    { title: '实际日', dataIndex: 'actual_date', width: 120, render: (v: string) => v || '-' },
                    { title: '状态', dataIndex: 'status', width: 90 },
                  ]}
                />
              </div>
            ),
          },
          {
            key: 'ai_analysis',
            label: <span className="font-semibold flex items-center gap-1"><RobotOutlined /> AI条款分析</span>,
            children: (
              <div className="pb-6">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-sm text-slate-400">AI 将从交付周期、违约条款、知识产权、付款条件等维度分析合同风险</div>
                  <Button type="primary" size="small" icon={<RobotOutlined />} onClick={handleAiAnalyze} loading={aiLoading}>
                    {aiResult ? '重新分析' : '开始分析'}
                  </Button>
                </div>
                {aiLoading ? (
                  <div className="flex items-center justify-center py-16">
                    <Spin tip="AI 正在分析合同条款..." />
                  </div>
                ) : aiResult ? (
                  <div className="space-y-4">
                    {/* Risk Level */}
                    {aiResult.risk_level && (
                      <div className="flex items-center gap-3">
                        <span className="text-sm font-bold uppercase text-slate-400">综合风险</span>
                        <span className={`px-3 py-1 rounded-full text-sm font-bold ${
                          aiResult.risk_level === 'H' ? 'bg-red-50 text-red-600 border border-red-200' :
                          aiResult.risk_level === 'M' ? 'bg-amber-50 text-amber-600 border border-amber-200' :
                          'bg-emerald-50 text-emerald-600 border border-emerald-200'
                        }`}>
                          {aiResult.risk_level === 'H' ? '高风险' : aiResult.risk_level === 'M' ? '中风险' : '低风险'}
                        </span>
                      </div>
                    )}

                    {/* Clause Risk Items */}
                    {Array.isArray(aiResult.clauses) && (
                      <div>
                        <h4 className="text-sm font-bold uppercase text-slate-400 mb-2">条款风险清单</h4>
                        <div className="space-y-2">
                          {aiResult.clauses.map((c, i) => {
                            const riskConfig: Record<string, { bg: string; border: string; icon: string; label: string; iconColor: string }> = {
                              H: { bg: 'bg-red-50', border: 'border-red-200', icon: 'error', label: '高', iconColor: 'text-red-500' },
                              M: { bg: 'bg-amber-50', border: 'border-amber-200', icon: 'warning', label: '中', iconColor: 'text-amber-500' },
                              L: { bg: 'bg-emerald-50', border: 'border-emerald-200', icon: 'check_circle', label: '低', iconColor: 'text-emerald-500' },
                            }
                            const rc = riskConfig[c.risk] || riskConfig.M
                            return (
                              <div key={i} className={`p-3 rounded-lg border ${rc.bg} ${rc.border}`}>
                                <div className="flex items-center gap-2 mb-1">
                                  <Icon name={rc.icon} className={`text-sm ${rc.iconColor}`} />
                                  <span className="text-sm font-bold text-slate-800">{c.clause}</span>
                                  <Tag color={c.risk === 'H' ? 'error' : c.risk === 'M' ? 'warning' : 'success'}>
                                    {rc.label}风险
                                  </Tag>
                                </div>
                                <div className="text-sm text-slate-600 ml-6">{c.detail}</div>
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    {/* Overall Comment */}
                    {aiResult.overall_comment && (
                      <div className="p-4 bg-blue-50 rounded-lg border border-blue-100">
                        <div className="text-sm font-bold uppercase text-blue-400 mb-1">AI 综合建议</div>
                        <div className="text-sm text-blue-800">{String(aiResult.overall_comment)}</div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-16 text-slate-400 text-sm">
                    <RobotOutlined className="text-3xl mb-3 block text-slate-300" />
                    点击"开始分析"让 AI 审核当前合同版本的条款风险
                  </div>
                )}
              </div>
            ),
          },
        ]} />
      </div>

      {/* Sign Modal */}
      <Modal title="签署合同" open={signModal} onOk={handleSign} onCancel={() => { setSignModal(false); setShowSignPad(false); setSignatureImage(null) }}
        width={showSignPad ? 600 : 480}>
        <div className="py-4">
          <p className="text-sm text-slate-600 mb-3">确认签署合同 <span className="font-bold">{contract.contract_no}</span>？</p>
          <div className="mb-4">
            <label className="text-sm font-medium text-slate-700 mb-1 block">签署日期</label>
            <DatePicker className="w-full" value={signDate} onChange={(d) => setSignDate(d)} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-2 block">电子签名（可选）</label>
            {signatureImage ? (
              <div className="border border-slate-200 rounded-lg p-2 bg-slate-50">
                <img src={signatureImage} alt="签名" className="max-h-24" />
                <Button size="small" className="mt-2" onClick={() => { setSignatureImage(null); setShowSignPad(true) }}>重新签名</Button>
              </div>
            ) : showSignPad ? (
              <SignaturePad
                onSave={(dataUrl) => { setSignatureImage(dataUrl); setShowSignPad(false) }}
                onCancel={() => setShowSignPad(false)}
              />
            ) : (
              <Button onClick={() => setShowSignPad(true)} className="border-dashed">
                <Icon name="draw" className="text-sm mr-1" />
                添加手写签名
              </Button>
            )}
          </div>
        </div>
      </Modal>

      {/* Submit Approval Modal — 仅旧引擎无策略时手动选人 */}
      <Modal title="提交合同审批" open={approvalModal} onOk={() => handleSubmitApproval(true)}
        onCancel={() => setApprovalModal(false)} confirmLoading={approvalSubmitting} okText="提交审批">
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            将合同 <b>{contract?.contract_no}</b> 当前版本 V{currentVersion?.version_no} 提交审批
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">选择审批人（按顺序）</label>
            <Select mode="multiple" className="w-full" placeholder="请选择审批人" showSearch filterOption={false}
              value={selectedApprovers} onChange={setSelectedApprovers}
              loading={userSelect.loading}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            <div className="text-sm text-slate-400 mt-1">多选时将按选择顺序依次审批（流程管理未命中时的回退）</div>
          </div>
        </div>
      </Modal>
        </div>

        {wfInstance && (
          <aside
            className="w-[320px] shrink-0 sticky top-4 hidden md:block self-start rounded-xl border border-slate-200 shadow-sm overflow-hidden bg-white"
            style={{ height: 'calc(100vh - 140px)', maxHeight: 840 }}
          >
            <WfFlowDynamics
              steps={wfInstance.flow_steps || []}
              comments={wfInstance.comments || []}
              onSubmitComment={handleWfComment}
              commenting={wfCommenting}
            />
          </aside>
        )}
      </div>

      {wfInstance && (
        <div
          className="md:hidden mt-4 rounded-xl border border-slate-200 shadow-sm overflow-hidden bg-white"
          style={{ height: 420 }}
        >
          <WfFlowDynamics
            steps={wfInstance.flow_steps || []}
            comments={wfInstance.comments || []}
            onSubmitComment={handleWfComment}
            commenting={wfCommenting}
          />
        </div>
      )}
    </div>
  )
}
