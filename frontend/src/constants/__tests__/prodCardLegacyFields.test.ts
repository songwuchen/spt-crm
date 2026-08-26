import { describe, expect, it } from 'vitest'
import { prodCardDetailShowsRowIndex } from '@/constants/prodCardLegacyFields'

describe('prodCardLegacyFields row index', () => {
  it('标准化室/电气车间子表显示序号列', () => {
    expect(prodCardDetailShowsRowIndex('std_room_fill')).toBe(true)
    expect(prodCardDetailShowsRowIndex('elec_workshop_fill')).toBe(true)
    expect(prodCardDetailShowsRowIndex('prod_card_line_items')).toBe(false)
  })
})
