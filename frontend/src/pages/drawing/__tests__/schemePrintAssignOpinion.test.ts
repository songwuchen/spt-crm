import { describe, expect, it } from 'vitest'
import {
  buildCsDrawingPrintDocument,
  buildInstallPrintDocument,
  buildRequisitionPrintDocument,
} from '@/pages/drawing/schemePrint'
import type { WfFlowStep } from '@/types/lowcode'

const assignStep: WfFlowStep = {
  node_instance_id: 'n-assign',
  node_name: '研究院安排',
  status: 'completed',
  action: 'approve',
  opinion: '请优先处理包装单',
  handler_name: '郑志颖',
  completed_at: '2026-08-20T10:00:00',
}

describe('drawing print includes research-assign opinion', () => {
  it('requisition footer contains 研究院安排 opinion when chief steps also present', () => {
    const html = buildRequisitionPrintDocument({
      formData: { serial_no: '2026082601', transfer_channel: '邮件' },
      flowSteps: [
        assignStep,
        {
          node_instance_id: 'n-chief',
          node_name: '总工审批',
          status: 'completed',
          action: 'approve',
          opinion: '同意',
          handler_name: '曹修国',
          completed_at: '2026-08-26T08:25:00',
        },
        {
          node_instance_id: 'n-dept',
          node_name: '部门审批',
          status: 'completed',
          action: 'approve',
          opinion: '同意',
          handler_name: '张贺',
          completed_at: '2026-08-26T08:07:00',
        },
      ],
    })
    expect(html).toContain('总工审批')
    expect(html).toContain('研究院安排')
    expect(html).toContain('请优先处理包装单')
  })

  it('requisition footer contains 研究院安排 opinion', () => {
    const html = buildRequisitionPrintDocument({
      formData: { serial_no: '2026082001', transfer_channel: '邮件' },
      flowSteps: [assignStep],
    })
    expect(html).toContain('研究院安排')
    expect(html).toContain('请优先处理包装单')
  })

  it('install footer contains 研究院安排 opinion', () => {
    const html = buildInstallPrintDocument({
      formData: {
        serial_no: '2026082001',
        project_no: 'P1',
        design_card_no: '02-1',
        drawing_issue_type: '出方案图',
      },
      flowSteps: [assignStep],
    })
    expect(html).toContain('请优先处理包装单')
  })

  it('cs drawing footer contains 部门指派 opinion', () => {
    const html = buildCsDrawingPrintDocument({
      formData: {
        serial_no: '2026082001',
        drawing_no_note: '图1',
        dept_dispatch: '研管办',
        transfer_channel: '邮件',
      },
      flowSteps: [{
        ...assignStep,
        node_name: '部门指派-研管办',
        opinion: '转新乡工艺包装',
      }],
    })
    expect(html).toContain('部门指派-研管办')
    expect(html).toContain('转新乡工艺包装')
  })
})
