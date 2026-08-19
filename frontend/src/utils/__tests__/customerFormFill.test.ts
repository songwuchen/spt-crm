import { describe, expect, it } from 'vitest'
import {
  clearCustomerFormFillPatch,
  isShipAddressField,
  needsCustomerFormFill,
  pickShipAddressFill,
  shipAddressFieldIds,
} from '../customerFormFill'

describe('customerFormFill', () => {
  it('detects ship address on cs_product_return field_6', () => {
    const fields = [
      { id: 'customer_name', type: 'customer' },
      { id: 'field_6', type: 'address', label: '货物地址' },
    ]
    expect(needsCustomerFormFill(fields)).toBe(true)
    expect(shipAddressFieldIds(fields)).toEqual(['field_6'])
  })

  it('detects ship address on cs_product_replace field_3', () => {
    const fields = [
      { id: 'customer_category', type: 'text' },
      { id: 'field_3', type: 'address', label: '货物地址' },
    ]
    expect(needsCustomerFormFill(fields)).toBe(true)
    expect(shipAddressFieldIds(fields)).toEqual(['field_3'])
  })

  it('picks only present address field from api fill', () => {
    const fields = [{ id: 'field_6', type: 'address', label: '货物地址' }]
    const fill = {
      customer_category: 'A',
      field_3: { province: '内蒙古', city: '包头', district: '昆都仑区', detail: 'x' },
      field_6: { province: '内蒙古', city: '包头', district: '昆都仑区', detail: 'x' },
    }
    expect(pickShipAddressFill(fields, fill)).toEqual({
      customer_category: 'A',
      field_6: fill.field_6,
    })
  })

  it('clears linked fields on customer reset', () => {
    const fields = [
      { id: 'customer_category', type: 'text' },
      { id: 'field_6', type: 'address', label: '货物地址' },
    ]
    expect(clearCustomerFormFillPatch(fields)).toEqual({
      customer_category: undefined,
      field_6: undefined,
    })
  })

  it('isShipAddressField matches label', () => {
    expect(isShipAddressField({ id: 'ship_to', type: 'address', label: '货物地址' })).toBe(true)
    expect(isShipAddressField({ id: 'field_6', type: 'text', label: '货物地址' })).toBe(false)
  })
})
