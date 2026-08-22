import type { FieldDefinition } from '@/types/lowcode'

/** 可作为「业务员」来源、触发区域经理对照回填的字段 id */
export const SALESPERSON_FIELD_IDS = new Set([
  'sales_person',
  'salesperson',
  'owner_id',
  'no_sales_person',
  'yes_sales_person',
])

export function isSalespersonField(f: FieldDefinition): boolean {
  return f.type === 'person'
    && (SALESPERSON_FIELD_IDS.has(f.id) || f.label === '业务员')
}

export function isRegionManagerField(f: FieldDefinition): boolean {
  return f.type === 'person'
    && (f.id === 'region_manager' || f.id === 'region_manager_id'
      || (f.label || '').includes('区域经理'))
}

export function parsePersonFieldId(raw: unknown): string {
  if (raw == null || raw === '') return ''
  if (typeof raw === 'object' && raw !== null && 'id' in (raw as object)) {
    return String((raw as { id?: string }).id || '').trim()
  }
  return String(raw).trim()
}
