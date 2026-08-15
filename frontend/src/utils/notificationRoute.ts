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
 *
 * 审批类：桌面端带查询参数，审批中心据此打开对应抽屉/详情（不再只落到空列表）。
 * 抄送类：落到审批中心「抄送我的」，并可带 wf= 打开对应流程。
 */
export function notificationTarget(
  bizType?: string,
  bizId?: string,
  notifType?: string,
): string | null {
  const mobile = currentZone() === 'mobile'
  const p = mobile ? '/m' : ''

  // 流程抄送 → 审批中心「抄送我的」（与 wf_process_cc 列表对齐）
  if (notifType === 'approval_cc') {
    if (mobile) {
      return bizId
        ? `/m/approvals?tab=cc&wf=${encodeURIComponent(bizId)}`
        : '/m/approvals?tab=cc'
    }
    return bizId
      ? `/approvals?tab=cc&wf=${encodeURIComponent(bizId)}`
      : '/approvals?tab=cc'
  }

  switch (bizType) {
    case 'approval_flow':
    case 'approval':
      // 旧引擎：移动端有按流程的详情页；Web 端用 ?flow= 打开审批详情
      if (mobile) return bizId ? `/m/approvals/${bizId}` : '/m/approvals'
      return bizId ? `/approvals?flow=${encodeURIComponent(bizId)}` : '/approvals'
    case 'wf_instance':
    case 'workflow':
      // 新工作流：移动端进 lowcode 详情；桌面端 ?wf= 打开流程抽屉
      if (mobile) return bizId ? `/m/lowcode/approvals/${bizId}` : '/m/lowcode/approvals'
      return bizId ? `/approvals?wf=${encodeURIComponent(bizId)}` : '/approvals'
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
      // 通知若带的是版本 id（非流程实例），无法稳定拼合同 URL，回审批中心
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
