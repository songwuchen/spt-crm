import { describe, expect, it } from 'vitest'
import {
  columnsToFieldSpecs,
  toCanonicalRows,
  recomputeLineRow,
  recomputePayRow,
  sumLineAmounts,
} from '@/components/ContractTerms'
import { FALLBACK_LINE_COLUMNS, FALLBACK_PAY_COLUMNS } from '@/constants/contractDetailTables'

describe('合同明细列（与目录对齐）', () => {
  it('FALLBACK 列 id 与简道云/目录一致', () => {
    expect(FALLBACK_LINE_COLUMNS.map((c) => c.id)).toEqual([
      'is_fx', 'product_type', 'name', 'spec', 'unit', 'qty',
      'fx_price', 'fx_rate', 'price', 'amount', 'fx_amount',
      'elec_ctrl', 'standard', 'line_remark',
    ])
    expect(FALLBACK_PAY_COLUMNS.map((c) => c.id)).toEqual([
      'due_date', 'kind', 'ratio', 'amount', 'remind', 'note',
    ])
  })

  it('columnsToFieldSpecs 映射 show_when / percent / computed', () => {
    const specs = columnsToFieldSpecs(FALLBACK_LINE_COLUMNS)
    const fx = specs.find((s) => s.key === 'fx_price')
    expect(fx?.showWhen).toEqual({ field: 'is_fx', equals: ['是'] })
    expect(specs.find((s) => s.key === 'amount')?.computed).toBe(true)
    const pay = columnsToFieldSpecs(FALLBACK_PAY_COLUMNS)
    expect(pay.find((s) => s.key === 'ratio')?.kind).toBe('pct')
    expect(pay.find((s) => s.key === 'amount')?.computed).toBe(true)
  })

  it('recomputePayRow：总金额 × 比例', () => {
    expect(recomputePayRow({ ratio: 0.3 }, 100000).amount).toBe(30000)
    expect(recomputePayRow({ ratio: 0.5 }, 200).amount).toBe(100)
  })

  it('toCanonicalRows 能吃旧 _widget_* 别名', () => {
    const rows = toCanonicalRows(
      [{ _widget_1561431500376: '筛机A', _widget_1561431500458: 2, name: null }],
      FALLBACK_LINE_COLUMNS,
    )
    expect(rows[0].name).toBe('筛机A')
    expect(rows[0].qty).toBe(2)
  })

  it('toCanonicalRows 保留设计器新增自定义列', () => {
    const rows = toCanonicalRows(
      [{ name: 'A', custom_col: '扩展' }],
      FALLBACK_LINE_COLUMNS,
    )
    expect(rows[0].custom_col).toBe('扩展')
  })

  it('recomputeLineRow 外币公式', () => {
    const row = recomputeLineRow({
      is_fx: '是', fx_price: 10, fx_rate: 7, qty: 2, price: 0,
    })
    expect(row.price).toBe(70)
    expect(row.amount).toBe(140)
    expect(row.fx_amount).toBe(20)
  })

  it('sumLineAmounts', () => {
    expect(sumLineAmounts([{ amount: 10 }, { amount: 20.5 }])).toBe(30.5)
  })
})
