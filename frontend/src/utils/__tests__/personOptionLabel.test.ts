import { describe, expect, it } from 'vitest'
import { formatPersonOptionLabel } from '@/utils/personOptionLabel'

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
