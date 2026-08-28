import { describe, expect, it } from 'vitest'
import { findFirstMissingReviewRequired } from '@/constants/contractReview'

describe('findFirstMissingReviewRequired', () => {
  it('requires department_id for contract review', () => {
    const missing = findFirstMissingReviewRequired({
      review_type: '合同评审',
      owner_id: 'u1',
      company_name: '测试公司',
      is_export: '否',
      need_pricing: '未核价',
      need_install: '无需指导安装',
      elec_ctrl: '含电控电缆',
      review_json: {
        company_nature: '民营',
        industry: '矿山',
        scale_fund: 1000,
        salary_insurance: '正常',
        has_weight_req: '无',
        sign_basis: '招投标',
      },
    })
    expect(missing).toEqual({ name: ['department_id'], label: '业务部门' })
  })

  it('passes when department_id is set', () => {
    const missing = findFirstMissingReviewRequired({
      review_type: '合同评审',
      owner_id: 'u1',
      department_id: 'd1',
      company_name: '测试公司',
      is_export: '否',
      need_pricing: '未核价',
      need_install: '无需指导安装',
      elec_ctrl: '含电控电缆',
      review_json: {
        company_nature: '民营',
        industry: '矿山',
        scale_fund: 1000,
        salary_insurance: '正常',
        has_weight_req: '无',
        sign_basis: '招投标',
      },
    })
    expect(missing).toBeNull()
  })
})
