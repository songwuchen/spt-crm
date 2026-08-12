import { useState, useEffect } from 'react'
import { Button, Input, Radio, Space, message } from 'antd'
import { leadApi } from '@/api/lead'

export type IntelDecision = 'include' | 'attack' | 'return' | 'draft'
export type CustomerNewness = 'new' | 'old'

type Props = {
  leadId: string
  taskId: string
  initialNewness?: string | null
  initialOpinion?: string | null
  initialReturnReason?: string | null
  initialAssessRemark?: string | null
  compact?: boolean
  /** 嵌入审批抽屉时：标题用「本节点填写」，字段顺序对齐简道云 */
  embedded?: boolean
  onDone: (decision: IntelDecision) => void
}

/**
 * 信息情报部审批（对齐简道云评估信息）：
 * 客户类型 → 项目最终状态 → 回退原因 → 备注2 → 操作意见 → 裁定按钮
 */
export default function LeadIntelReviewForm({
  leadId, taskId, initialNewness, initialOpinion, initialReturnReason,
  initialAssessRemark, compact, embedded, onDone,
}: Props) {
  const [newness, setNewness] = useState<CustomerNewness | undefined>()
  const [finalStatus, setFinalStatus] = useState<'pending' | 'include' | 'return' | 'attack'>('include')
  const [returnReason, setReturnReason] = useState('')
  const [opinion, setOpinion] = useState('')
  const [assessRemark, setAssessRemark] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (initialNewness === 'new' || initialNewness === 'old') setNewness(initialNewness)
    else if (initialNewness === '新') setNewness('new')
    else if (initialNewness === '老') setNewness('old')
    if (initialOpinion) setOpinion(initialOpinion)
    if (initialReturnReason) setReturnReason(initialReturnReason)
    if (initialAssessRemark) setAssessRemark(initialAssessRemark)
  }, [initialNewness, initialOpinion, initialReturnReason, initialAssessRemark])

  const resolvePayload = () => ({
    customer_newness: newness,
    return_reason: returnReason.trim() || undefined,
    opinion: opinion.trim() || undefined,
    assess_remark: assessRemark.trim() || undefined,
  })

  const submit = async (decision: IntelDecision) => {
    const payload = resolvePayload()
    if (decision !== 'draft' && !payload.customer_newness) {
      message.warning('请选择客户类型（新/老）')
      return
    }
    if (decision === 'return' && !payload.return_reason) {
      message.warning('回退须填写回退原因')
      return
    }
    setLoading(true)
    try {
      await leadApi.intelReview(leadId, {
        decision,
        task_id: taskId,
        ...payload,
      })
      const labels: Record<IntelDecision, string> = {
        include: '已收录', attack: '已标记袭击', return: '已回退', draft: '已暂存',
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
    if (finalStatus === 'return') return 'return'
    if (finalStatus === 'attack') return 'attack'
    return 'include'
  }

  const primaryLabel =
    finalStatus === 'return' ? '回退'
      : finalStatus === 'attack' ? '袭击'
        : '收录'

  const gap = compact ? 'space-y-3' : 'space-y-4'

  return (
    <div className={gap}>
      {!embedded && (
        <div className="rounded-sm bg-teal-600 px-3 py-2 text-[13px] font-semibold text-white">
          评估信息（审批时填写）
        </div>
      )}

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

      <div>
        <div className="text-sm font-medium text-slate-700 mb-2">
          <span className="text-red-500 mr-0.5">*</span>项目最终状态
        </div>
        <Radio.Group
          value={finalStatus}
          onChange={(e) => setFinalStatus(e.target.value)}
          optionType="button"
          buttonStyle="solid"
          options={[
            { value: 'pending', label: '待审', disabled: true },
            { value: 'include', label: '收录' },
            { value: 'return', label: '回退' },
            { value: 'attack', label: '袭击' },
          ]}
        />
      </div>

      {finalStatus === 'return' && (
        <div>
          <div className="text-sm font-medium text-slate-700 mb-2">
            <span className="text-red-500 mr-0.5">*</span>回退原因
          </div>
          <Input.TextArea
            rows={compact ? 2 : 3}
            value={returnReason}
            onChange={(e) => setReturnReason(e.target.value)}
            placeholder="请填写回退原因"
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

      <div>
        <div className="text-sm font-medium text-slate-700 mb-2">操作意见</div>
        <Input.TextArea
          rows={compact ? 2 : 3}
          value={opinion}
          onChange={(e) => setOpinion(e.target.value)}
          placeholder="选填"
        />
      </div>

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
    </div>
  )
}
