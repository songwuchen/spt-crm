import { describe, expect, it } from 'vitest'
import { supplementDrawingNo, supplementPrintPrefix } from '@/pages/drawing/prodCardPrint'

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
