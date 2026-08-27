import { describe, expect, it } from 'vitest'
import { resolveExpandDetailTablePageSize } from '@/utils/listDetailExpandPagination'

describe('resolveExpandDetailTablePageSize', () => {
  it('returns base page size when detail expand is off', () => {
    expect(resolveExpandDetailTablePageSize(20, null)).toBe(20)
    expect(resolveExpandDetailTablePageSize(20, undefined)).toBe(20)
  })

  it('raises page size to fit all flat rows on current API page', () => {
    expect(resolveExpandDetailTablePageSize(20, 65)).toBe(65)
    expect(resolveExpandDetailTablePageSize(20, 20)).toBe(20)
    expect(resolveExpandDetailTablePageSize(20, 0)).toBe(20)
  })
})
