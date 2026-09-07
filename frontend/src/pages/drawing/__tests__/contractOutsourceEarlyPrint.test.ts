import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'
import {
  buildContractOutsourceEarlyPrintFileName,
  buildContractOutsourceEarlyPrintHtml,
} from '@/pages/drawing/contractOutsourceEarlyPrint'

describe('contract outsource early print', () => {
  const labels = {
    users: {
      u1: '杨彩梅',
      u2: '李兴玉',
      u3: '刘松超',
    },
    depts: {
      d1: '冶金矿山装备销售事业部',
    },
    contracts: {
      c1: 'WMGF202608121',
    },
  }

  it('builds file name like JDY sample', () => {
    const name = buildContractOutsourceEarlyPrintFileName({
      contract_no: 'c1',
      salesperson: 'u1',
      department: 'd1',
      apply_datetime: '2026-08-31',
    }, labels, dayjs('2026-09-04'))
    expect(name).toContain('WMGF202608121')
    expect(name).toContain('杨彩梅')
    expect(name).toContain('合同外购件提前安排流程')
    expect(name).toContain('2026-08-31')
  })

  it('renders main fields and equipment table', () => {
    const html = buildContractOutsourceEarlyPrintHtml({
      formData: {
        serial_no: '2026083100001',
        contract_no: 'c1',
        salesperson: 'u1',
        department: 'd1',
        transfer_dept_head: 'u3',
        designer_multi: ['u2'],
        business_desc: '提前外购申请',
        equipment_details: [{
          designer: 'u2',
          product_name: '电机',
          spec_model: 'YE5-160M-6-7.5-380-50-IP55-F',
          material: '外购件',
          qty: 10,
          brand: '南阳或卧龙',
        }],
      },
      labels,
      initiatorName: '史文超',
      startedAt: '2026-08-31T06:22:18',
      flowSteps: [{
        node_instance_id: '1',
        node_name: '市场支持中心',
        node_type: 'approval',
        status: 'completed',
        handler_name: '王亚飞',
        completed_at: '2026-08-31T06:23:37',
        action: 'approve',
      }],
      printDate: dayjs('2026-09-04T08:02:48'),
    })
    expect(html).toContain('合同外购件提前安排流程')
    expect(html).toContain('WMGF202608121')
    expect(html).toContain('杨彩梅')
    expect(html).toContain('冶金矿山装备销售事业部')
    expect(html).toContain('刘松超')
    expect(html).toContain('李兴玉')
    expect(html).toContain('提前外购申请')
    expect(html).toContain('YE5-160M-6-7.5-380-50-IP55-F')
    expect(html).toContain('审批意见')
    expect(html).toContain('王亚飞')
  })
})
