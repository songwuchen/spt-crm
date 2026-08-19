/** 线索流程：信息情报部 vs 业务员确认是否转商机 */

export function isLeadOwnerConfirmNode(nodeName?: string | null, nodeId?: string | null): boolean {
  const id = (nodeId || '').trim()
  if (id === 'cc_owner' || id === 'approval_owner_confirm') return true
  const name = (nodeName || '').trim()
  if (!name) return false
  return name.includes('转商机') || name.includes('确认转化')
}

/** 撤回/驳回/退回发起人后的「修改并重新提交」待办（非审批） */
export function isLeadReviseTodo(opts: {
  taskKind?: string | null
  nodeType?: string | null
  nodeName?: string | null
}): boolean {
  if (opts.taskKind === 'revise' || opts.nodeType === 'revise') return true
  const name = (opts.nodeName || '').trim()
  return name.includes('修改并重新提交') || name === '修改后重新提交'
}

/** 线索修订待办 → 申报编辑页（对齐简道云：待办点进去像第一次报项目） */
export function leadReviseEditPath(leadId: string, taskId: string, mobile = false): string {
  const base = mobile ? `/m/leads/${leadId}/edit` : `/leads/${leadId}/edit`
  const q = new URLSearchParams({ reviseTask: taskId })
  return `${base}?${q.toString()}`
}

/** 待办是否应展示情报四态表单（收录/袭击/回退） */
export function isLeadIntelTodo(opts: {
  bizType?: string | null
  nodeName?: string | null
  nodeId?: string | null
  nodeType?: string | null
  taskKind?: string | null
}): boolean {
  if (opts.bizType === 'lead_reactivation') {
    return isLeadReactivationIntelTodo(opts)
  }
  if (opts.bizType !== 'lead') return false
  if (isLeadReviseTodo(opts)) return false
  if (isLeadOwnerConfirmNode(opts.nodeName, opts.nodeId)) return false
  return true
}

/** 180天激活：情报审节点 */
export function isLeadReactivationIntelTodo(opts: {
  bizType?: string | null
  nodeName?: string | null
  nodeId?: string | null
}): boolean {
  if (opts.bizType !== 'lead_reactivation') return false
  const id = (opts.nodeId || '').trim()
  if (id === 'approval_intel') return true
  const name = (opts.nodeName || '').trim()
  return name.includes('情报') || name.includes('激活')
}

/** 180天激活：业务员/内勤跟进节点 */
export function isLeadReactivationFollowTodo(opts: {
  bizType?: string | null
  nodeName?: string | null
  nodeId?: string | null
}): boolean {
  if (opts.bizType !== 'lead_reactivation') return false
  if (isLeadReactivationIntelTodo(opts)) return false
  const id = (opts.nodeId || '').trim()
  return id === 'approval_sales' || id === 'approval_filler' || id === 'approval_filler_skip' || !!opts.nodeName
}
