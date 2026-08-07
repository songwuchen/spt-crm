/** 低代码填报默认值（发起人/今日等），桌面与移动共用。 */
import dayjs from 'dayjs'
import type { FieldDefinition } from '@/types/lowcode'
import { dateFieldFormat } from '@/components/lowcode/dateField'

export function buildLowcodeInitialValues(
  fields: FieldDefinition[],
  currentUser?: { id?: string; real_name?: string; username?: string } | null,
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of fields) {
    if (f.type === 'detail_table') {
      if (Array.isArray(f.default_value) && f.default_value.length) {
        const meaningful = f.default_value.filter((row) => {
          if (!row || typeof row !== 'object') return false
          return Object.values(row as Record<string, unknown>).some(
            (v) => v != null && v !== '' && !(Array.isArray(v) && v.length === 0),
          )
        })
        if (meaningful.length) out[f.id] = meaningful
      }
      continue
    }
    if (f.default_value !== undefined && f.default_value !== null && f.default_value !== '') {
      out[f.id] = f.default_value
      continue
    }
    const props = (f.props || {}) as Record<string, unknown>
    if (props.default_today && (f.type === 'date' || f.type === 'datetime')) {
      out[f.id] = dayjs().format(dateFieldFormat(f))
      continue
    }
    if (props.default_current_user && (f.type === 'person' || f.type === 'person_multi') && currentUser?.id) {
      out[f.id] = f.type === 'person_multi' ? [currentUser.id] : currentUser.id
    }
  }
  return out
}
