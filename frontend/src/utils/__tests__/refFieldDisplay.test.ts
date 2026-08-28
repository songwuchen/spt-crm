import { describe, expect, it } from 'vitest'
import {
  customerReadonlyLabel,
  isRefUuid,
  MISSING_CUSTOMER_LABEL,
} from '@/utils/refFieldDisplay'

describe('refFieldDisplay', () => {
  it('detects uuid refs', () => {
    expect(isRefUuid('7d621b53-5b61-4a28-a4a2-d2fc65c4cc94')).toBe(true)
    expect(isRefUuid('河北安丰钢铁')).toBe(false)
  })

  it('shows plain name when value is not uuid', () => {
    expect(customerReadonlyLabel('河北安丰钢铁', undefined)).toBe('河北安丰钢铁')
  })

  it('shows friendly label when uuid unresolved', () => {
    expect(customerReadonlyLabel(
      '7d621b53-5b61-4a28-a4a2-d2fc65c4cc94',
      MISSING_CUSTOMER_LABEL,
    )).toBe(MISSING_CUSTOMER_LABEL)
  })

  it('shows resolved name for uuid', () => {
    expect(customerReadonlyLabel(
      '7d621b53-5b61-4a28-a4a2-d2fc65c4cc94',
      'Quote Test Customer',
    )).toBe('Quote Test Customer')
  })
})
