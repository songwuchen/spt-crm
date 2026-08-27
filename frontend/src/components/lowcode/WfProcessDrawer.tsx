// 工作流审批详情：左单据+操作 / 右流程动态（对齐简道云审批体验）
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Button, Space, Tag, Drawer, Input, message, Typography, Select, Spin, Radio, Tabs, Modal, Dropdown,
} from 'antd'
import {
  CheckCircleOutlined, CloseCircleOutlined, SwapOutlined,
  RollbackOutlined, FileTextOutlined, PrinterOutlined, ThunderboltOutlined, StopOutlined, SaveOutlined,
  EditOutlined, FullscreenOutlined, FullscreenExitOutlined,
} from '@ant-design/icons'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import { contractApi } from '@/api/contract'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'
import type { ContractItem, ContractVersion } from '@/api/types'
import type { WfInstanceDetail, FieldDefinition } from '@/types/lowcode'
import FormRenderer from '@/components/lowcode/FormRenderer'
import ApproveFieldForm, { missingRequiredFields } from '@/components/lowcode/ApproveFieldForm'
import { filterProdCardLegacyFieldPerms } from '@/constants/prodCardLegacyFields'
import PersonField from '@/components/lowcode/fields/PersonField'
import ContractRegistrationReadonly from '@/components/lowcode/ContractRegistrationReadonly'
import ContractReviewReadonly from '@/components/lowcode/ContractReviewReadonly'
import LeadIntelReviewForm from '@/components/lead/LeadIntelReviewForm'
import LeadOwnerConfirmActions from '@/components/lead/LeadOwnerConfirmActions'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import FormInstanceSystemMeta from '@/components/lowcode/FormInstanceSystemMeta'
import WfActivateFlowModal from '@/components/lowcode/WfActivateFlowModal'
import AttachmentPanel from '@/components/AttachmentPanel'
import ContractAttachmentSlots from '@/components/ContractAttachmentSlots'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'
import { applyApproveFieldDefaults } from '@/utils/lowcodeFormDefaults'
import { resolveNodeActions } from '@/utils/wfNodeActions'
import { canPrintDrawingDocument, isDrawingApproveAndPrintNode, printSchemeInstance } from '@/pages/drawing/schemePrint'
import { isQuoteManagementForm, printQuoteInstance } from '@/pages/quote/quotePrint'
import {
  BIZ_BONUS_PRINT_MODE_LABELS,
  defaultBizBonusPrintMode,
  isBizBonusApproveAndPrintNode,
  isBizBonusForm,
  printBizBonusInstance,
  type BizBonusPrintMode,
} from '@/pages/bonus/bizBonusPrint'
import {
  defaultProdCardPrintMode,
  isProdCardApproveAndPrintNode,
  isProdCardSupplementForm,
  printProdCardInstance,
  type ProdCardPrintMode,
} from '@/pages/drawing/prodCardPrint'
import { isTechAgreementReviewBiz, printTechAgreementReview } from '@/pages/techAgreementReview/techAgreementReviewPrint'
import { isContractReviewBiz, printContractReview } from '@/pages/contractReview/contractReviewPrint'
import { techAgreementReviewApi } from '@/api/techAgreementReview'
import { isLeadOwnerConfirmNode, isLeadReviseTodo, isLeadReactivationIntelTodo, isLeadReactivationFollowTodo, leadReviseEditPath, LEAD_INTEL_FIELD_PERMS } from '@/utils/leadWorkflow'
import { dataLogFromWfDetail } from '@/utils/dataLogLabels'
import { useAuthStore } from '@/stores/useAuthStore'

const { Text, Title } = Typography

/** 180天激活：biz_detail 中属于「本次激活」的字段（对齐简道云 Tab） */
const REACT_BIZ_LABELS = new Set(['项目近况', '跟进进度', '实地拜访情况', '项目状态'])
const WIDE_BIZ_LABELS = new Set([
  '备注1（线索内容）', '备注：请示部门经理的结果', '详细地址', '回退原因',
  '备注2', '操作意见', '备注', '核心需求', '母公司或者控股公司情况及性质说明',
])

function BizDetailGrid({ entries }: { entries: [string, unknown][] }) {
  if (!entries.length) {
    return <Text type="secondary">暂无内容</Text>
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5 rounded-lg bg-slate-50 border border-slate-100 p-4">
      {entries.map(([k, v]) => (
        <div
          key={k}
          className={`flex gap-2 text-sm min-w-0 ${WIDE_BIZ_LABELS.has(k) ? 'sm:col-span-2' : ''}`}
        >
          <span className="shrink-0 w-36 text-slate-500">{k}</span>
          <span className="text-slate-800 font-medium break-all whitespace-pre-wrap">
            {v == null || v === '' ? '—' : String(v)}
          </span>
        </div>
      ))}
    </div>
  )
}

import {
  bizEntityPath,
  formModuleInstancePath,
  resolveWorkflowBizPath,
  workflowDocOpenLabel,
} from '@/utils/workflowBizPath'

export { bizEntityPath } from '@/utils/workflowBizPath'

export function WfProcessDrawer({ open, taskId, instanceId, onClose, onDone }: {
  open: boolean
  taskId?: string | null
  instanceId?: string | null
  onClose: () => void
  onDone: () => void
}) {
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const canActivateFlow = hasPermission('workflow:activate') || hasPermission('workflow:manage')
  const [detail, setDetail] = useState<WfInstanceDetail | null>(null)
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [formData, setFormData] = useState<Record<string, unknown>>({})
  const [opinion, setOpinion] = useState('')
  const [fieldUpdates, setFieldUpdates] = useState<Record<string, unknown>>({})
  const [fieldHighlight, setFieldHighlight] = useState(false)
  const [transferTo, setTransferTo] = useState<unknown>(undefined)
  const [returnTo, setReturnTo] = useState<string | undefined>(undefined)
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(false)
  const [moreMode, setMoreMode] = useState<'transfer' | 'return' | null>(null)
  const [activateOpen, setActivateOpen] = useState(false)
  const [sideTab, setSideTab] = useState('flow')
  const [mainTab, setMainTab] = useState('original')
  const [commenting, setCommenting] = useState(false)
  const [leadFinalStatus, setLeadFinalStatus] = useState<'include' | 'return' | 'revise' | 'attack'>('include')
  const [contract, setContract] = useState<ContractItem | null>(null)
  const [contractVersion, setContractVersion] = useState<ContractVersion | null>(null)
  const [contractLoading, setContractLoading] = useState(false)
  const [contractReview, setContractReview] = useState<ContractReview | null>(null)
  const [contractReviewLoading, setContractReviewLoading] = useState(false)
  const [fullscreen, setFullscreen] = useState(false)

  const loadContractBiz = async (d: WfInstanceDetail) => {
    if (d.biz_type !== 'contract_version') {
      setContract(null); setContractVersion(null)
      return
    }
    const cid = d.biz_ref_id
    const vid = d.biz_id
    if (!cid && !vid) return
    setContractLoading(true)
    try {
      const [cRes, vRes] = await Promise.all([
        cid ? contractApi.get(cid).catch(() => null) : Promise.resolve(null),
        vid ? contractApi.getVersion(vid).catch(() => null) : Promise.resolve(null),
      ])
      if (cRes?.data) setContract(cRes.data)
      if (vRes?.data) {
        setContractVersion(vRes.data)
        if (!cRes?.data && vRes.data.contract_id) {
          const c2 = await contractApi.get(vRes.data.contract_id).catch(() => null)
          if (c2?.data) setContract(c2.data)
        }
      } else if (cRes?.data?.versions?.length && vid) {
        const match = cRes.data.versions.find((v) => v.id === vid)
          || cRes.data.versions.find((v) => v.version_no === cRes.data.current_version_no)
        if (match) setContractVersion(match)
      }
    } finally {
      setContractLoading(false)
    }
  }

  const loadContractReviewBiz = async (d: WfInstanceDetail) => {
    if (d.biz_type !== 'contract_review') {
      setContractReview(null)
      return
    }
    const rid = d.biz_id
    if (!rid) return
    setContractReviewLoading(true)
    try {
      const res = await contractReviewApi.get(rid).catch(() => null)
      setContractReview(res?.data || null)
    } finally {
      setContractReviewLoading(false)
    }
  }

  const reloadDetail = async () => {
    if (!instanceId) return
    const d = await workflowApi.instance(instanceId, taskId ? { task_id: taskId } : undefined)
    setDetail(d.data)
    // 优先用流程详情内嵌的表单快照（审批人不必有 form_data:view）
    let nextFields: FieldDefinition[] = []
    if (d.data.form_fields?.length) {
      nextFields = d.data.form_fields
      setFields(d.data.form_fields)
      setFormData(d.data.form_data || {})
    } else if (d.data.form_instance_id) {
      try {
        const fi = await lowcodeApi.getInstance(d.data.form_instance_id)
        nextFields = fi.data.field_definitions
        setFields(fi.data.field_definitions)
        setFormData(fi.data.form_data)
      } catch {
        setFields([])
        setFormData({})
      }
    } else {
      setFields([]); setFormData({})
    }
    const ct = d.data.current_task
    const seed = { ...(ct?.field_values || {}) }
    setFieldUpdates(applyApproveFieldDefaults(seed, {
      fieldIds: (ct?.field_perms || []).map((p) => p.field),
      formFields: nextFields,
      fieldMeta: ct?.field_meta,
    }))
    await loadContractBiz(d.data)
    await loadContractReviewBiz(d.data)
  }

  useEffect(() => {
    if (!open) {
      setFullscreen(false)
      return
    }
    if (!instanceId) return
    setOpinion(''); setTransferTo(undefined); setReturnTo(undefined); setFieldUpdates({}); setFieldHighlight(false); setMoreMode(null)
    setSideTab('flow'); setMainTab('original'); setContract(null); setContractVersion(null)
    setContractReview(null)
    setLoading(true)
    ;(async () => {
      try {
        await reloadDetail()
      } finally {
        setLoading(false)
      }
    })()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 仅随抽屉打开/实例切换重载
  }, [open, instanceId, taskId])

  // 线索修订待办：关闭抽屉，跳到与首次申报相同的编辑页
  useEffect(() => {
    if (!open || !detail) return
    const ct = detail.current_task
    const revise = isLeadReviseTodo({
      taskKind: ct?.task_kind,
      nodeType: ct?.node_type,
      nodeName: ct?.node_name,
    })
    if (detail.biz_type === 'lead' && detail.biz_id && revise && ct?.task_id) {
      onClose()
      navigate(leadReviseEditPath(detail.biz_id, ct.task_id))
    }
  }, [open, detail, navigate, onClose])

  // 客户修订待办：跳到客户编辑页修改后再提（审批抽屉内无法编辑原生字段）
  useEffect(() => {
    if (!open || !detail) return
    const ct = detail.current_task
    const revise = ct?.task_kind === 'revise' || ct?.node_type === 'revise'
    if (detail.biz_type === 'customer' && detail.biz_id && revise && ct?.task_id) {
      onClose()
      const q = new URLSearchParams({ wf: detail.id, task: ct.task_id })
      navigate(`/customers/${detail.biz_id}/edit?${q.toString()}`)
    }
  }, [open, detail, navigate, onClose])

  // 180天激活待办：默认打开「本次激活内容」Tab（对齐简道云）
  useEffect(() => {
    if (!open || !detail || detail.biz_type !== 'lead_reactivation') return
    const ct = detail.current_task
    const revise = ct?.task_kind === 'revise' || ct?.node_type === 'revise'
    const act = !!ct?.task_id && (detail.status === 'running' || revise)
    const followTodo = isLeadReactivationFollowTodo({
      bizType: detail.biz_type,
      nodeId: ct?.node_id,
      nodeName: ct?.node_name,
    })
    if (act && ((ct?.field_perms?.length ?? 0) > 0 || followTodo)) setMainTab('activation')
  }, [open, detail])

  // URL/调用方传入的 taskId 仅作加载提示；能否操作以 current_task 为准（已办任务 id 不能误开操作区）
  const effectiveTaskId = detail?.current_task?.task_id || null
  const isReviseTask = detail?.current_task?.task_kind === 'revise'
    || detail?.current_task?.node_type === 'revise'
  const canAct = !!effectiveTaskId && (detail?.status === 'running' || isReviseTask)
  const nodeActs = resolveNodeActions(detail?.current_task?.node_actions, detail?.biz_type)

  const canPrintScheme = canPrintDrawingDocument(fields, formData, detail?.process_name)
  const canPrintProdCard = isProdCardSupplementForm(fields, formData, detail?.process_name)
  const canPrintQuote = isQuoteManagementForm(undefined, detail?.form_code)
  const canPrintBonus = isBizBonusForm(detail?.form_code, undefined, detail?.process_name)
  const canPrintTar = isTechAgreementReviewBiz(detail?.biz_type)
  const canPrintContractReview = isContractReviewBiz(detail?.biz_type)
  const approveAndPrint = canAct && nodeActs.submit && (
    (canPrintScheme && (isDrawingApproveAndPrintNode(detail?.current_task?.node_name) || nodeActs.submit_print))
    || (canPrintProdCard && (isProdCardApproveAndPrintNode(detail?.current_task?.node_name) || nodeActs.submit_print))
    || (canPrintBonus && (isBizBonusApproveAndPrintNode(detail?.current_task?.node_name) || nodeActs.submit_print))
  )

  const handlePrintScheme = async (prodMode?: ProdCardPrintMode, bonusMode?: BizBonusPrintMode) => {
    try {
      const ct = detail?.current_task
      const mergedForm = { ...formData, ...fieldUpdates }
      if (canPrintTar && detail?.biz_id) {
        const res = await techAgreementReviewApi.get(detail.biz_id)
        await printTechAgreementReview({ row: res.data, flowSteps: detail?.flow_steps })
        return
      }
      if (canPrintContractReview && detail?.biz_id) {
        const res = await contractReviewApi.get(detail.biz_id)
        await printContractReview({ row: res.data, flowSteps: detail?.flow_steps })
        return
      }
      if (canPrintQuote) {
        await printQuoteInstance({
          formData: mergedForm,
          fieldDefinitions: fields,
          businessNo: detail?.business_no,
        })
        return
      }
      if (canPrintBonus) {
        await printBizBonusInstance({
          formData: mergedForm,
          fieldDefinitions: fields,
          businessNo: detail?.business_no,
          flowSteps: detail?.flow_steps,
          mode: bonusMode || defaultBizBonusPrintMode(),
        })
        return
      }
      if (canPrintProdCard) {
        const inject = ct && isProdCardApproveAndPrintNode(ct.node_name) && opinion.trim()
          ? {
            node_name: ct.node_name,
            opinion: opinion.trim(),
            action: 'approve',
          }
          : null
        await printProdCardInstance({
          formData: mergedForm,
          fieldDefinitions: fields,
          businessNo: detail?.business_no,
          flowSteps: detail?.flow_steps,
          mode: prodMode || defaultProdCardPrintMode(mergedForm),
          injectApproval: inject,
        })
        return
      }
      const inject = ct && isDrawingApproveAndPrintNode(ct.node_name) && opinion.trim()
        ? {
          node_name: ct.node_name,
          opinion: opinion.trim(),
          action: 'approve',
        }
        : null
      await printSchemeInstance({
        formData: mergedForm,
        fieldDefinitions: fields,
        businessNo: detail?.business_no,
        flowSteps: detail?.flow_steps,
        injectApproval: inject,
      })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '打印失败')
    }
  }

  const handleEndProcess = () => {
    if (!detail?.id) return
    Modal.confirm({
      title: '确认手动结束？',
      content: '结束后将取消「修改并重新提交」待办，流程不再出现在待办列表。如需再走审批，可在「我发起的」中重新发起。',
      okText: '结束流程',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        setBusy(true)
        try {
          await workflowApi.endProcess(detail.id)
          message.success('已手动结束流程')
          onDone()
          onClose()
        } catch (err: unknown) {
          const msg = err instanceof Error ? err.message : ''
          if (msg) message.warning(msg)
        } finally {
          setBusy(false)
        }
      },
    })
  }

  const act = async (action: string) => {
    if (!effectiveTaskId) return
    if (action === 'transfer') {
      const ids = Array.isArray(transferTo)
        ? transferTo.filter(Boolean)
        : (transferTo ? [transferTo] : [])
      if (!ids.length) return message.error('请选择转交接收人')
    }
    if (action === 'return' && !returnTo) return message.error('请选择退回的目标节点')
    const ct = detail?.current_task
    if (action === 'approve' && ct && !isReviseTask) {
      if (ct.opinion_required && !opinion.trim()) return message.error('请填写审批意见')
      const submitPerms = filterProdCardLegacyFieldPerms(ct.field_perms || [], ct.node_name)
      const miss = missingRequiredFields(submitPerms, fieldUpdates, {
        rules: detail?.form_rules,
        formFields: fields,
        formData,
        fieldMeta: ct.field_meta,
        nodeName: ct.node_name,
      })
      if (miss.length) {
        setFieldHighlight(true)
        const labels = miss.map((id) => ct.field_meta?.find((m) => m.id === id)?.label || id)
        return message.error(`请填写必填项: ${labels.join('、')}`)
      }
    }
    setBusy(true)
    try {
      if (action === 'save') {
        if (isReviseTask && detail?.form_instance_id) {
          const nextData = { ...formData, ...fieldUpdates }
          await lowcodeApi.updateInstance(detail.form_instance_id, { form_data: nextData })
        } else {
          const actPerms = filterProdCardLegacyFieldPerms(ct?.field_perms || [], ct?.node_name)
          const updates = actPerms.length
            ? Object.fromEntries(actPerms.map((p) => [p.field, fieldUpdates[p.field]]))
            : undefined
          await workflowApi.act(effectiveTaskId, { action: 'save', field_updates: updates })
        }
        message.success('已暂存')
        await reloadDetail()
        return
      }
      // 修订待办：先保存表单再重新提交
      if (isReviseTask && (action === 'approve' || action === 'resubmit')) {
        if (detail?.form_instance_id) {
          const nextData = { ...formData, ...fieldUpdates }
          await lowcodeApi.updateInstance(detail.form_instance_id, { form_data: nextData })
        }
        await workflowApi.act(effectiveTaskId, { action: 'resubmit', opinion: opinion.trim() || undefined })
        message.success('已重新提交'); onDone(); onClose()
        return
      }
      const actPerms = filterProdCardLegacyFieldPerms(ct?.field_perms || [], ct?.node_name)
      const updates = actPerms.length
        ? Object.fromEntries(actPerms.map((p) => [p.field, fieldUpdates[p.field]]))
        : undefined
      const mergedForm = { ...formData, ...fieldUpdates }
      const shouldPrintAfterApprove = action === 'approve'
        && (
          (canPrintScheme && isDrawingApproveAndPrintNode(ct?.node_name))
          || (canPrintProdCard && isProdCardApproveAndPrintNode(ct?.node_name))
          || (canPrintBonus && isBizBonusApproveAndPrintNode(ct?.node_name))
        )
      await workflowApi.act(effectiveTaskId, {
        action, opinion: opinion.trim() || undefined,
        transfer_to: action === 'transfer'
          ? (Array.isArray(transferTo)
            ? (transferTo as string[]).filter(Boolean)
            : (transferTo ? [String(transferTo)] : undefined))
          : undefined,
        to_node_id: action === 'return' ? returnTo : undefined,
        field_updates: action === 'approve' ? updates : undefined,
      })
      if (shouldPrintAfterApprove) {
        message.success('已通过，正在打开打印预览')
        try {
          const inject = {
            node_name: ct?.node_name,
            opinion: opinion.trim() || undefined,
            action: 'approve',
          }
          if (canPrintProdCard) {
            await printProdCardInstance({
              formData: mergedForm,
              fieldDefinitions: fields,
              businessNo: detail?.business_no,
              flowSteps: detail?.flow_steps,
              mode: defaultProdCardPrintMode(mergedForm),
              injectApproval: inject,
            })
          } else if (canPrintBonus) {
            await printBizBonusInstance({
              formData: mergedForm,
              fieldDefinitions: fields,
              businessNo: detail?.business_no,
              flowSteps: detail?.flow_steps,
              mode: defaultBizBonusPrintMode(),
            })
          } else {
            await printSchemeInstance({
              formData: mergedForm,
              fieldDefinitions: fields,
              businessNo: detail?.business_no,
              flowSteps: detail?.flow_steps,
              injectApproval: inject,
            })
          }
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          message.warning(msg || '已通过，打印失败，可稍后点打印重试')
        }
        onDone(); onClose()
        return
      }
      message.success('已处理'); onDone(); onClose()
    } finally { setBusy(false) }
  }

  const submitComment = async (content: string) => {
    if (!instanceId) return
    setCommenting(true)
    try {
      await workflowApi.comment(instanceId, content)
      await reloadDetail()
      setSideTab('comments')
      message.success('评论已发送')
    } finally {
      setCommenting(false)
    }
  }

  const docPath = detail ? resolveWorkflowBizPath({
    bizType: detail.biz_type,
    bizId: detail.biz_id,
    bizRefId: detail.biz_ref_id,
    formInstanceId: detail.form_instance_id,
    formCode: detail.form_code,
    taskKind: detail.current_task?.task_kind,
    nodeType: detail.current_task?.node_type,
    nodeName: detail.current_task?.node_name,
    taskId: effectiveTaskId,
  }) : null
  const docOpenLabel = workflowDocOpenLabel({
    isRevise: isReviseTask,
    bizType: detail?.biz_type,
    formCode: detail?.form_code,
  })
  const bizEntries = detail?.biz_detail ? Object.entries(detail.biz_detail) : []
  const isLeadReactivation = detail?.biz_type === 'lead_reactivation'
  const originalBizEntries = bizEntries.filter(([k]) => !REACT_BIZ_LABELS.has(k))
  const activationBizEntries = bizEntries.filter(([k]) => REACT_BIZ_LABELS.has(k))
  const currentNode = detail?.current_task?.node_name
    || detail?.flow_steps?.find((s) => s.is_current)?.node_name
    || '审批'
  const isLeadOwnerConfirm = detail?.biz_type === 'lead' && isLeadOwnerConfirmNode(
    detail?.current_task?.node_name,
    detail?.current_task?.node_id,
  )
  const isLeadReactivationIntel = detail?.biz_type === 'lead_reactivation' && canAct && !!effectiveTaskId
    && isLeadReactivationIntelTodo({
      bizType: detail.biz_type,
      nodeId: detail.current_task?.node_id,
      nodeName: detail.current_task?.node_name,
    })
  const isLeadIntel = (detail?.biz_type === 'lead' && canAct && !!effectiveTaskId && !!detail?.biz_id
    && !isReviseTask && !isLeadOwnerConfirm)
    || isLeadReactivationIntel

  const taskFieldPerms = detail?.current_task?.field_perms || []
  const effectiveFieldPerms = isLeadIntel && taskFieldPerms.length === 0
    ? LEAD_INTEL_FIELD_PERMS
    : taskFieldPerms
  const hasNodeFields = canAct && effectiveFieldPerms.length > 0 && !!detail?.current_task
  /** 审批抽屉内不整单编辑；修订待办除外（走原单据编辑页） */
  const canSaveDraft = canAct && !isLeadIntel && !isLeadOwnerConfirm && nodeActs.save
    && (detail?.current_task?.field_perms?.length ?? 0) > 0
    && (isReviseTask || effectiveFieldPerms.length > 0)
  const formEditPath = detail?.form_instance_id && detail?.form_code
    ? formModuleInstancePath(detail.form_code, detail.form_instance_id, { edit: true })
    : null

  const isLeadReactivationFollow = detail?.biz_type === 'lead_reactivation' && canAct && !!effectiveTaskId
    && isLeadReactivationFollowTodo({
      bizType: detail.biz_type,
      nodeId: detail.current_task?.node_id,
      nodeName: detail.current_task?.node_name,
    })
  const isLeadReactivationFillerConfirm = isLeadReactivationFollow
    && detail?.current_task?.node_id === 'approval_filler'
    && !(detail.current_task.field_perms?.length)

  const nodeFieldSection = hasNodeFields && detail?.current_task ? (
    <section className="rounded-lg border border-amber-200 bg-amber-50/40 p-4">
      <div className="text-sm font-semibold text-slate-700 mb-2">
        本节点{effectiveFieldPerms.every((p) => p.access === 'readonly') ? '核对' : '填写'}
        （{detail.current_task.node_name || '审批'}）
      </div>
      <ApproveFieldForm
        currentTask={{
          ...detail.current_task,
          field_perms: filterProdCardLegacyFieldPerms(
            effectiveFieldPerms.filter((p) => p.field !== 'review_opinion'),
            detail.current_task.node_name,
          ),
        }}
        values={fieldUpdates}
        onChange={setFieldUpdates}
        showTitle={false}
        highlightMissing={fieldHighlight}
        rules={detail.form_rules || []}
        formData={formData}
        formFields={fields}
      />
      {isLeadIntel && (
        <div className="mt-4 pt-3 border-t border-amber-100/80">
          <div className="text-sm font-medium text-slate-700 mb-2">
            <span className="text-red-500 mr-0.5">*</span>项目最终状态
          </div>
          <Radio.Group
            value={leadFinalStatus}
            onChange={(e) => setLeadFinalStatus(e.target.value)}
            optionType="button"
            buttonStyle="solid"
            options={isLeadReactivationIntel
              ? [
                  { value: 'include', label: '收录' },
                  { value: 'revise', label: '回退' },
                  { value: 'attack', label: '袭击' },
                ]
              : [
                  { value: 'include', label: '收录' },
                  { value: 'revise', label: '回退' },
                  { value: 'return', label: '驳回' },
                  { value: 'attack', label: '袭击' },
                ]}
          />
          {!isLeadReactivationIntel && leadFinalStatus === 'return' && (
            <div className="mt-2 text-xs text-amber-700">驳回须在上方填写原因；驳回后不可再报备</div>
          )}
          {leadFinalStatus === 'revise' && (
            <div className="mt-2 text-xs text-blue-700">
              {isLeadReactivationIntel
                ? '回退须在上方填写原因；将退回内勤或业务员重新处理'
                : '回退须在上方填写原因；申报人可修改后重新提交'}
            </div>
          )}
        </div>
      )}
    </section>
  ) : isLeadReactivationFillerConfirm ? (
    <section className="rounded-lg border border-slate-200 bg-slate-50/80 p-4">
      <div className="text-sm text-slate-600">
        请核对左侧「本次激活内容」中业务员填写的跟进信息，确认无误后点击「通过」提交情报审。
      </div>
    </section>
  ) : null

  const defaultBizSection = (
    <>
      <div className="text-sm font-semibold text-slate-700 mb-2">
        {detail?.biz_type === 'contract_version' && contract
          ? '合同登记信息'
          : detail?.biz_type === 'lead'
            ? '申报信息（创建时填写）'
            : detail?.biz_type === 'customer'
              ? '客户信息'
              : detail?.biz_type === 'contract_review'
                ? '合同评审信息'
                : detail?.biz_type === 'tech_agreement_review'
                  ? '技术协议评审信息'
                  : '业务信息'}
      </div>
      {detail?.biz_type === 'lead' && detail.biz_id && (
        <div className="mb-4">
          <AttachmentPanel bizType="lead" bizId={detail.biz_id} title="附件" compact readonly />
        </div>
      )}
      {detail?.biz_type === 'contract_version' && (contract?.id || detail.biz_ref_id) && (
        <div className="mb-4 space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
          <div className="text-sm font-semibold text-slate-700">合同附件（发起人上传）</div>
          <ContractAttachmentSlots
            slot="contract_files"
            contractId={contract?.id || detail.biz_ref_id || undefined}
            readonly
          />
          <ContractAttachmentSlots
            slot="accept_files"
            contractId={contract?.id || detail.biz_ref_id || undefined}
            readonly
          />
        </div>
      )}
      {fields.length ? (
        <FormRenderer
          fields={fields}
          mode={isReviseTask ? 'edit' : 'readonly'}
          value={isReviseTask ? { ...formData, ...fieldUpdates } : formData}
          onChange={isReviseTask ? ((v) => {
            setFormData(v)
            setFieldUpdates(v)
          }) : undefined}
          rules={detail?.form_rules || []}
          applyFieldPerms={false}
          gridLayout={fullscreen ? 'adaptive' : 'default'}
        />
      ) : detail?.biz_type === 'contract_version' ? (
        contractLoading ? (
          <div className="py-8 text-center"><Spin /></div>
        ) : contract ? (
          <ContractRegistrationReadonly contract={contract} version={contractVersion} />
        ) : bizEntries.length ? (
          <BizDetailGrid entries={bizEntries} />
        ) : (
          <Text type="secondary">暂无业务明细{docPath ? '，可点击上方「打开原单据」' : ''}</Text>
        )
      ) : detail?.biz_type === 'contract_review' ? (
        contractReviewLoading ? (
          <div className="py-8 text-center"><Spin /></div>
        ) : contractReview ? (
          <ContractReviewReadonly row={contractReview} compactAttachments />
        ) : bizEntries.length ? (
          <BizDetailGrid entries={bizEntries} />
        ) : (
          <Text type="secondary">暂无业务明细{docPath ? '，可点击上方「打开原单据」' : ''}</Text>
        )
      ) : bizEntries.length ? (
        <BizDetailGrid entries={bizEntries} />
      ) : (
        <Text type="secondary">暂无业务明细{docPath ? '，可点击上方「打开原单据」' : ''}</Text>
      )}
      {detail?.biz_type === 'customer' && detail.biz_id && (
        <div className="mt-4">
          <AttachmentPanel bizType="customer" bizId={detail.biz_id} title="附件" compact readonly />
        </div>
      )}
      {detail?.biz_type === 'tech_agreement_review' && detail.biz_id && (
        <div className="mt-4 space-y-3">
          <AttachmentPanel
            bizType="tech_agreement_review_drawing"
            bizId={detail.biz_id}
            title="认可图（附件）"
            compact
            readonly
          />
          <AttachmentPanel
            bizType="tech_agreement_review"
            bizId={detail.biz_id}
            title="技术协议（附件）"
            compact
            readonly
          />
        </div>
      )}
    </>
  )

  return (
    <Drawer
      title={null}
      width={fullscreen ? '100vw' : 'min(1100px, 96vw)'}
      open={open}
      onClose={onClose}
      destroyOnClose
      styles={{
        body: { padding: 0, height: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column' },
        wrapper: { height: '100%' },
      }}
      className="wf-approve-drawer"
      rootClassName={fullscreen ? 'wf-approve-drawer-root spt-drawer-fullscreen' : 'wf-approve-drawer-root'}
    >
      {loading || !detail ? (
        <div className="flex items-center justify-center h-full min-h-[560px]"><Spin /></div>
      ) : (
        <div className="flex h-full min-h-0 flex-1 flex-col lg:flex-row overflow-hidden">
          {/* 左侧：单据滚动 + 底部固定操作区 */}
          <div className="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-100 shrink-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {detail.business_no && (
                      <Text type="secondary" className="text-xs font-mono">{detail.business_no}</Text>
                    )}
                    {PSTATUS[detail.status] && (
                      <Tag color={PSTATUS[detail.status].color}>{PSTATUS[detail.status].text}</Tag>
                    )}
                  </div>
                  <Title level={4} style={{ margin: '6px 0 0' }} className="!text-lg truncate">
                    {detail.title || detail.business_no || '(无标题)'}
                  </Title>
                  <div className="mt-2 inline-flex items-center gap-2 rounded-md bg-blue-50 text-blue-700 px-2.5 py-1 text-sm font-medium">
                    {isReviseTask ? '请修改后重新提交' : `当前节点：${currentNode}`}
                  </div>
                </div>
                <Space size="small" wrap className="shrink-0">
                  {canPrintTar && (
                    <Button
                      size="small"
                      icon={<PrinterOutlined />}
                      onClick={() => { void handlePrintScheme() }}
                    >
                      打印
                    </Button>
                  )}
                  {canPrintContractReview && (
                    <Button
                      size="small"
                      icon={<PrinterOutlined />}
                      onClick={() => { void handlePrintScheme() }}
                    >
                      打印
                    </Button>
                  )}
                  {canPrintQuote && (
                    <Button
                      size="small"
                      icon={<PrinterOutlined />}
                      onClick={() => { void handlePrintScheme() }}
                    >
                      打印报价单
                    </Button>
                  )}
                  {canPrintScheme && (
                    <Button
                      size="small"
                      icon={<PrinterOutlined />}
                      onClick={() => { void handlePrintScheme() }}
                    >
                      打印
                    </Button>
                  )}
                  {canPrintProdCard && (
                    <Dropdown
                      menu={{
                        items: [
                          {
                            key: 'notice',
                            label: '生产通知单',
                            onClick: () => { void handlePrintScheme('notice') },
                          },
                          {
                            key: 'supplement',
                            label: '生产补充卡',
                            onClick: () => { void handlePrintScheme('supplement') },
                          },
                        ],
                      }}
                      trigger={['click']}
                    >
                      <Button size="small" icon={<PrinterOutlined />}>
                        打印
                      </Button>
                    </Dropdown>
                  )}
                  {canPrintBonus && (
                    <Dropdown
                      menu={{
                        items: (Object.entries(BIZ_BONUS_PRINT_MODE_LABELS) as [BizBonusPrintMode, string][]).map(
                          ([key, label]) => ({
                            key,
                            label,
                            onClick: () => { void handlePrintScheme(undefined, key) },
                          }),
                        ),
                      }}
                      trigger={['click']}
                    >
                      <Button size="small" icon={<PrinterOutlined />}>
                        打印
                      </Button>
                    </Dropdown>
                  )}
                  {canActivateFlow && detail.can_activate && (
                    <Button
                      size="small"
                      type="primary"
                      ghost
                      icon={<ThunderboltOutlined />}
                      onClick={() => setActivateOpen(true)}
                    >
                      激活流程
                    </Button>
                  )}
                  {docPath && (
                    <Button
                      size="small"
                      icon={<FileTextOutlined />}
                      onClick={() => { onClose(); navigate(docPath) }}
                    >
                      {contract ? '打开合同页' : docOpenLabel}
                    </Button>
                  )}
                  {formEditPath && !isReviseTask && (
                    <Button
                      size="small"
                      icon={<EditOutlined />}
                      onClick={() => { onClose(); navigate(formEditPath) }}
                    >
                      编辑原单据
                    </Button>
                  )}
                  <Button
                    size="small"
                    icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
                    onClick={() => setFullscreen((v) => !v)}
                    title={fullscreen ? '退出全屏' : '全屏查看'}
                    aria-label={fullscreen ? '退出全屏' : '全屏查看'}
                  >
                    {fullscreen ? '退出全屏' : '全屏'}
                  </Button>
                </Space>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
              {isLeadReactivation ? (
                <Tabs
                  activeKey={mainTab}
                  onChange={setMainTab}
                  className="wf-reactivation-main-tabs"
                  items={[
                    {
                      key: 'original',
                      label: '原申报信息内容',
                      children: (
                        <div className="space-y-4 pt-1">
                          {detail.biz_id && (
                            <AttachmentPanel bizType="lead" bizId={detail.biz_id} title="附件" compact readonly />
                          )}
                          <BizDetailGrid entries={originalBizEntries} />
                        </div>
                      ),
                    },
                    {
                      key: 'activation',
                      label: '本次激活内容',
                      children: (
                        <div className="space-y-4 pt-1">
                          {activationBizEntries.length > 0 && (
                            <BizDetailGrid entries={activationBizEntries} />
                          )}
                          {nodeFieldSection}
                          {!hasNodeFields && !activationBizEntries.length && (
                            <Text type="secondary">暂无激活填写内容</Text>
                          )}
                        </div>
                      ),
                    },
                  ]}
                />
              ) : (
                <>
                  <section>{defaultBizSection}</section>
                  {nodeFieldSection}
                </>
              )}
              <FormInstanceSystemMeta
                initiatorName={detail.initiator_name}
                createdAt={detail.created_at || detail.started_at}
                updatedAt={detail.updated_at}
                status={detail.status}
                flowSteps={detail.flow_steps}
              />
            </div>

            {/* 底部固定：操作意见 + 操作按钮（线索按钮为收录/袭击/回退/暂存） */}
            {canAct && (
              <div className="shrink-0 border-t border-slate-200 bg-white shadow-[0_-4px_12px_rgba(15,23,42,0.04)]">
                <div className="px-5 pt-3 pb-2">
                  <div className="text-sm font-semibold text-slate-700 mb-2">操作意见</div>
                  <Input.TextArea
                    rows={3}
                    placeholder={detail.current_task?.opinion_required
                      ? '请填写操作意见（必填）'
                      : '请填写操作意见（可选）'}
                    value={opinion}
                    onChange={(e) => setOpinion(e.target.value)}
                    className="!resize-none"
                  />
                </div>
                {isLeadIntel ? (
                  <div className="px-5 py-3">
                    <LeadIntelReviewForm
                      actionsOnly
                      showFinalStatus={false}
                      compact
                      mode={detail.biz_type === 'lead_reactivation' ? 'reactivation' : 'lead'}
                      leadId={detail.biz_id!}
                      taskId={effectiveTaskId!}
                      fieldValues={fieldUpdates}
                      opinion={opinion}
                      finalStatus={leadFinalStatus}
                      onFinalStatusChange={(v) => {
                        if (v === 'include' || v === 'return' || v === 'revise' || v === 'attack') {
                          setLeadFinalStatus(v)
                        }
                      }}
                      onDone={(decision) => {
                        if (decision === 'draft') {
                          void reloadDetail()
                          return
                        }
                        onDone()
                        onClose()
                      }}
                    />
                  </div>
                ) : isLeadOwnerConfirm ? (
                  <div className="px-5 py-3 space-y-3">
                    <LeadOwnerConfirmActions
                      leadId={detail.biz_id!}
                      taskId={effectiveTaskId!}
                      opinion={opinion}
                      onDone={() => {
                        onDone()
                        onClose()
                      }}
                    />
                    <Button
                      size="small"
                      type="link"
                      className="!px-0"
                      onClick={() => setMoreMode((m) => (m === 'transfer' ? null : 'transfer'))}
                    >
                      {moreMode === 'transfer' ? '收起转交' : '转交他人处理'}
                    </Button>
                  </div>
                ) : isReviseTask ? (
                  <div className="px-5 py-3 flex flex-wrap items-center gap-2">
                    <Button
                      icon={<SaveOutlined />}
                      loading={busy}
                      onClick={() => act('save')}
                    >
                      暂存
                    </Button>
                    <Button
                      type="primary"
                      icon={<CheckCircleOutlined />}
                      loading={busy}
                      onClick={() => act('resubmit')}
                    >
                      保存并重新提交
                    </Button>
                    <Button
                      danger
                      icon={<StopOutlined />}
                      loading={busy}
                      onClick={handleEndProcess}
                    >
                      手动结束
                    </Button>
                    <Text type="secondary" className="text-xs">
                      修改后重新提交，或结束流程以关闭待办
                    </Text>
                  </div>
                ) : (
                  <div className="px-5 py-3 flex flex-wrap items-center gap-2">
                    {canSaveDraft && (
                      <Button
                        icon={<SaveOutlined />}
                        loading={busy}
                        onClick={() => act('save')}
                      >
                        暂存
                      </Button>
                    )}
                    {nodeActs.submit && (
                      <Button
                        type="primary"
                        icon={<CheckCircleOutlined />}
                        loading={busy}
                        onClick={() => act('approve')}
                      >
                        {approveAndPrint ? '通过并打印' : '通过'}
                      </Button>
                    )}
                    {nodeActs.return && (
                      <Button
                        loading={busy}
                        icon={<RollbackOutlined />}
                        onClick={() => {
                          if (!(detail.approval_nodes?.length)) {
                            message.info('当前流程无可退回节点')
                            return
                          }
                          setMoreMode((m) => (m === 'return' ? null : 'return'))
                        }}
                        disabled={!(detail.approval_nodes?.length)}
                      >
                        退回
                      </Button>
                    )}
                    {nodeActs.transfer && (
                      <Button
                        loading={busy}
                        icon={<SwapOutlined />}
                        onClick={() => setMoreMode((m) => (m === 'transfer' ? null : 'transfer'))}
                      >
                        转交
                      </Button>
                    )}
                    {nodeActs.reject && (
                      <Button
                        danger
                        icon={<CloseCircleOutlined />}
                        loading={busy}
                        onClick={() => act('reject')}
                        title="驳回后发起人可修改并重新提交"
                      >
                        驳回
                      </Button>
                    )}
                  </div>
                )}
                {!isLeadIntel && !isReviseTask && moreMode && (
                  <div className="px-5 pb-3 space-y-2 border-t border-dashed border-slate-100 pt-3">
                    {moreMode === 'transfer' && (
                      <Space wrap align="start">
                        <div style={{ width: 320 }}>
                          <PersonField
                            multi
                            value={transferTo}
                            onChange={setTransferTo}
                            placeholder="选择转交人员（可多选）"
                          />
                        </div>
                        <Button type="primary" ghost icon={<SwapOutlined />} loading={busy} onClick={() => act('transfer')}>
                          确认转交
                        </Button>
                      </Space>
                    )}
                    {moreMode === 'return' && (detail.approval_nodes?.length ?? 0) > 0 && (
                      <Space wrap>
                        <Select
                          style={{ width: 220 }}
                          placeholder="退回到审批节点"
                          value={returnTo}
                          onChange={setReturnTo}
                          allowClear
                          options={(detail.approval_nodes || []).map((n) => ({ label: n.name, value: n.id }))}
                        />
                        <Button type="primary" ghost icon={<RollbackOutlined />} loading={busy} onClick={() => act('return')}>
                          确认退回
                        </Button>
                      </Space>
                    )}
                    <Button type="link" size="small" className="!px-0" onClick={() => setMoreMode(null)}>
                      收起
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 右侧/下方：流程动态（始终展示，避免 hidden md:block 在窄屏/缩放时整栏消失） */}
          <div className="w-full lg:w-[320px] shrink-0 flex flex-col min-h-[280px] lg:min-h-0 lg:self-stretch border-t lg:border-t-0 lg:border-l border-slate-200 overflow-hidden bg-slate-50">
            <WfFlowDynamics
              steps={detail.flow_steps || []}
              comments={detail.comments || []}
              tab={sideTab}
              onTabChange={setSideTab}
              onSubmitComment={submitComment}
              commenting={commenting}
              dataLog={dataLogFromWfDetail({ ...detail, form_fields: fields })}
            />
          </div>
        </div>
      )}
      <WfActivateFlowModal
        open={activateOpen}
        instanceId={detail?.id || instanceId}
        nodes={detail?.activate_nodes}
        onClose={() => setActivateOpen(false)}
        onDone={() => {
          void reloadDetail()
          onDone()
        }}
      />
    </Drawer>
  )
}

export function useWfProcessDrawer(reload: () => void) {
  const [open, setOpen] = useState(false)
  const [taskId, setTaskId] = useState<string | null>(null)
  const [instanceId, setInstanceId] = useState<string | null>(null)
  const openWith = (iid: string, tid?: string | null) => {
    setInstanceId(iid)
    setTaskId(tid || null)
    setOpen(true)
  }
  const node = (
    <WfProcessDrawer
      open={open}
      taskId={taskId}
      instanceId={instanceId}
      onClose={() => setOpen(false)}
      onDone={reload}
    />
  )
  return { openWith, node }
}
