import type { WfNodeActions } from '@/types/lowcode'

/** 默认：暂存/通过/退回/转交；驳回关（线索流程单独开启） */
export const DEFAULT_NODE_ACTIONS: Required<WfNodeActions> = {
  submit: true,
  return: true,
  reject: false,
  submit_print: false,
  save: true,
  transfer: true,
  batch_submit: false,
  signature: false,
}

const LEAD_BIZ_TYPES = new Set(['lead', 'lead_reactivation'])

/** 解析节点操作；线索/180天激活默认保留驳回，其余流程默认关闭驳回 */
export function resolveNodeActions(
  raw?: WfNodeActions | null,
  bizType?: string | null,
): Required<WfNodeActions> {
  const out = { ...DEFAULT_NODE_ACTIONS, ...(raw || {}) }
  if (LEAD_BIZ_TYPES.has(bizType || '') && raw?.reject !== false) {
    out.reject = true
  }
  return out
}
