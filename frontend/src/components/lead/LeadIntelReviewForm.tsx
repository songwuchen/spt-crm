import { useState, useEffect } from 'react'
import { Button, Input, Radio, Space, message } from 'antd'
import { leadApi } from '@/api/lead'

export type IntelDecision = 'include' | 'attack' | 'return' | 'revise' | 'draft'
export type CustomerNewness = 'new' | 'old'
export type IntelFinalStatus = 'pending' | 'include' | 'return' | 'revise' | 'attack'

type Props = {
  leadId: string
  taskId: string
  /** 申报信息 vs 180天激活（API 不同） */
  mode?: 'lead' | 'reactivation'
  initialNewness?: string | null
  initialOpinion?: string | null
  initialReturnReason?: string | null
  initialAssessRemark?: string | null
  compact?: boolean
  /**
   * 审批抽屉通用壳：字段已由 ApproveFieldForm + 底部「操作意见」承担，
   * 本组件只渲染裁定相关 UI。
   */
  actionsOnly?: boolean
  /** actionsOnly 时是否展示「项目最终状态」（可放到本节点填写区另行渲染） */
  showFinalStatus?: boolean
  finalStatus?: IntelFinalStatus
  onFinalStatusChange?: (v: IntelFinalStatus) => void
  /** actionsOnly 时与 ApproveFieldForm / 底部意见同步 */
  fieldValues?: Record<string, unknown>
  opinion?: string
  onDone: (decision: IntelDecision) => void
}

function parseNewness(v: unknown): CustomerNewness | undefined {
  if (v === 'new' || v === 'old') return v
  if (v === '新') return 'new'
  if (v === '老') return 'old'
  return undefined
}

/**
 * 信息情报部裁定。
 * - 默认：完整评估表单（详情页待办区）
 * - actionsOnly：接入通用审批抽屉（本节点字段 + 底部意见另渲染）
 */
export default function LeadIntelReviewForm({
  leadId, taskId, mode = 'lead', initialNewness, initialOpinion, initialReturnReason,
  initialAssessRemark, compact, actionsOnly, showFinalStatus = true,
  finalStatus: finalStatusProp, onFinalStatusChange,
  fieldValues, opinion: opinionProp, onDone,
}: Props) {
  const [newness, setNewness] = useState<CustomerNewness | undefined>()
  const [finalStatusInner, setFinalStatusInner] = useState<IntelFinalStatus>('include')
  const finalStatus = finalStatusProp ?? finalStatusInner
  const setFinalStatus = (v: IntelFinalStatus) => {
    onFinalStatusChange?.(v)
    if (finalStatusProp === undefined) setFinalStatusInner(v)
  }
  const [returnReason, setReturnReason] = useState('')
  const [opinion, setOpinion] = useState('')
  const [assessRemark, setAssessRemark] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const n = parseNewness(initialNewness)
    if (n) setNewness(n)
    if (initialOpinion) setOpinion(initialOpinion)
    if (initialReturnReason) setReturnReason(initialReturnReason)
    if (initialAssessRemark) setAssessRemark(initialAssessRemark)
  }, [initialNewness, initialOpinion, initialReturnReason, initialAssessRemark])

  const resolvePayload = () => {
    if (actionsOnly) {
      const fv = fieldValues || {}
      return {
        customer_newness: parseNewness(fv.customer_newness),
        return_reason: String(fv.reject_reason ?? '').trim() || undefined,
        assess_remark: String(fv.assess_remark ?? '').trim() || undefined,
        has_internal_conflict: String(fv.has_internal_conflict ?? '').trim() || undefined,
        conflict_note: String(fv.conflict_note ?? '').trim() || undefined,
        opinion: String(opinionProp ?? '').trim() || undefined,
      }
    }
    return {
      customer_newness: newness,
      return_reason: returnReason.trim() || undefined,
      assess_remark: assessRemark.trim() || undefined,
      opinion: opinion.trim() || undefined,
    }
  }

  const submit = async (decision: IntelDecision) => {
    const payload = resolvePayload()
    if (decision !== 'draft' && !payload.customer_newness) {
      message.error('请选择客户类型（新/老）')
      return
    }
    if ((decision === 'return' || decision === 'revise') && !payload.return_reason) {
      message.error(decision === 'revise' ? '请填写回退原因' : '请填写驳回原因')
      return
    }
    setLoading(true)
    try {
      const api = mode === 'reactivation' ? leadApi.reactivationIntelReview : leadApi.intelReview
      await api(leadId, {
        decision,
        task_id: taskId,
        ...payload,
      })
      const labels: Record<IntelDecision, string> = {
        include: mode === 'reactivation' ? '已收录，180天计时已重置' : '已收录',
        attack: mode === 'reactivation' ? '已标记袭击，180天计时已重置' : '已标记袭击',
        return: mode === 'reactivation' ? '已回退' : '已驳回（不可再报备）',
        revise: mode === 'reactivation' ? '已回退至内勤/业务员' : '已回退，等待申报人修改后重新提交',
        draft: '已暂存',
      }
      message.success(labels[decision])
      onDone(decision)
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || '操作失败')
    } finally {
      setLoading(false)
    }
  }

  const primaryDecision = (): IntelDecision => {
    if (finalStatus === 'return') return mode === 'reactivation' ? 'revise' : 'return'
    if (finalStatus === 'revise') return 'revise'
    if (finalStatus === 'attack') return 'attack'
    return 'include'
  }

  const primaryLabel =
    finalStatus === 'return' && mode !== 'reactivation' ? '驳回'
      : finalStatus === 'revise' || (finalStatus === 'return' && mode === 'reactivation') ? '回退'
        : finalStatus === 'attack' ? '袭击'
          : '收录'

  const statusOptions = mode === 'reactivation'
    ? [
        { value: 'include', label: '收录' },
        { value: 'revise', label: '回退' },
        { value: 'attack', label: '袭击' },
      ]
    : [
        { value: 'pending', label: '待审', disabled: true },
        { value: 'include', label: '收录' },
        { value: 'revise', label: '回退' },
        { value: 'return', label: '驳回' },
        { value: 'attack', label: '袭击' },
      ]

  const statusBlock = (
    <div>
      <div className="text-sm font-medium text-slate-700 mb-2">
        <span className="text-red-500 mr-0.5">*</span>项目最终状态
      </div>
      <Radio.Group
        value={finalStatus}
        onChange={(e) => setFinalStatus(e.target.value)}
        optionType="button"
        buttonStyle="solid"
        options={statusOptions}
      />
      {actionsOnly && finalStatus === 'return' && mode !== 'reactivation' && (
        <div className="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
          驳回后流程结束，项目不可再报备；请在上方「本节点填写」中填写驳回原因
        </div>
      )}
      {actionsOnly && finalStatus === 'revise' && (
        <div className="mt-2 text-xs text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-1.5">
          {mode === 'reactivation'
            ? '回退后将退回内勤或业务员重新处理；请在上方填写回退原因'
            : '回退后申报人可修改并重新提交审批；请在上方填写回退原因'}
        </div>
      )}
    </div>
  )

  const actionButtons = (
    <Space wrap>
      <Button
        type="primary"
        danger={finalStatus === 'return'}
        loading={loading}
        disabled={finalStatus === 'pending'}
        onClick={() => submit(primaryDecision())}
      >
        {primaryLabel}
      </Button>
      <Button loading={loading} onClick={() => submit('draft')}>暂存</Button>
    </Space>
  )

  if (actionsOnly) {
    return (
      <div className={compact ? 'space-y-3' : 'space-y-4'}>
        {showFinalStatus && statusBlock}
        {actionButtons}
      </div>
    )
  }

  return (
    <div className={compact ? 'space-y-3' : 'space-y-4'}>
      <div className="rounded-sm bg-teal-600 px-3 py-2 text-[13px] font-semibold text-white">
        评估信息（审批时填写）
      </div>

      <div>
        <div className="text-sm font-medium text-slate-700 mb-2">
          <span className="text-red-500 mr-0.5">*</span>客户类型（新/老）
        </div>
        <Radio.Group
          value={newness}
          onChange={(e) => setNewness(e.target.value)}
          optionType="button"
          buttonStyle="solid"
          options={[
            { value: 'new', label: '新' },
            { value: 'old', label: '老' },
          ]}
        />
      </div>

      {statusBlock}

      {(finalStatus === 'return' || finalStatus === 'revise') && (
        <div>
          <div className="text-sm font-medium text-slate-700 mb-2">
            <span className="text-red-500 mr-0.5">*</span>
            {finalStatus === 'revise' ? '回退原因' : '驳回原因'}
          </div>
          <Input.TextArea
            rows={compact ? 2 : 3}
            value={returnReason}
            onChange={(e) => setReturnReason(e.target.value)}
            placeholder={
              finalStatus === 'revise'
                ? '请填写回退原因（申报人修改时可见）'
                : '请填写驳回原因（驳回后不可再报备/跟进）'
            }
          />
        </div>
      )}

      <div>
        <div className="text-sm font-medium text-slate-700 mb-2">备注2</div>
        <Input.TextArea
          rows={compact ? 2 : 3}
          value={assessRemark}
          onChange={(e) => setAssessRemark(e.target.value)}
          placeholder="评估备注"
        />
      </div>

      {!actionsOnly && (
        <div>
          <div className="text-sm font-medium text-slate-700 mb-2">操作意见</div>
          <Input.TextArea
            rows={compact ? 2 : 3}
            value={opinion}
            onChange={(e) => setOpinion(e.target.value)}
            placeholder="可选"
          />
        </div>
      )}

      {actionButtons}
    </div>
  )
}
