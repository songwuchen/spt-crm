import { describe, expect, it } from 'vitest'
import { FALLBACK_LINE_COLUMNS, validateContractLineRows } from '@/constants/contractDetailTables'

describe('validateContractLineRows', () => {
  it('requires at least one detail row on submit', () => {
    expect(validateContractLineRows([{}], FALLBACK_LINE_COLUMNS)).toBe('请填写合同明细')
  })

  it('requires marked columns in each row', () => {
    const err = validateContractLineRows(
      [{ is_fx: '否', product_type: '复频筛', name: '筛', spec: 'X', unit: '台', qty: 1 }],
      FALLBACK_LINE_COLUMNS,
    )
    expect(err).toMatch(/单价/)
  })

  it('requires fx columns when is_fx is 是', () => {
    const err = validateContractLineRows(
      [{ is_fx: '是', product_type: '复频筛', name: '筛', spec: 'X', unit: '台', qty: 1, price: 100 }],
      FALLBACK_LINE_COLUMNS,
    )
    expect(err).toMatch(/外币单价|汇率/)
  })

  it('passes when required columns are filled', () => {
    expect(validateContractLineRows(
      [{ is_fx: '否', product_type: '复频筛', name: '筛', spec: 'X', unit: '台', qty: 1, price: 100 }],
      FALLBACK_LINE_COLUMNS,
    )).toBeNull()
  })
})
