import { describe, it, expect } from 'vitest'

describe('Test framework', () => {
  it('should run basic assertions', () => {
    expect(1 + 1).toBe(2)
    expect(true).toBeTruthy()
    expect([1, 2, 3]).toHaveLength(3)
  })

  it('should handle async', async () => {
    const result = await Promise.resolve('ok')
    expect(result).toBe('ok')
  })
})
