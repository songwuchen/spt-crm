import { useState } from 'react'
import { Button, Checkbox, Space, message } from 'antd'
import { leadApi } from '@/api/lead'
import { workflowApi } from '@/api/lowcodeWorkflow'

type DoneKind = 'convert' | 'skip'

type Props = {
  leadId: string
  taskId: string
  /** 审批抽屉里的操作意见，可为空 */
  opinion?: string
  compact?: boolean
  onDone?: (kind: DoneKind) => void
}

/**
 * 线索流程「业务员确认是否转商机」专用操作区。
 * - 确认转商机：通过流程 + 创建商机（未匹配客户时系统自动建档）
 * - 暂不转商机：通过流程结束，保留情报收录，不转化（勿用 reject，以免线索被打成驳回）
 */
export default function LeadOwnerConfirmActions({
  leadId,
  taskId,
  opinion,
  compact,
  onDone,
}: Props) {
  const [createOpp, setCreateOpp] = useState(true)
  const [busy, setBusy] = useState(false)

  const run = async (kind: DoneKind) => {
    setBusy(true)
    try {
      const op = (opinion || '').trim()
        || (kind === 'convert' ? '确认转商机' : '暂不转商机')

      // 先转化再过流程：避免「流程已完成但商机未建」的半成功态
      if (kind === 'convert') {
        try {
          const res = await leadApi.qualify(leadId, createOpp)
          const src = res.data.customer_link_source
          const suffix = res.data.project_code
            ? src === 'auto_created'
              ? `，已自动创建客户并关联`
              : src === 'matched'
                ? `，已关联已有客户`
                : src === 'ambiguous'
                  ? `，客户重名请在商机中手工选择`
                  : ``
            : ''
          message.success(
            res.data.project_code
              ? `已转商机 ${res.data.project_code}${suffix}`
              : '线索已标记为已转化',
          )
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          if (msg?.includes('已转化')) {
            message.success(msg)
          } else {
            message.error(msg || '转化失败（请确认账号有「转化线索」权限），流程未提交')
            return
          }
        }
      }

      await workflowApi.act(taskId, { action: 'approve', opinion: op })
      if (kind !== 'convert') {
        message.success('已确认暂不转商机；线索保持收录，之后可在详情转化')
      }
      onDone?.(kind)
    } catch {
      message.error(kind === 'convert' ? '已转化，但流程确认失败，请刷新后重试流程' : '处理失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={compact ? 'space-y-2' : 'space-y-3'}>
      <div className={`rounded-lg border border-amber-200 bg-amber-50/80 ${compact ? 'px-3 py-2' : 'px-3 py-2.5'}`}>
        <div className={`font-semibold text-slate-800 ${compact ? 'text-sm' : 'text-sm'}`}>
          请明确：是否转商机
        </div>
        <div className="text-xs text-slate-500 mt-1 leading-relaxed">
          情报部已收录。需要出方案报价请选「确认转商机」；拟建/暂不报价请选「暂不转商机」（线索仍保留，可稍后转化）。
        </div>
        <div className="mt-2">
          <Checkbox checked={createOpp} onChange={(e) => setCreateOpp(e.target.checked)}>
            转商机时同时创建商机（带入需求摘要 / 预算；未匹配客户时系统自动建档）
          </Checkbox>
        </div>
      </div>
      <Space wrap size="middle">
        <Button type="primary" loading={busy} onClick={() => void run('convert')}>
          确认转商机
        </Button>
        <Button loading={busy} onClick={() => void run('skip')}>
          暂不转商机
        </Button>
      </Space>
    </div>
  )
}
