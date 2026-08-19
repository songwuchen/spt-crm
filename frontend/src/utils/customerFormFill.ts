import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

type FormFieldLite = { id?: string; type?: string; label?: string }

/** 简道云「货物地址」：更换 field_3、退回 field_6（同 widget） */
export function isShipAddressField(f: FormFieldLite): boolean {
  if (f.type !== 'address') return false
  if (f.id === 'field_3' || f.id === 'field_6') return true
  return (f.label || '').includes('货物地址')
}

export function shipAddressFieldIds(fields: FormFieldLite[]): string[] {
  return fields.filter(isShipAddressField).map((f) => f.id!).filter(Boolean)
}

/** 选客户后联动：客户类别（客户信息·客户类型 A/B/C/D）+ 货物地址 */
export async function fetchCustomerFormFill(
  customerId: string,
): Promise<Record<string, unknown>> {
  if (!customerId) return {}
  try {
    const res = await client.get<unknown, ApiResponse<Record<string, unknown>>>(
      `/api/v1/lc/customer-form-fill/${customerId}`,
      { headers: { 'X-Silent-Error': '1' } },
    )
    return res.data || {}
  } catch {
    return {}
  }
}

/** 表单是否含简道云式客户联动字段 */
export function needsCustomerFormFill(fields: FormFieldLite[]): boolean {
  const hasCategory = fields.some((f) => f.id === 'customer_category')
  return hasCategory || shipAddressFieldIds(fields).length > 0
}

/** 清空客户联动回填字段 */
export function clearCustomerFormFillPatch(fields: FormFieldLite[]): Record<string, unknown> {
  const patch: Record<string, unknown> = { customer_category: undefined }
  for (const id of shipAddressFieldIds(fields)) {
    patch[id] = undefined
  }
  return patch
}

/** 只保留当前表单存在的货物地址字段 */
export function pickShipAddressFill(
  fields: FormFieldLite[],
  fill: Record<string, unknown>,
): Record<string, unknown> {
  const ids = new Set(shipAddressFieldIds(fields))
  const out: Record<string, unknown> = {}
  if ('customer_category' in fill) out.customer_category = fill.customer_category
  for (const id of ids) {
    if (id in fill) out[id] = fill[id]
  }
  return out
}
