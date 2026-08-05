import { describe, it, expect } from 'vitest'
import dayjs from 'dayjs'
import { formatFormDate, isValidFormDate, formDateRule } from '../formDate'

describe('formDate', () => {
  it('accepts empty', () => {
    expect(isValidFormDate(null)).toBe(true)
    expect(isValidFormDate(undefined)).toBe(true)
    expect(isValidFormDate('')).toBe(true)
    expect(formatFormDate(null)).toBeUndefined()
  })

  it('formats valid dayjs', () => {
    expect(formatFormDate(dayjs('2026-08-05'))).toBe('2026-08-05')
    expect(isValidFormDate(dayjs('2026-08-05'))).toBe(true)
  })

  it('rejects invalid dayjs that would become Invalid Date', () => {
    const bad = dayjs('not-a-date')
    expect(bad.isValid()).toBe(false)
    expect(isValidFormDate(bad)).toBe(false)
    expect(formatFormDate(bad)).toBeNull()
    expect(bad.format('YYYY-MM-DD')).toBe('Invalid Date')
  })

  it('rejects Invalid Date string', () => {
    expect(isValidFormDate('Invalid Date')).toBe(false)
  })

  it('formDateRule rejects invalid', async () => {
    await expect(formDateRule.validator(null, dayjs('x'))).rejects.toThrow(/有效日期/)
    await expect(formDateRule.validator(null, dayjs('2026-01-01'))).resolves.toBeUndefined()
    await expect(formDateRule.validator(null, null)).resolves.toBeUndefined()
  })
})
