import { describe, expect, it } from 'vitest'
import type { FieldDefinition } from '@/types/lowcode'
import { evaluateSubmitValidations } from '@/utils/submitValidations'

const fields: FieldDefinition[] = [
  {
    id: 'payment_details',
    type: 'detail_table',
    label: '来款明细',
    detail_table_columns: [{ id: 'amount', type: 'number', label: '金额' }],
  },
  {
    id: 'payment_total',
    type: 'formula',
    label: '来款合计',
    props: { formula: 'SUM($payment_details.amount#)' },
  },
  {
    id: 'payment_allocation',
    type: 'detail_table',
    label: '款项分配',
    detail_table_columns: [{ id: 'alloc_amount', type: 'number', label: '分配金额' }],
  },
  {
    id: 'alloc_total',
    type: 'formula',
    label: '分配金额合计',
    props: { formula: 'SUM($payment_allocation.alloc_amount#)' },
  },
]

describe('evaluateSubmitValidations', () => {
  it('passes when alloc total equals payment total', () => {
    const err = evaluateSubmitValidations(
      [{ formula: '$alloc_total#-$payment_total#==0', message: '不一致' }],
      fields,
      {
        payment_details: [{ amount: 100 }, { amount: 50 }],
        payment_allocation: [{ alloc_amount: 80 }, { alloc_amount: 70 }],
      },
    )
    expect(err).toBeNull()
  })

  it('blocks when totals differ', () => {
    const err = evaluateSubmitValidations(
      [{ formula: '$alloc_total#-$payment_total#==0', message: '请确保相等' }],
      fields,
      {
        payment_details: [{ amount: 100 }],
        payment_allocation: [{ alloc_amount: 90 }],
      },
    )
    expect(err).toBe('请确保相等')
  })
})
