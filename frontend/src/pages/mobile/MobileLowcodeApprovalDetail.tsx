// 移动端 → 扩展平台审批详情: 表单/业务明细(只读) + 流程轨迹 + 处理(通过/退回/转交/驳回)。
// 线索审核走情报四态表单，不提供通用通过/驳回。
import { useEffect, useState } from 'react'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { Input, Select, message } from 'antd'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { workflowApi } from '@/api/lowcodeWorkflow'
import { lowcodeApi } from '@/api/lowcode'
import type { WfInstanceDetail, FieldDefinition } from '@/types/lowcode'
import FormRenderer from '@/components/lowcode/FormRenderer'
import ApproveFieldForm, { missingRequiredFields } from '@/components/lowcode/ApproveFieldForm'
import LeadIntelReviewForm from '@/components/lead/LeadIntelReviewForm'
import LeadOwnerConfirmActions from '@/components/lead/LeadOwnerConfirmActions'
import PersonField from '@/components/lowcode/fields/PersonField'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import AttachmentPanel from '@/components/AttachmentPanel'
import ContractAttachmentSlots from '@/components/ContractAttachmentSlots'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'
import { applyApproveFieldDefaults } from '@/utils/lowcodeFormDefaults'
import { canPrintDrawingDocument, isDrawingApproveAndPrintNode, printSchemeInstance } from '@/pages/drawing/schemePrint'
import {
  defaultProdCardPrintMode,
  isProdCardApproveAndPrintNode,
  isProdCardSupplementForm,
  printProdCardInstance,
  type ProdCardPrintMode,
} from '@/pages/drawing/prodCardPrint'
import { isLeadOwnerConfirmNode } from '@/utils/leadWorkflow'
import {
  isReviseWorkflowTask,
  resolveWorkflowBizPath,
  workflowDocOpenLabel,
} from '@/utils/workflowBizPath'

export default function MobileLowcodeApprovalDetail() {
  usePageTitle('审批详情')
  const { id = '' } = useParams()
  const [sp] = useSearchParams()
  const taskFromQuery = sp.get('task')
  const nav = useNavigate()
  const [detail, setDetail] = useState<WfInstanceDetail | null>(null)
  const [fields, setFields] = useState<FieldDefinition[]>([])
  const [formData, setFormData] = useState<Record<string, unknown>>({})
  const [opinion, setOpinion] = useState('')
  const [fieldUpdates, setFieldUpdates] = useState<Record<string, unknown>>({})
  const [fieldHighlight, setFieldHighlight] = useState(false)
  const [transferTo, setTransferTo] = useState<unknown>(undefined)
  const [returnTo, setReturnTo] = useState<string | undefined>(undefined)
  const [moreMode, setMoreMode] = useState<'transfer' | 'return' | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [sideTab, setSideTab] = useState('flow')
  const [commenting, setCommenting] = useState(false)

  const load = async (taskHint?: string | null) => {
    const d = await workflowApi.instance(id, taskHint ? { task_id: taskHint } : undefined)
    setDetail(d.data)
    let nextFields: FieldDefinition[] = fields
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
      } catch { /* 无 form_data:view 且非审批相关人时忽略 */ }
    }
    const ct = d.data.current_task
    setFieldUpdates(applyApproveFieldDefaults({ ...(ct?.field_values || {}) }, {
      fieldIds: (ct?.field_perms || []).map((p) => p.field),
      formFields: nextFields,
      fieldMeta: ct?.field_meta,
    }))
    return d.data
  }

  useEffect(() => {
    (async () => {
      try {
        await load(taskFromQuery)
      } catch { message.error('加载失败') } finally { setLoading(false) }
    })()
  }, [id, taskFromQuery])

  // 仅当后端确认「当前登录人仍有待办」才可操作；URL 里的 task 只作加载提示，
  // 不能单独决定 canAct（已办深链会带上已完成的 task_id，流程若仍 running 会误露出操作区）。
  const effectiveTaskId = detail?.current_task?.task_id || null
  const isReviseTask = detail?.current_task?.task_kind === 'revise'
    || detail?.current_task?.node_type === 'revise'
  const canAct = !!effectiveTaskId && (detail?.status === 'running' || isReviseTask)
  const isLeadOwnerConfirm = detail?.biz_type === 'lead' && isLeadOwnerConfirmNode(
    detail?.current_task?.node_name,
    detail?.current_task?.node_id,
  )
  const isLeadIntel = detail?.biz_type === 'lead' && canAct && !!detail?.biz_id && !!effectiveTaskId
    && !isReviseTask && !isLeadOwnerConfirm

  // 线索修订：跳到申报编辑页（与第一次报项目同体验）
  useEffect(() => {
    if (!detail) return
    const ct = detail.current_task
    if (detail && ct?.task_id && isReviseWorkflowTask({
      taskKind: ct.task_kind, nodeType: ct.node_type, nodeName: ct.node_name,
    })) {
      const path = resolveWorkflowBizPath({
        bizType: detail.biz_type,
        bizId: detail.biz_id,
        bizRefId: detail.biz_ref_id,
        formInstanceId: detail.form_instance_id,
        formCode: detail.form_code,
        taskKind: ct.task_kind,
        nodeType: ct.node_type,
        nodeName: ct.node_name,
        taskId: ct.task_id,
        mobile: true,
      })
      if (path) nav(path, { replace: true })
    }
  }, [detail, nav])
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
    mobile: true,
  }) : null
  const docOpenLabel = workflowDocOpenLabel({
    isRevise: isReviseTask,
    bizType: detail?.biz_type,
    formCode: detail?.form_code,
  })
  const bizEntries = detail?.biz_detail ? Object.entries(detail.biz_detail) : []

  const act = async (action: string) => {
    if (!effectiveTaskId) return
    if (action === 'transfer') {
      const ids = Array.isArray(transferTo)
        ? transferTo.filter(Boolean)
        : (transferTo ? [transferTo] : [])
      if (!ids.length) {
        message.error('请选择转交接收人'); return
      }
    }
    if (action === 'return' && !returnTo) {
      message.error('请选择退回的目标节点'); return
    }
    const ct = detail?.current_task
    if (action === 'approve' && ct && !isReviseTask) {
      if (ct.opinion_required && !opinion.trim()) {
        message.error('请填写审批意见'); return
      }
      const miss = missingRequiredFields(ct.field_perms, fieldUpdates, {
        rules: detail?.form_rules,
        formFields: fields,
        formData,
        fieldMeta: ct.field_meta,
      })
      if (miss.length) {
        setFieldHighlight(true)
        const labels = miss.map((fid) => ct.field_meta?.find((m) => m.id === fid)?.label || fid)
        message.error(`请填写必填项: ${labels.join('、')}`); return
      }
    }
    setBusy(true)
    try {
      if (isReviseTask && (action === 'approve' || action === 'resubmit')) {
        if (detail?.form_instance_id) {
          const nextData = { ...formData, ...fieldUpdates }
          await lowcodeApi.updateInstance(detail.form_instance_id, { form_data: nextData })
        }
        await workflowApi.act(effectiveTaskId, { action: 'resubmit', opinion: opinion.trim() || undefined })
        message.success('已重新提交'); nav('/m/approvals')
        return
      }
      const updates = (ct?.field_perms || []).length
        ? Object.fromEntries((ct!.field_perms || []).map((p) => [p.field, fieldUpdates[p.field]]))
        : undefined
      const canPrintSchemeDoc = canPrintDrawingDocument(fields, formData, detail?.process_name)
      const canPrintProd = isProdCardSupplementForm(fields, formData, detail?.process_name)
      const shouldPrintAfterApprove = action === 'approve'
        && (
          (canPrintSchemeDoc && isDrawingApproveAndPrintNode(ct?.node_name))
          || (canPrintProd && isProdCardApproveAndPrintNode(ct?.node_name))
        )
      const mergedForm = { ...formData, ...fieldUpdates }
      await workflowApi.act(effectiveTaskId, {
        action,
        opinion: opinion.trim() || undefined,
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
          if (canPrintProd) {
            await printProdCardInstance({
              formData: mergedForm,
              fieldDefinitions: fields,
              businessNo: detail?.business_no,
              flowSteps: detail?.flow_steps,
              mode: defaultProdCardPrintMode(mergedForm),
              injectApproval: inject,
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
        nav('/m/approvals')
        return
      }
      message.success('已处理'); nav('/m/approvals')
    } catch { message.error('处理失败') } finally { setBusy(false) }
  }

  const submitComment = async (content: string) => {
    setCommenting(true)
    try {
      await workflowApi.comment(id, content)
      message.success('评论已发表')
      await load(taskFromQuery)
      setSideTab('comments')
    } catch {
      message.error('评论失败')
    } finally {
      setCommenting(false)
    }
  }

  if (loading) return <div className="flex items-center justify-center h-64"><MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 32 }} /></div>
  if (!detail) return null
  const st = PSTATUS[detail.status] || { cls: 'bg-slate-100 text-slate-500', text: detail.status }
  const canPrintScheme = canPrintDrawingDocument(fields, formData, detail.process_name)
  const canPrintProdCard = isProdCardSupplementForm(fields, formData, detail.process_name)
  const approveAndPrint = canAct && (
    (canPrintScheme && isDrawingApproveAndPrintNode(detail.current_task?.node_name))
    || (canPrintProdCard && isProdCardApproveAndPrintNode(detail.current_task?.node_name))
  )

  const handlePrintScheme = async (prodMode?: ProdCardPrintMode) => {
    try {
      const ct = detail.current_task
      const mergedForm = { ...formData, ...fieldUpdates }
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
          businessNo: detail.business_no,
          flowSteps: detail.flow_steps,
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
        businessNo: detail.business_no,
        flowSteps: detail.flow_steps,
        injectApproval: inject,
      })
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '打印失败')
    }
  }

  return (
    <div className={canAct ? 'pb-28' : ''}>
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0"><MobileIcon name="arrow_back_ios" /></button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">审批详情</h2>
        <div className="w-10" />
      </div>

      <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
        <div className="flex items-center justify-between gap-2">
          <h4 className="text-base font-bold text-slate-900 truncate">{detail.title || '(无标题)'}</h4>
          <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${st.cls}`}>{st.text}</span>
        </div>
        {detail.current_task?.node_name && (
          <div className="text-sm text-slate-500 mt-2">
            {isReviseTask ? '请修改后重新提交' : `当前节点：${detail.current_task.node_name}`}
          </div>
        )}
        {(canPrintScheme || canPrintProdCard || docPath) && (
          <div className="mt-3 flex gap-2 flex-wrap">
            {canPrintScheme && (
              <button
                type="button"
                onClick={() => { void handlePrintScheme() }}
                className="flex-1 h-10 rounded-lg bg-slate-50 text-primary text-sm font-bold border border-slate-100"
              >
                打印
              </button>
            )}
            {canPrintProdCard && (
              <>
                <button
                  type="button"
                  onClick={() => { void handlePrintScheme('notice') }}
                  className="flex-1 min-w-[40%] h-10 rounded-lg bg-slate-50 text-primary text-sm font-bold border border-slate-100"
                >
                  生产通知单
                </button>
                <button
                  type="button"
                  onClick={() => { void handlePrintScheme('supplement') }}
                  className="flex-1 min-w-[40%] h-10 rounded-lg bg-slate-50 text-primary text-sm font-bold border border-slate-100"
                >
                  生产补充卡
                </button>
              </>
            )}
            {docPath && (
              <button
                type="button"
                onClick={() => nav(docPath)}
                className="flex-1 h-10 rounded-lg bg-slate-50 text-primary text-sm font-bold border border-slate-100"
              >
                {docOpenLabel}
              </button>
            )}
          </div>
        )}
      </div>

      {fields.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
          <div className="text-sm font-bold text-slate-500 mb-2">
            {isReviseTask ? '请修改表单后重新提交' : '表单内容'}
          </div>
          <FormRenderer
            fields={fields}
            mode={isReviseTask ? 'edit' : 'readonly'}
            value={isReviseTask ? { ...formData, ...fieldUpdates } : formData}
            onChange={isReviseTask ? ((v) => {
              setFormData(v)
              setFieldUpdates(v)
            }) : undefined}
            rules={detail.form_rules || []}
            applyFieldPerms={false}
            detailLayout="cards"
          />
        </div>
      )}

      {!fields.length && bizEntries.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
          <div className="text-sm font-bold text-slate-500 mb-2">
            {detail.biz_type === 'lead'
              ? '申报信息（创建时填写）'
              : detail.biz_type === 'customer'
                ? '客户信息'
                : '业务信息'}
          </div>
          <div className="space-y-2">
            {bizEntries.map(([k, v]) => (
              <div key={k} className="flex gap-3 text-sm">
                <span className="shrink-0 w-28 text-slate-500">{k}</span>
                <span className="text-slate-800 font-medium whitespace-pre-wrap break-all">{String(v)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {detail.biz_type === 'lead' && detail.biz_id && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
          <AttachmentPanel bizType="lead" bizId={detail.biz_id} title="附件" compact readonly />
        </div>
      )}
      {detail.biz_type === 'customer' && detail.biz_id && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
          <AttachmentPanel bizType="customer" bizId={detail.biz_id} title="附件" compact readonly />
        </div>
      )}
      {detail.biz_type === 'contract_version' && (detail.biz_ref_id || detail.biz_id) && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3 space-y-3">
          <div className="text-sm font-bold text-slate-500">合同附件（发起人上传）</div>
          <ContractAttachmentSlots
            slot="contract_files"
            contractId={detail.biz_ref_id || undefined}
            readonly
          />
          <ContractAttachmentSlots
            slot="accept_files"
            contractId={detail.biz_ref_id || undefined}
            readonly
          />
        </div>
      )}
      {detail.biz_type === 'contract_review' && detail.biz_id && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3 space-y-3">
          <AttachmentPanel bizType="contract_review" bizId={detail.biz_id} title="附件（合同）" compact readonly />
          <AttachmentPanel
            bizType="contract_review_image"
            bizId={detail.biz_id}
            title="图片"
            accept="image/*"
            compact
            readonly
          />
          <AttachmentPanel bizType="contract_review_cost" bizId={detail.biz_id} title="成本附件" compact readonly />
          <AttachmentPanel
            bizType="contract_review_feedback"
            bizId={detail.biz_id}
            title="反馈附件"
            compact
            readonly
          />
          <AttachmentPanel
            bizType="contract_review_feedback_image"
            bizId={detail.biz_id}
            title="反馈图片"
            accept="image/*"
            compact
            readonly
          />
        </div>
      )}
      <div className={canAct ? 'mb-3' : ''}>
        <WfFlowDynamics
          variant="page"
          steps={detail.flow_steps || []}
          comments={detail.comments || []}
          tab={sideTab}
          onTabChange={setSideTab}
          onSubmitComment={submitComment}
          commenting={commenting}
        />
      </div>

      {isLeadIntel && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3 max-h-[55vh] overflow-y-auto z-30" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
          {detail.current_task && (detail.current_task.field_perms?.length ?? 0) > 0 && (
            <div className="mb-3">
              <div className="text-sm font-bold text-slate-700 mb-2">
                本节点填写（{detail.current_task.node_name || '信息情报部审批'}）
              </div>
              <ApproveFieldForm
                currentTask={{
                  ...detail.current_task,
                  field_perms: (detail.current_task.field_perms || []).filter(
                    (p) => p.field !== 'review_opinion',
                  ),
                }}
                values={fieldUpdates}
                onChange={setFieldUpdates}
                highlightMissing={fieldHighlight}
                rules={detail.form_rules || []}
                formData={formData}
                formFields={fields}
              />
            </div>
          )}
          <div className="text-sm font-bold text-slate-700 mb-1">操作意见</div>
          <Input.TextArea
            rows={2}
            placeholder="选填"
            value={opinion}
            onChange={(e) => setOpinion(e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <LeadIntelReviewForm
            compact
            actionsOnly
            leadId={detail.biz_id!}
            taskId={effectiveTaskId!}
            fieldValues={fieldUpdates}
            opinion={opinion}
            onDone={(decision) => {
              if (decision === 'draft') {
                void load(effectiveTaskId)
                return
              }
              nav('/m/approvals')
            }}
          />
        </div>
      )}

      {canAct && isLeadOwnerConfirm && detail.biz_id && effectiveTaskId && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3 max-h-[60vh] overflow-y-auto z-30" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
          <div className="text-sm font-bold text-slate-700 mb-1">操作意见</div>
          <Input.TextArea
            rows={2}
            placeholder="选填"
            value={opinion}
            onChange={(e) => setOpinion(e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <LeadOwnerConfirmActions
            compact
            leadId={detail.biz_id}
            taskId={effectiveTaskId}
            opinion={opinion}
            onDone={() => nav('/m/approvals')}
          />
        </div>
      )}

      {canAct && !isLeadIntel && !isLeadOwnerConfirm && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3 max-h-[60vh] overflow-y-auto z-30" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
          {isReviseTask ? (
            <>
              <div className="text-sm text-slate-500 mb-2">修改内容后重新提交，或手动结束以关闭待办</div>
              <button
                onClick={() => act('resubmit')}
                disabled={busy}
                className="w-full h-11 rounded-xl bg-primary text-white font-bold border-0 disabled:opacity-60 mb-2"
              >
                保存并重新提交
              </button>
              <button
                onClick={() => {
                  if (!detail?.id) return
                  if (!window.confirm('确认手动结束？结束后将取消修订待办。')) return
                  setBusy(true)
                  workflowApi.endProcess(detail.id)
                    .then(() => {
                      message.success('已手动结束流程')
                      nav('/m/approvals')
                    })
                    .catch((err: unknown) => {
                      const msg = err instanceof Error ? err.message : ''
                      if (msg) message.warning(msg)
                    })
                    .finally(() => setBusy(false))
                }}
                disabled={busy}
                className="w-full h-11 rounded-xl bg-white text-rose-500 font-bold border border-rose-200 disabled:opacity-60"
              >
                手动结束
              </button>
            </>
          ) : (
            <>
          {detail.current_task && (detail.current_task.field_perms?.length ?? 0) > 0 && (
            <ApproveFieldForm
              currentTask={detail.current_task}
              values={fieldUpdates}
              onChange={setFieldUpdates}
              highlightMissing={fieldHighlight}
              rules={detail.form_rules || []}
              formData={formData}
              formFields={fields}
            />
          )}
          <Input.TextArea
            rows={2}
            placeholder={detail.current_task?.opinion_required ? '审批意见(必填)' : '审批意见(可选)'}
            value={opinion}
            onChange={(e) => setOpinion(e.target.value)}
            style={{ marginBottom: 8 }}
          />
          <div className="grid grid-cols-2 gap-2">
            <button onClick={() => act('approve')} disabled={busy} className="h-11 rounded-xl bg-primary text-white font-bold border-0 disabled:opacity-60">
              {approveAndPrint ? '通过并打印' : '通过'}
            </button>
            <button
              onClick={() => {
                if (!(detail.approval_nodes?.length)) {
                  message.info('当前流程无可退回节点')
                  return
                }
                setMoreMode((m) => (m === 'return' ? null : 'return'))
              }}
              disabled={busy || !(detail.approval_nodes?.length)}
              className="h-11 rounded-xl bg-slate-100 text-slate-700 font-bold border-0 disabled:opacity-60"
            >
              退回
            </button>
            <button onClick={() => setMoreMode((m) => (m === 'transfer' ? null : 'transfer'))} disabled={busy} className="h-11 rounded-xl bg-slate-100 text-slate-700 font-bold border-0 disabled:opacity-60">转交</button>
            <button onClick={() => act('reject')} disabled={busy} className="h-11 rounded-xl bg-red-50 text-red-600 font-bold border-0 disabled:opacity-60">驳回</button>
          </div>
          {moreMode && (
            <div className="mt-3 pt-3 border-t border-dashed border-slate-200 space-y-3">
              {moreMode === 'transfer' && (
                <div>
                  <div className="text-sm font-bold text-slate-600 mb-1">转交接收人（可多选）</div>
                  <PersonField multi value={transferTo} onChange={setTransferTo} placeholder="选择转交人员（可多选）" />
                  <button
                    type="button"
                    onClick={() => act('transfer')}
                    disabled={busy}
                    className="mt-2 w-full h-10 rounded-lg bg-primary/10 text-primary font-bold border-0 disabled:opacity-60"
                  >
                    确认转交
                  </button>
                </div>
              )}
              {moreMode === 'return' && (detail.approval_nodes?.length ?? 0) > 0 && (
                <div>
                  <div className="text-sm font-bold text-slate-600 mb-1">退回到节点</div>
                  <Select
                    className="w-full"
                    placeholder="选择审批节点"
                    value={returnTo}
                    onChange={setReturnTo}
                    allowClear
                    options={(detail.approval_nodes || []).map((n) => ({ label: n.name, value: n.id }))}
                  />
                  <button
                    type="button"
                    onClick={() => act('return')}
                    disabled={busy}
                    className="mt-2 w-full h-10 rounded-lg bg-primary/10 text-primary font-bold border-0 disabled:opacity-60"
                  >
                    确认退回
                  </button>
                </div>
              )}
              <button type="button" onClick={() => setMoreMode(null)} className="text-sm text-slate-500 bg-transparent border-0 p-0">
                收起
              </button>
            </div>
          )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
