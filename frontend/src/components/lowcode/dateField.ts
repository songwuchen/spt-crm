/** 低代码日期/日期时间字段的展示与落库格式（通用）。 */
import type { FieldDefinition } from '@/types/lowcode'

/** 是否需要选择到时分秒。`date` 恒为否；`datetime` 可用 props.show_time=false 降为仅日期。 */
export function fieldShowsTime(field: Pick<FieldDefinition, 'type' | 'props'>): boolean {
  if (field.type === 'date') return false
  if (field.type !== 'datetime') return false
  const p = field.props as Record<string, unknown> | undefined
  if (p?.show_time === false || p?.date_only === true) return false
  return true
}

export function dateFieldFormat(field: Pick<FieldDefinition, 'type' | 'props'>): string {
  return fieldShowsTime(field) ? 'YYYY-MM-DD HH:mm:ss' : 'YYYY-MM-DD'
}

export function dateFieldDisplayFormat(field: Pick<FieldDefinition, 'type' | 'props'>): string {
  return fieldShowsTime(field) ? 'YYYY-MM-DD HH:mm' : 'YYYY-MM-DD'
}
