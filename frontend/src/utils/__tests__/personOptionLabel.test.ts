import { describe, expect, it } from 'vitest'
import { formatPersonOptionLabel, plainPersonDisplayName } from '@/utils/personOptionLabel'

describe('formatPersonOptionLabel', () => {
  it('shows department suffix when present', () => {
    expect(formatPersonOptionLabel('张三', ['销售一部'])).toBe('张三 · 销售一部')
  })

  it('joins multiple departments', () => {
    expect(formatPersonOptionLabel('李四', ['华北区', '销售一部'])).toBe('李四 · 华北区/销售一部')
  })

  it('falls back to name only', () => {
    expect(formatPersonOptionLabel('王五', [])).toBe('王五')
  })
})

describe('plainPersonDisplayName', () => {
  it('strips department suffix', () => {
    expect(plainPersonDisplayName('杨昆 · 清欠办')).toBe('杨昆')
  })

  it('keeps plain name', () => {
    expect(plainPersonDisplayName('王华')).toBe('王华')
  })
})
