/** 表单详情系统信息区：对齐简道云底部「提交人 / 提交时间 / …」 */
import type { ReactNode } from 'react'
import { Tag } from 'antd'
import type { WfFlowStep } from '@/types/lowcode'

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  submitted: { color: 'blue', text: '已提交' },
  running: { color: 'processing', text: '进行中' },
  completed: { color: 'success', text: '已通过' },
  rejected: { color: 'error', text: '已驳回' },
  withdrawn: { color: 'default', text: '已撤回' },
}

function formatDt(v?: string | null): string {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v).replace('T', ' ').slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function MetaCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex gap-2 min-w-0 py-1.5">
      <span className="shrink-0 text-slate-500 w-[72px]">{label}</span>
      <span className="min-w-0 text-slate-800 break-all">{children}</span>
    </div>
  )
}

export default function FormInstanceSystemMeta({
  initiatorName,
  createdAt,
  updatedAt,
  status,
  flowSteps,
}: {
  initiatorName?: string | null
  createdAt?: string | null
  updatedAt?: string | null
  status?: string | null
  flowSteps?: WfFlowStep[] | null
}) {
  const statusTag = status
    ? (STATUS_TAG[status] || { color: 'default', text: status })
    : null
  const currentSteps = (flowSteps || []).filter((s) => s.is_current)
  const currentNode = currentSteps.map((s) => s.node_name).filter(Boolean).join('、') || '—'
  const assignees = [
    ...new Set(
      currentSteps.flatMap((s) => (s.assignees || []).map((a) => a.name).filter(Boolean)),
    ),
  ]
  const currentAssignees = assignees.join('、') || '—'
  const hasFlow = (flowSteps || []).length > 0

  return (
    <div className="mt-6 pt-4 border-t border-slate-200 text-sm">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-8">
        <MetaCell label="提交人">{initiatorName || '—'}</MetaCell>
        <MetaCell label="提交时间">{formatDt(createdAt)}</MetaCell>
        <MetaCell label="更新时间">{formatDt(updatedAt || createdAt)}</MetaCell>
        <MetaCell label="流程状态">
          {statusTag ? <Tag color={statusTag.color} className="m-0">{statusTag.text}</Tag> : '—'}
        </MetaCell>
        {hasFlow ? (
          <>
            <MetaCell label="当前节点">{currentNode}</MetaCell>
            <MetaCell label="当前负责人">{currentAssignees}</MetaCell>
          </>
        ) : null}
      </div>
    </div>
  )
}
