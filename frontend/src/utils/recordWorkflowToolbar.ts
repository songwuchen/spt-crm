import type { WfInstanceDetail } from '@/types/lowcode'
import { canUserActRevise } from '@/utils/reviseWorkflow'

const REVISE_END_STATUSES = new Set(['rejected', 'withdrawn', 'returned'])

export type EndProcessPermissionOpts = {
  canManageWorkflow?: boolean
  canDeleteFormData?: boolean
}

/** 记录详情工具栏是否可「结束流程」（对齐简道云：进行中终止 / 修订待办关闭） */
export function canEndProcessInRecordView(
  detail: WfInstanceDetail | null | undefined,
  userId: string | null | undefined,
  reviseTaskId: string | null | undefined,
  opts?: EndProcessPermissionOpts,
): boolean {
  if (detail?.can_end_process != null) return detail.can_end_process
  if (!detail?.id || !userId) return false

  if (detail.status === 'running') {
    const isAdmin = opts?.canManageWorkflow || opts?.canDeleteFormData
    return detail.initiator_id === userId || !!isAdmin
  }

  if (!REVISE_END_STATUSES.has(detail.status || '')) return false
  if (detail.initiator_id === userId) return true
  if (reviseTaskId && canUserActRevise(detail, reviseTaskId, userId)) return true
  return false
}

/** 结束流程是否为「终止进行中流程」（区别于关闭修订待办） */
export function isRunningProcessTerminate(detail: WfInstanceDetail | null | undefined): boolean {
  return detail?.status === 'running'
}
