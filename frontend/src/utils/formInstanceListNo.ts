import type { FieldDefinition, FormInstance } from '@/types/lowcode'

/** 列表「流水号」：serial_no / 收款号(payment_no) / 其它 auto_number，不用设计卡号顶替 */
export function recordListNo(r: FormInstance, fields: FieldDefinition[]): string {
  const data = r.form_data || {}
  if (data.serial_no != null && data.serial_no !== '') return String(data.serial_no)
  if (data.payment_no != null && data.payment_no !== '') return String(data.payment_no)
  const serialField = fields.find((f) => f.id === 'serial_no')
    || fields.find((f) => f.type === 'auto_number' && /流水号|收款号/.test(f.label || '') && !/设计卡/.test(f.label || ''))
  if (serialField) {
    const v = data[serialField.id]
    if (v != null && v !== '') return String(v)
  }
  if (r.business_no) {
    const card = data.design_card_no
    const drawing = data.drawing_no
    const biz = String(r.business_no)
    if (card != null && card !== '' && biz === String(card)) return '—'
    if (drawing != null && drawing !== '' && biz === String(drawing)) return '—'
    return r.business_no
  }
  return '—'
}
