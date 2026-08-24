import { describe, expect, it } from 'vitest'
import {
  applyProdCardOrderTypeMerged,
  applySimpleFormulas,
  recomputeDetailRowOnColChange,
} from '@/utils/lowcodeSimpleFormulas'
import type { FieldDefinition } from '@/types/lowcode'

const cols: FieldDefinition[] = [
  { id: 'qty', type: 'number', label: '数量' },
  { id: 'unit_price', type: 'number', label: '单价' },
  { id: 'line_amount', type: 'number', label: '合计' },
]

const invoiceFields: FieldDefinition[] = [
  {
    id: 'contract_lines_new',
    type: 'detail_table',
    label: '合同明细',
    detail_table_columns: cols,
  },
  {
    id: 'total_amount',
    type: 'formula',
    label: '总价合计',
    props: { formula: 'SUM($contract_lines_new.line_amount#)' },
  },
]

describe('明细合计可手改', () => {
  it('改数量/单价时重算合计', () => {
    const row = recomputeDetailRowOnColChange(
      { qty: 0.6, unit_price: 1140000, line_amount: 1 },
      cols,
      'qty',
    )
    expect(row.line_amount).toBe(684000)
  })

  it('直接改合计时保留手填值', () => {
    const row = recomputeDetailRowOnColChange(
      { qty: 0.6, unit_price: 1140000, line_amount: 700000 },
      cols,
      'line_amount',
    )
    expect(row.line_amount).toBe(700000)
  })

  it('手改合计后总价跟着汇总', () => {
    const next = applySimpleFormulas(invoiceFields, {
      contract_lines_new: [{ qty: 0.6, unit_price: 1140000, line_amount: 700000 }],
    })
    expect((next.contract_lines_new as { line_amount: number }[])[0].line_amount).toBe(700000)
    expect(next.total_amount).toBe(700000)
  })
})

describe('生产卡下单类型（合并含补充）', () => {
  const fields: FieldDefinition[] = [
    {
      id: 'field',
      type: 'text',
      label: '下单类型（合并含补充）',
      props: { suggest_formula: "IF($is_supplement#=='是','补充',$order_type#)" },
    },
  ]

  it('非补充时等于下单类型', () => {
    const next = applySimpleFormulas(fields, { is_supplement: '否', order_type: '备件' })
    expect(next.field).toBe('备件')
  })

  it('补充时为「补充」', () => {
    const next = applySimpleFormulas(fields, { is_supplement: '是', order_type: '设备' })
    expect(next.field).toBe('补充')
  })

  it('手改 field 时不被联动覆盖', () => {
    const next = applyProdCardOrderTypeMerged(
      { is_supplement: '否', order_type: '备件', field: '自定义' },
      { skipField: true },
    )
    expect(next.field).toBe('自定义')
  })
})

describe('字段加减公式', () => {
  it('多轮重算：累计=历史+本次，未发货=合同−累计', () => {
    const fields: FieldDefinition[] = [
      {
        id: 'ship_amount',
        type: 'formula',
        label: '发货金额',
        props: { formula: 'SUM($ship_lines.line_amount#)' },
      },
      {
        id: 'shipped_amount_incl',
        type: 'formula',
        label: '累计',
        props: { formula: '$prior_shipped_amount#+$ship_amount#' },
      },
      {
        id: 'unshipped_amount',
        type: 'formula',
        label: '未发货',
        props: { formula: '$contract_amount#-$shipped_amount_incl#' },
      },
    ]
    const next = applySimpleFormulas(fields, {
      ship_lines: [{ line_amount: 8748 }],
      prior_shipped_amount: 12000,
      contract_amount: 128000.5,
    })
    expect(next.ship_amount).toBe(8748)
    expect(next.shipped_amount_incl).toBe(20748)
    expect(next.unshipped_amount).toBe(107252.5)
  })
})
