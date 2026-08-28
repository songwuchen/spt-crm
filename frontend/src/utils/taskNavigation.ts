/** 待办任务 → 业务办理页路由（180天重激活待办应跳进关联线索详情） */
import { currentZone } from '@/config/zone'
import { toZonePath } from '@/utils/zonePaths'

export interface TaskNavSource {
  biz_type?: string | null
  biz_id?: string | null
}

export function taskNavigatePath(task: TaskNavSource, mobile = currentZone() === 'mobile'): string | null {
  const { biz_type: bizType, biz_id: bizId } = task
  if (!bizId) return null
  let path: string | null = null
  if (bizType === 'lead_reactivation' || bizType === 'lead') {
    path = bizType === 'lead_reactivation' ? `/leads/${bizId}?react=1` : `/leads/${bizId}`
  } else if (bizType === 'customer') {
    path = `/customers/${bizId}`
  } else if (bizType === 'project') {
    path = `/opportunities/${bizId}`
  } else if (bizType === 'contract') {
    path = `/contracts/${bizId}`
  }
  if (!path) return null
  return mobile ? toZonePath(path, 'mobile') : path
}
