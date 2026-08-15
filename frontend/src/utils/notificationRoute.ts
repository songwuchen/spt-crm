// Zone-aware routing for notifications.
//
// A notification carries only (biz_type, biz_id); the destination page differs
// between the full Web 端 and the 移动端 (different route trees, /… vs /m/…).
// Both the desktop NotificationBell/NotificationCenter and the MobileNotifications
// page resolve their jump target through here so the two stay in sync.

import { currentZone } from '@/config/zone'

/** 流程类通知：在通知中心本页打开详情，避免整页跳到「审批中心」造成割裂感 */
function notificationsWfTarget(bizId: string | undefined, mobile: boolean): string {
  if (mobile) {
    // 移动端进流程详情页（非整页切到审批中心 Tab）
    return bizId
      ? `/m/lowcode/approvals/${encodeURIComponent(bizId)}`
      : '/m/notifications'
  }
  return bizId
    ? `/notifications?wf=${encodeURIComponent(bizId)}`
    : '/notifications'
}

export function isInlineWorkflowNotification(
  bizType?: string,
  notifType?: string,
): boolean {
  if (notifType === 'approval_cc') return true
  if (
    (notifType === 'approval_pending' || notifType === 'approval_decided' || notifType === 'approval_sla_overdue')
    && (bizType === 'wf_instance' || bizType === 'workflow')
  ) {
    return true
  }
  return bizType === 'wf_instance' || bizType === 'workflow'
}

/**
 * Resolve the in-app target route for a notification. Returns null when the
 * biz_type has no dedicated detail page (caller then just marks it read).
 *
 * 流程抄送 / 新引擎审批结果与待办：PC 落在通知中心并带 ?wf= 打开抽屉；
 * 待办也可在抽屉内处理，不必先跳进审批中心。
 * 旧引擎 approval_flow 仍进审批中心。
 */
export function notificationTarget(
  bizType?: string,
  bizId?: string,
  notifType?: string,
): string | null {
  const mobile = currentZone() === 'mobile'
  const p = mobile ? '/m' : ''

  if (notifType === 'approval_cc') {
    return notificationsWfTarget(bizId, mobile)
  }

  if (
    (notifType === 'approval_pending' || notifType === 'approval_decided' || notifType === 'approval_sla_overdue')
    && (bizType === 'wf_instance' || bizType === 'workflow')
  ) {
    return notificationsWfTarget(bizId, mobile)
  }

  switch (bizType) {
    case 'approval_flow':
    case 'approval':
      // 旧引擎：移动端有按流程的详情页；Web 端用 ?flow= 打开审批详情
      if (mobile) return bizId ? `/m/approvals/${bizId}` : '/m/approvals'
      return bizId ? `/approvals?flow=${encodeURIComponent(bizId)}` : '/approvals'
    case 'wf_instance':
    case 'workflow':
      return notificationsWfTarget(bizId, mobile)
    case 'lead':
      return bizId ? `${p}/leads/${bizId}` : `${p}/leads`
    case 'service_ticket':
      return bizId ? `${p}/service-tickets/${bizId}` : null
    case 'project':
      return bizId ? `${p}/opportunities/${bizId}` : null
    case 'contract':
      // 移动端无合同详情路由，回退到合同列表
      return mobile ? '/m/contracts' : (bizId ? `/opportunities/contracts/${bizId}` : null)
    case 'contract_review':
      return bizId ? `${p}/contract-reviews/${bizId}` : `${p}/contract-reviews`
    case 'tech_agreement_review':
      return bizId ? `/tech-agreement-reviews/${bizId}` : '/tech-agreement-reviews'
    case 'contract_version':
      return mobile ? '/m/approvals' : '/approvals'
    case 'customer':
      return bizId ? `${p}/customers/${bizId}` : null
    case 'quote_version':
    case 'change_request':
    case 'solution':
    case 'order':
      return mobile ? '/m/approvals' : '/approvals'
    default:
      return null
  }
}

/** The "所有通知" list page for the current zone. */
export function notificationsHome(): string {
  return currentZone() === 'mobile' ? '/m/notifications' : '/notifications'
}
