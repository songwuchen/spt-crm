import { describe, expect, it } from 'vitest'
import { buildTechAgreementReviewPrintHtml } from '@/pages/techAgreementReview/techAgreementReviewPrint'
import type { TechAgreementReview } from '@/api/techAgreementReview'

/** 简道云样单 HTJSXY-2026081901 */
const jdySampleRow: TechAgreementReview = {
  id: 'tar-1',
  review_code: 'HTJSXY-2026081901',
  status: 'approved',
  applicant_name: '王华',
  apply_at: '2026-08-19T08:00:00',
  owner_name: '李振朝',
  department_name: '清欠办',
  company_name: '山东瑞信招标有限公司',
  industry: '工业升级',
  project_title:
    '滨州市宏通资源综合利用有限公司，邹平炭渣振动叠筛设备项目，滨州市宏通资源综合利用有限公司，滨州炭渣振动叠筛设备项目，详见附件',
  has_weight_req: '无',
  use_idle_equip: '否',
  has_smart: '否',
  need_pricing: '已核价',
  sign_basis: '前期投标阶段',
  pre_contact: '杨梅',
  remark: '',
}

const jdySampleAttachments = [
  '(河南威猛振动设备) 邹平炭渣车间-振动叠筛技术协议.docx',
  '滨州炭渣车间-振动叠筛技术协议.docx',
]

describe('techAgreementReviewPrint', () => {
  it('对齐简道云表格模板 20230517112920525（HTJSXY-2026081901）', () => {
    const html = buildTechAgreementReviewPrintHtml({
      row: jdySampleRow,
      drawingFiles: jdySampleAttachments.map((original_name) => ({ original_name })),
      agreementFiles: jdySampleAttachments.map((original_name) => ({ original_name })),
      flowSteps: [
        {
          node_instance_id: 'n11',
          node_name: '审批反馈',
          status: 'completed',
          action: 'approve',
          opinion: '无',
          handler_name: '王华',
          completed_at: '2026-08-20T14:06:00',
        },
        {
          node_instance_id: 'n10',
          node_name: '设计审批2.1',
          status: 'completed',
          action: 'approve',
          opinion: '不建议聚氨酯筛板',
          handler_name: '周彦立',
          completed_at: '2026-08-20T13:57:00',
        },
        {
          node_instance_id: 'n9',
          node_name: '部门审批',
          status: 'completed',
          action: 'approve',
          opinion: '请设计和核价部门核实',
          handler_name: '李新合',
          completed_at: '2026-08-19T10:38:00',
        },
      ],
    })

    expect(html).toContain('class="meta-head"')
    expect(html).toContain('申请人')
    expect(html).toContain('日期时间')
    expect(html).toContain('流水号')
    expect(html).toContain('王华')
    expect(html).toContain('2026-08-19')
    expect(html).toContain('HTJSXY-2026081901')
    expect(html).not.toContain('<td class="lbl">申请人</td>')

    expect(html).toContain('李振朝')
    expect(html).toContain('清欠办')
    expect(html).toContain('山东瑞信招标有限公司')
    expect(html).toContain('合同是否含智能化部分')
    expect(html).toContain('前期投标阶段')
    expect(html).toContain('杨梅')
    expect(html).toContain('流转完成')
    expect(html).toContain('邹平炭渣振动叠筛设备项目')

    expect(html).toContain('认可图（附件）')
    expect(html).toContain('技术协议（附件）')
    expect(html).toContain('class="val-left attach"')
    expect(html).toContain(jdySampleAttachments.join(', '))

    expect(html).toContain('审批意见</td>')
    expect(html).toContain('op-sep')
    expect(html.indexOf('审批反馈')).toBeLessThan(html.indexOf('设计审批2.1'))
    expect(html.indexOf('设计审批2.1')).toBeLessThan(html.indexOf('部门审批'))

    expect(html).not.toContain('打印时间')
    expect(html).not.toContain('设计审批</td>')
    expect(html).not.toContain('设计审批2</td>')
    expect(html).not.toContain('是否有异议')
    expect(html).not.toContain('电控装置')
  })

  it('申请人/业务员只显示姓名，不带部门后缀', () => {
    const html = buildTechAgreementReviewPrintHtml({
      row: {
        ...jdySampleRow,
        applicant_name: '杨昆 · 清欠办',
        owner_name: '李振朝 · 销售部',
      },
    })
    expect(html).toContain('杨昆')
    expect(html).not.toContain('杨昆 · 清欠办')
    expect(html).not.toContain('李振朝 · 销售部')
    expect(html).toContain('李振朝')
  })
})
