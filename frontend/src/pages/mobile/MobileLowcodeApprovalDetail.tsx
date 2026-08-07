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
import PersonField from '@/components/lowcode/fields/PersonField'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'

function bizEntityPath(bizType?: string | null, bizId?: string | null, bizRefId?: string | null): string | null {
  if (!bizType || !bizId) return null
  const map: Record<string, string> = {
    lead: `/m/leads/${bizId}`,
    order: `/m/orders/${bizId}`,
    service_ticket: `/m/service-tickets/${bizId}`,
    contract_review: `/m/contract-reviews/${bizId}`,
  }
  if (map[bizType]) return map[bizType]
  if (bizType === 'contract_version' && bizRefId) return `/m/contracts/${bizRefId}`
  return null
}

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
  const [moreOpen, setMoreOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [sideTab, setSideTab] = useState('flow')
  const [commenting, setCommenting] = useState(false)

  const load = async (taskHint?: string | null) => {
    const d = await workflowApi.instance(id, taskHint ? { task_id: taskHint } : undefined)
    setDetail(d.data)
    setFieldUpdates({ ...(d.data.current_task?.field_values || {}) })
    if (d.data.form_fields?.length) {
      setFields(d.data.form_fields)
      setFormData(d.data.form_data || {})
    } else if (d.data.form_instance_id) {
      try {
        const fi = await lowcodeApi.getInstance(d.data.form_instance_id)
        setFields(fi.data.field_definitions)
        setFormData(fi.data.form_data)
      } catch { /* 无 form_data:view 且非审批相关人时忽略 */ }
    }
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
  const canAct = !!effectiveTaskId && detail?.status === 'running'
  const isLeadIntel = detail?.biz_type === 'lead' && canAct && !!detail?.biz_id && !!effectiveTaskId
  const bizPath = detail ? bizEntityPath(detail.biz_type, detail.biz_id, detail.biz_ref_id) : null
  const bizEntries = detail?.biz_detail ? Object.entries(detail.biz_detail) : []

  const act = async (action: string) => {
    if (!effectiveTaskId) return
    if (action === 'transfer' && !transferTo) {
      message.error('请选择转交接收人'); return
    }
    if (action === 'return' && !returnTo) {
      message.error('请选择退回的目标节点'); return
    }
    const ct = detail?.current_task
    if (action === 'approve' && ct) {
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
      const updates = (ct?.field_perms || []).length
        ? Object.fromEntries((ct!.field_perms || []).map((p) => [p.field, fieldUpdates[p.field]]))
        : undefined
      await workflowApi.act(effectiveTaskId, {
        action,
        opinion: opinion.trim() || undefined,
        transfer_to: action === 'transfer'
          ? (Array.isArray(transferTo) ? transferTo[0] : transferTo) as string
          : undefined,
        to_node_id: action === 'return' ? returnTo : undefined,
        field_updates: action === 'approve' ? updates : undefined,
      })
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
          <div className="text-sm text-slate-500 mt-2">当前节点：{detail.current_task.node_name}</div>
        )}
        {bizPath && (
          <button
            type="button"
            onClick={() => nav(bizPath)}
            className="mt-3 w-full h-10 rounded-lg bg-slate-50 text-primary text-sm font-bold border border-slate-100"
          >
            查看完整单据
          </button>
        )}
      </div>

      {fields.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
          <div className="text-sm font-bold text-slate-500 mb-2">表单内容</div>
          <FormRenderer
            fields={fields}
            mode="readonly"
            value={formData}
            rules={detail.form_rules || []}
            applyFieldPerms={false}
            detailLayout="cards"
          />
        </div>
      )}

      {!fields.length && bizEntries.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 p-4 mb-3">
          <div className="text-sm font-bold text-slate-500 mb-2">
            {detail.biz_type === 'lead' ? '线索信息' : '业务信息'}
          </div>
          <div className="space-y-2">
            {bizEntries.map(([k, v]) => (
              <div key={k} className="flex gap-3 text-sm">
                <span className="shrink-0 w-20 text-slate-500">{k}</span>
                <span className="text-slate-800 font-medium whitespace-pre-wrap break-all">{String(v)}</span>
              </div>
            ))}
          </div>
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
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3 max-h-[55vh] overflow-y-auto" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
          <div className="text-sm font-bold text-slate-700 mb-2">情报审批</div>
          <LeadIntelReviewForm
            compact
            leadId={detail.biz_id!}
            taskId={effectiveTaskId!}
            initialNewness={
              detail.biz_detail?.['客户类型'] === '新' ? 'new'
                : detail.biz_detail?.['客户类型'] === '老' ? 'old'
                  : undefined
            }
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

      {canAct && !isLeadIntel && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3 max-h-[60vh] overflow-y-auto z-30" style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}>
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
            <button onClick={() => act('approve')} disabled={busy} className="h-11 rounded-xl bg-primary text-white font-bold border-0 disabled:opacity-60">通过</button>
            <button
              onClick={() => {
                if (!(detail.approval_nodes?.length)) {
                  message.info('当前流程无可退回节点')
                  return
                }
                setMoreOpen(true)
              }}
              disabled={busy || !(detail.approval_nodes?.length)}
              className="h-11 rounded-xl bg-slate-100 text-slate-700 font-bold border-0 disabled:opacity-60"
            >
              退回
            </button>
            <button onClick={() => setMoreOpen(true)} disabled={busy} className="h-11 rounded-xl bg-slate-100 text-slate-700 font-bold border-0 disabled:opacity-60">转交</button>
            <button onClick={() => act('reject')} disabled={busy} className="h-11 rounded-xl bg-red-50 text-red-600 font-bold border-0 disabled:opacity-60">驳回</button>
          </div>
          {moreOpen && (
            <div className="mt-3 pt-3 border-t border-dashed border-slate-200 space-y-3">
              <div>
                <div className="text-sm font-bold text-slate-600 mb-1">转交接收人</div>
                <PersonField value={transferTo} onChange={setTransferTo} placeholder="选择转交人员" />
                <button
                  type="button"
                  onClick={() => act('transfer')}
                  disabled={busy}
                  className="mt-2 w-full h-10 rounded-lg bg-primary/10 text-primary font-bold border-0 disabled:opacity-60"
                >
                  确认转交
                </button>
              </div>
              {(detail.approval_nodes?.length ?? 0) > 0 && (
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
              <button type="button" onClick={() => setMoreOpen(false)} className="text-sm text-slate-500 bg-transparent border-0 p-0">
                收起
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
