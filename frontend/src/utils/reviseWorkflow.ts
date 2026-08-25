import type { WfFlowStep, WfInstanceDetail } from '@/types/lowcode'

export function isReviseFlowStep(step: WfFlowStep): boolean {
  return step.node_type === 'revise'
    || step.node_def_id === '__initiator_revise__'
    || (step.node_name || '').includes('修改并重新提交')
}

type WfTaskRow = WfInstanceDetail['tasks'][number] & { node_instance_id?: string }

/** 从流程详情解析当前用户可处理的修订待办 task_id */
export function resolveReviseTaskId(
  detail: WfInstanceDetail | null | undefined,
  opts?: { urlTaskId?: string | null; userId?: string | null },
): string | null {
  if (opts?.urlTaskId) return opts.urlTaskId
  if (!detail) return null

  const ct = detail.current_task
  if (ct?.task_id && (ct.task_kind === 'revise' || ct.node_type === 'revise')) {
    return ct.task_id
  }

  const reviseNodeIds = new Set<string>()
  for (const s of detail.flow_steps || []) {
    if (isReviseFlowStep(s)) reviseNodeIds.add(s.node_instance_id)
  }
  const curRevise = (detail.flow_steps || []).find((s) => s.is_current && isReviseFlowStep(s))
  if (curRevise?.node_instance_id) reviseNodeIds.add(curRevise.node_instance_id)

  const terminal = detail.status === 'returned'
    || detail.status === 'rejected'
    || detail.status === 'withdrawn'
  const uid = opts?.userId

  for (const raw of detail.tasks || []) {
    const t = raw as WfTaskRow
    if (t.status !== 'pending') continue
    const onRevise = reviseNodeIds.size
      ? reviseNodeIds.has(t.node_instance_id || '')
      : terminal
    if (!onRevise) continue
    if (!uid || t.assignee_id === uid || detail.initiator_id === uid) {
      return t.id
    }
  }
  return null
}

export function canUserActRevise(
  detail: WfInstanceDetail | null | undefined,
  taskId: string | null | undefined,
  userId: string | null | undefined,
): boolean {
  if (!detail || !taskId || !userId) return false
  if (detail.initiator_id === userId) return true
  const t = detail.tasks?.find((x) => x.id === taskId)
  return t?.assignee_id === userId
}

export function hasActiveReviseStep(detail: WfInstanceDetail | null | undefined): boolean {
  if (!detail) return false
  return (detail.flow_steps || []).some((s) => s.is_current && isReviseFlowStep(s))
}
