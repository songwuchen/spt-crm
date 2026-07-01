/**
 * Centralized label/color maps used across multiple pages.
 * Single source of truth for status display text and colors.
 */

// --- Approval ---
export const approvalStatusLabels: Record<string, string> = {
  pending: '审批中', approved: '已通过', rejected: '已驳回', withdrawn: '已撤回',
}
export const approvalStatusColors: Record<string, string> = {
  pending: 'processing', approved: 'success', rejected: 'error', withdrawn: 'default',
}
export const approvalModeLabels: Record<string, string> = {
  sequential: '顺序审批', parallel: '并行审批', any_one: '任一审批',
}
export const approvalModeColors: Record<string, string> = {
  sequential: 'blue', parallel: 'purple', any_one: 'cyan',
}
export const taskStatusLabelsApproval: Record<string, string> = {
  pending: '待审批', approved: '已通过', rejected: '已驳回', waiting: '等待中', cancelled: '已取消',
}
export const taskStatusColorsApproval: Record<string, string> = {
  pending: 'warning', approved: 'success', rejected: 'error', waiting: 'default', cancelled: 'default',
}
export const approvalBizTypeLabels: Record<string, string> = {
  quote_version: '报价审批', contract_version: '合同审批', change_request: '变更审批', solution: '方案审批',
}

// --- Service Ticket ---
export const ticketTypeLabels: Record<string, string> = {
  fault: '故障', maintenance: '维保', training: '培训', spare: '备件', upgrade: '升级改造',
}
export const ticketPriorityLabels: Record<string, string> = {
  low: '低', medium: '中', high: '高', critical: '紧急',
}
export const ticketPriorityColors: Record<string, string> = {
  low: 'default', medium: 'processing', high: 'warning', critical: 'error',
}
export const ticketStatusLabels: Record<string, string> = {
  open: '待处理', assigned: '已分配', in_progress: '处理中', resolved: '已解决', closed: '已关闭',
}
export const ticketStatusColors: Record<string, string> = {
  open: 'default', assigned: 'blue', in_progress: 'processing', resolved: 'success', closed: 'success',
}

// --- Lead ---
export const leadStatusConfig: Record<string, { label: string; dot: string; bg: string; text: string; border: string }> = {
  new: { label: '新建', dot: 'bg-blue-500', bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100' },
  following: { label: '跟进中', dot: 'bg-amber-500', bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-100' },
  qualified: { label: '已转化', dot: 'bg-emerald-500', bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-100' },
  discarded: { label: '已废弃', dot: 'bg-slate-300', bg: 'bg-slate-50', text: 'text-slate-400', border: 'border-slate-200' },
}

// --- Change Request ---
export const changeTypeLabels: Record<string, string> = {
  scope: '范围变更', schedule: '进度变更', cost: '费用变更', requirement: '需求变更',
}
export const changeStatusLabels: Record<string, string> = {
  draft: '草稿', submitted: '已提交', approved: '已批准', rejected: '已驳回', implemented: '已实施',
}

// --- Quote ---
export const quoteStatusLabels: Record<string, string> = {
  draft: '草稿', submitted: '已提交', approved: '已批准', rejected: '已驳回', expired: '已过期',
}
export const quoteStatusColors: Record<string, string> = {
  draft: 'default', submitted: 'processing', approved: 'success', rejected: 'error', expired: 'warning',
}

// --- Contract ---
export const contractStatusLabels: Record<string, string> = {
  draft: '草稿', signed: '已签署', terminated: '已终止',
}
export const contractStatusColors: Record<string, string> = {
  draft: 'default', signed: 'success', terminated: 'error',
}

// --- Solution ---
export const solutionStatusLabels: Record<string, string> = {
  draft: '草稿', reviewing: '评审中', approved: '已批准', rejected: '已驳回', obsolete: '已废弃',
}
export const solutionStatusColors: Record<string, string> = {
  draft: 'default', reviewing: 'processing', approved: 'success', rejected: 'error', obsolete: 'warning',
}

// --- AI Task ---
export const aiTaskStatusLabels: Record<string, string> = {
  pending: '等待中', running: '运行中', done: '已完成', failed: '失败',
}
export const aiTaskStatusColors: Record<string, string> = {
  pending: 'default', running: 'processing', done: 'success', failed: 'error',
}

// --- Delivery Milestone ---
export const milestoneStatusLabels: Record<string, string> = {
  pending: '待开始', in_progress: '进行中', completed: '已完成', delayed: '已延期',
}
export const milestoneStatusColors: Record<string, string> = {
  pending: 'default', in_progress: 'processing', completed: 'success', delayed: 'error',
}

// --- Payment ---
export const paymentPlanStatusLabels: Record<string, string> = {
  pending: '待收', received: '已收', overdue: '逾期',
}

// --- Opportunity Project ---
export const opportunityStatusMap: Record<string, { label: string; dot: string }> = {
  active: { label: '进行中', dot: 'bg-blue-500' },
  won: { label: '赢单', dot: 'bg-emerald-500' },
  lost: { label: '丢单', dot: 'bg-red-500' },
  suspended: { label: '暂停', dot: 'bg-slate-400' },
}

// --- Quote Line Item ---
export const quoteLineItemTypeLabels: Record<string, string> = {
  standard: '标准品', nonstandard: '非标品', service: '服务', spare: '备件',
}

// --- Renewal ---
export const renewalStatusLabels: Record<string, string> = {
  open: '进行中', won: '已赢单', lost: '已丢失',
}
export const renewalStatusColors: Record<string, string> = {
  open: 'processing', won: 'success', lost: 'error',
}
