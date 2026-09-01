import { describe, expect, it } from 'vitest'
import { approvalLines, supplementDrawingNo, supplementPrintPrefix } from '@/pages/drawing/prodCardPrint'
import type { WfFlowStep } from '@/types/lowcode'

describe('supplementDrawingNo', () => {
  it('prefers yes_contract_no and ignores no_drawing_no', () => {
    expect(supplementDrawingNo({
      is_supplement: '是',
      yes_contract_no: 'WMGF202608143',
      no_drawing_no: 'KS26270',
    })).toBe('WMGF202608143')
  })

  it('does not fall back to no_drawing_no when yes_contract_no missing', () => {
    expect(supplementDrawingNo({
      no_drawing_no: 'KS26270',
      drawing_no: 'WMGF202608143',
    })).toBe('WMGF202608143')
  })
})

describe('supplementPrintPrefix', () => {
  it('prefers yes_contract_no over no_drawing_no for supplement filename', () => {
    const prefix = supplementPrintPrefix({
      is_supplement: '是',
      yes_contract_no: 'WMGF202608143',
      no_drawing_no: 'KS26270',
      serial_no: 'SCK00018',
    })
    expect(prefix).toBe('WMGF202608143')
  })

  it('falls back to process serial when contract no missing', () => {
    const prefix = supplementPrintPrefix({
      no_drawing_no: 'KS26270',
      serial_no: 'SCK00018',
    })
    expect(prefix).toBe('SCK00018')
  })

  it('falls back to process serial when no contract or drawing', () => {
    const prefix = supplementPrintPrefix({ serial_no: 'SCK00018' }, 'SCK00018')
    expect(prefix).toBe('SCK00018')
  })
})

describe('approvalLines', () => {
  const step = (node: string, at: string, id = node): WfFlowStep => ({
    node_instance_id: id,
    node_name: node,
    node_type: 'approve',
    status: 'completed',
    action: 'approve',
    opinion: '同意',
    handler_name: '张三',
    completed_at: at,
  })

  it('sorts by completed_at descending (newest first)', () => {
    const lines = approvalLines([
      step('财务核价', '2026-08-01T10:00:00Z'),
      step('设计指派', '2026-08-03T10:00:00Z'),
      step('区域经理', '2026-08-02T10:00:00Z'),
    ])
    expect(lines[0]).toContain('设计指派')
    expect(lines[1]).toContain('区域经理')
    expect(lines[2]).toContain('财务核价')
  })
})
