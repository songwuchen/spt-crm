import { describe, it, expect } from 'vitest'
import { buildTechAgreementReviewFieldLabels } from '@/utils/dataLogLabels'

describe('buildTechAgreementReviewFieldLabels', () => {
  it('includes native and form_json keys', () => {
    const map = buildTechAgreementReviewFieldLabels()
    expect(map.company_name).toBe('公司名称')
    expect(map['form_json.design_approver_ids']).toBe('设计审批')
    expect(map.has_objection).toBe('是否有异议')
  })
})
