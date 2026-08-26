import { describe, expect, it } from 'vitest'
import {
  applyDeptHeadToApproverRule,
  approverRuleHasDeptHead,
  stripDeptHeadFromApproverRule,
} from '@/utils/wfApproverRuleMix'

describe('wfApproverRuleMix', () => {
  it('指定人员 + 部门负责人 → mixed', () => {
    const base = { type: 'specified_user' as const, value: ['u1'] }
    const mixed = applyDeptHeadToApproverRule(base, true)
    expect(mixed.type).toBe('mixed')
    expect(approverRuleHasDeptHead(mixed)).toBe(true)
    expect(stripDeptHeadFromApproverRule(mixed)).toEqual(base)
  })

  it('取消勾选后还原主规则', () => {
    const base = { type: 'specified_user' as const, value: ['u1', 'u2'] }
    const withHead = applyDeptHeadToApproverRule(base, true)
    expect(stripDeptHeadFromApproverRule(applyDeptHeadToApproverRule(withHead, false))).toEqual(base)
  })
})
