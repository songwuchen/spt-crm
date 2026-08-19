/** 待办任务 → 业务办理页路由（180天重激活待办应跳进关联线索详情） */

export interface TaskNavSource {
  biz_type?: string | null
  biz_id?: string | null
}

export function taskNavigatePath(task: TaskNavSource): string | null {
  const { biz_type: bizType, biz_id: bizId } = task
  if (!bizId) return null
  if (bizType === 'lead_reactivation' || bizType === 'lead') {
    return bizType === 'lead_reactivation' ? `/leads/${bizId}?react=1` : `/leads/${bizId}`
  }
  if (bizType === 'customer') return `/customers/${bizId}`
  if (bizType === 'project') return `/opportunities/${bizId}`
  if (bizType === 'contract') return `/contracts/${bizId}`
  return null
}
