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
  compact?: boolean
  onDone: (decision: IntelDecision) => void
}

/**
 * 线索情报审批表单：新/老客户 + 项目最终状态 + 回退原因 + 操作意见。
 * 按钮：收录 / 袭击 / 回退 / 暂存。
 */
export default function LeadIntelReviewForm({
  leadId, taskId, initialNewness, initialOpinion, initialReturnReason, compact, onDone,
}: Props) {
  const [newness, setNewness] = useState<CustomerNewness | undefined>()
  const [finalStatus, setFinalStatus] = useState<'pending' | 'include' | 'return' | 'attack'>('include')
  const [returnReason, setReturnReason] = useState('')
  const [opinion, setOpinion] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (initialNewness === 'new' || initialNewness === 'old') setNewness(initialNewness)
    if (initialOpinion) setOpinion(initialOpinion)
    if (initialReturnReason) setReturnReason(initialReturnReason)
  }, [initialNewness, initialOpinion, initialReturnReason])

  const submit = async (decision: IntelDecision) => {
    if (decision !== 'draft' && !newness) {
      message.warning('请选择客户类型（新/老）')
      return
    }
    if (decision === 'return' && !returnReason.trim()) {
      message.warning('回退须填写回退原因')
      return
    }
    setLoading(true)
    try {
      await leadApi.intelReview(leadId, {
        decision,
        task_id: taskId,
        customer_newness: newness,
        return_reason: returnReason.trim() || undefined,
        opinion: opinion.trim() || undefined,
      })
      const labels: Record<IntelDecision, string> = {
        include: '已收录', attack: '已标记袭击', return: '已回退', draft: '已暂存',
      }
      message.success(labels[decision])
      onDone(decision)
    } catch {
      message.error('操作失败')
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

  return (
    <div className={compact ? 'space-y-3' : 'space-y-4'}>
      <div>
        <div className="text-sm font-medium text-slate-700 mb-2">
          <span className="text-red-500 mr-0.5">*</span>客户类型
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
