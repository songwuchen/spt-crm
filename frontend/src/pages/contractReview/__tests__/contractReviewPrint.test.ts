import { describe, expect, it } from 'vitest'
import { buildContractReviewPrintHtml } from '@/pages/contractReview/contractReviewPrint'
import type { ContractReview } from '@/api/contractReview'

const sampleRow: ContractReview = {
  id: 'cr-1',
  review_code: 'HTPS2026082600001',
  review_type: '合同评审',
  status: 'approved',
  company_name: '北京市大兴区环境卫生服务中心',
  owner_name: '张三',
  department_name: '冶金装备销售部',
  need_pricing: '有核价',
  is_export: '否',
  need_install: '指导安装',
  project_title: '振动筛采购项目',
  contract_amount: 1280000,
  created_by_name: '李四',
  created_at: '2026-08-26T08:00:00',
  review_json: {
    industry: '工业升级',
    company_nature: '国企',
    has_weight_req: '无',
    sign_basis: '公开招标',
  },
}

describe('contractReviewPrint', () => {
  it('生成合同评审系统打印 HTML（含分区与审批意见）', () => {
    const html = buildContractReviewPrintHtml({
      row: sampleRow,
      costFiles: [{ original_name: '成本.xlsx' }],
      reviewFiles: [{ original_name: '合同.pdf' }],
      flowSteps: [
        {
          node_instance_id: 'n1',
          node_name: '业务部门',
          status: 'completed',
          action: 'approve',
          opinion: '同意签订',
          handler_name: '王五',
          completed_at: '2026-08-26T10:00:00',
        },
      ],
    })

    expect(html).toContain('合同评审')
    expect(html).toContain('HTPS2026082600001')
    expect(html).toContain('北京市大兴区环境卫生服务中心')
    expect(html).toContain('基本信息')
    expect(html).toContain('客户信息')
    expect(html).toContain('成本.xlsx')
    expect(html).toContain('合同.pdf')
    expect(html).toContain('审批意见')
    expect(html).toContain('业务部门')
    expect(html).toContain('同意签订')
    expect(html).toContain('section-table')
    expect(html).toContain('class="ops"')
    expect(html).toContain('流转完成')
  })
})
