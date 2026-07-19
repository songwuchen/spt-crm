import { describe, it, expect } from 'vitest'
import { MASK_VALUE, isMaskValue, isMasked, fmtMoney, fmtPct } from '../mask'

describe('mask helpers', () => {
  it('识别后端下发的脱敏哨兵', () => {
    expect(isMaskValue(MASK_VALUE)).toBe(true)
    expect(isMaskValue('12')).toBe(false)
    expect(isMaskValue(12)).toBe(false)
  })

  it('数值字段的脱敏判定刻意更宽，避免退化成 NaN', () => {
    expect(isMasked('***')).toBe(true)
    expect(isMasked('保密')).toBe(true)   // 换了哨兵写法也不会显示 NaN
    expect(isMasked('12.5')).toBe(false)  // 数字串仍按数字处理
    expect(isMasked(12.5)).toBe(false)
    expect(isMasked(null)).toBe(false)
  })

  it('金额格式化：脱敏出 ***，空值出 -，正常值带 ¥', () => {
    expect(fmtMoney('***')).toBe('***')
    expect(fmtMoney(null)).toBe('-')
    expect(fmtMoney(undefined)).toBe('-')
    expect(fmtMoney(1234)).toBe('¥1,234')
    expect(fmtMoney('1234')).toBe('¥1,234')
    expect(fmtMoney(0)).toBe('¥0')  // 0 是合法金额，不能当空值
  })

  it('百分比格式化：入参为小数', () => {
    expect(fmtPct('***')).toBe('***')
    expect(fmtPct(null)).toBe('-')
    expect(fmtPct(0.155)).toBe('15.5%')
    expect(fmtPct(0)).toBe('0.0%')
  })
})
