/** 线索流程：信息情报部 vs 业务员确认是否转商机 */

export function isLeadOwnerConfirmNode(nodeName?: string | null, nodeId?: string | null): boolean {
  const id = (nodeId || '').trim()
  if (id === 'cc_owner' || id === 'approval_owner_confirm') return true
  const name = (nodeName || '').trim()
  if (!name) return false
  return name.includes('转商机') || name.includes('确认转化')
}

/** 待办是否应展示情报四态表单（收录/袭击/回退） */
export function isLeadIntelTodo(opts: {
  bizType?: string | null
  nodeName?: string | null
  nodeId?: string | null
  nodeType?: string | null
}): boolean {
  if (opts.bizType !== 'lead') return false
  if (isLeadOwnerConfirmNode(opts.nodeName, opts.nodeId)) return false
  return true
}
