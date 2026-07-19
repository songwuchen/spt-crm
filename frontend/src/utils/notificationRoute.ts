// Zone-aware routing for notifications.
//
// A notification carries only (biz_type, biz_id); the destination page differs
// between the full Web 端 and the 移动端 (different route trees, /… vs /m/…).
// Both the desktop NotificationBell/NotificationCenter and the MobileNotifications
// page resolve their jump target through here so the two stay in sync.

import { currentZone } from '@/config/zone'

/**
 * Resolve the in-app target route for a notification. Returns null when the
 * biz_type has no dedicated detail page (caller then just marks it read).
 */
export function notificationTarget(bizType?: string, bizId?: string): string | null {
  const mobile = currentZone() === 'mobile'
  const p = mobile ? '/m' : ''
  switch (bizType) {
    case 'approval_flow':
    case 'approval':
      // 移动端有按流程的详情页；Web 端用审批中心列表
      return mobile ? (bizId ? `/m/approvals/${bizId}` : '/m/approvals') : '/approvals'
    case 'wf_instance':
      // 新工作流引擎的流程实例，走扩展平台审批中心（与旧引擎分属不同路由树）
      return mobile
        ? (bizId ? `/m/lowcode/approvals/${bizId}` : '/m/lowcode/approvals')
        : '/lowcode/approvals'
    case 'lead':
      return bizId ? `${p}/leads/${bizId}` : `${p}/leads`
    case 'service_ticket':
      return bizId ? `${p}/service-tickets/${bizId}` : null
    case 'project':
      return bizId ? `${p}/opportunities/${bizId}` : null
    case 'contract':
      // 移动端无合同详情路由，回退到合同列表
      return mobile ? '/m/contracts' : (bizId ? `/opportunities/contracts/${bizId}` : null)
    case 'customer':
      return bizId ? `${p}/customers/${bizId}` : null
    default:
      return null
  }
}

/** The "所有通知" list page for the current zone. */
export function notificationsHome(): string {
  return currentZone() === 'mobile' ? '/m/notifications' : '/notifications'
}
