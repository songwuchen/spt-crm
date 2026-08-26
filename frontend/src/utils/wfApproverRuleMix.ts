import type { WfApproverRule } from '@/types/lowcode'

export const DEPT_HEAD_CC_RULE: WfApproverRule = {
  type: 'dept_head',
  exclude_initiator: true,
}

function asSubRules(value: unknown): WfApproverRule[] {
  if (!Array.isArray(value)) return []
  return value.filter((x): x is WfApproverRule => !!x && typeof x === 'object' && !!(x as WfApproverRule).type)
}

export function approverRuleHasDeptHead(rule?: WfApproverRule): boolean {
  if (!rule) return false
  if (rule.type === 'dept_head') return true
  if (rule.type === 'mixed') {
    return asSubRules(rule.value).some((s) => s.type === 'dept_head')
  }
  return false
}

/** 去掉部门负责人子规则，便于编辑主规则。 */
export function stripDeptHeadFromApproverRule(rule: WfApproverRule): WfApproverRule {
  if (rule.type === 'dept_head') {
    return { type: 'specified_user', value: [] }
  }
  if (rule.type !== 'mixed') return rule
  const subs = asSubRules(rule.value).filter((s) => s.type !== 'dept_head')
  if (subs.length === 0) return { type: 'specified_user', value: [] }
  if (subs.length === 1) return subs[0]
  return { type: 'mixed', value: subs }
}

/** 在主规则上叠加/移除部门负责人抄送。 */
export function applyDeptHeadToApproverRule(rule: WfApproverRule, on: boolean): WfApproverRule {
  if (!on) return stripDeptHeadFromApproverRule(rule)
  if (approverRuleHasDeptHead(rule)) return rule
  const base = stripDeptHeadFromApproverRule(rule)
  if (base.type === 'mixed') {
    return { type: 'mixed', value: [...asSubRules(base.value), DEPT_HEAD_CC_RULE] }
  }
  return { type: 'mixed', value: [base, DEPT_HEAD_CC_RULE] }
}
