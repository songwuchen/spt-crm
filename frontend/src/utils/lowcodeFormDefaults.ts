/** 低代码填报默认值（发起人/今日等），桌面与移动共用。 */
import dayjs from 'dayjs'
import type { FieldDefinition } from '@/types/lowcode'
import { dateFieldFormat } from '@/components/lowcode/dateField'

function isEmptyValue(v: unknown): boolean {
  if (v == null) return true
  if (typeof v === 'string' && !v.trim()) return true
  if (Array.isArray(v) && v.length === 0) return true
  return false
}

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

/** 审批本节点填写：空值时补 default_today / default_value（如下单日期默认当天）。 */
export function applyApproveFieldDefaults(
  current: Record<string, unknown>,
  opts: {
    fieldIds?: string[]
    formFields?: FieldDefinition[]
    fieldMeta?: Array<{ id: string; type?: string; props?: Record<string, unknown> }>
  },
): Record<string, unknown> {
  const byId = new Map<string, FieldDefinition>()
  for (const f of opts.formFields || []) {
    if (f?.id) byId.set(f.id, f)
  }
  for (const m of opts.fieldMeta || []) {
    if (!m?.id) continue
    const base = byId.get(m.id)
    byId.set(m.id, {
      ...(base || { id: m.id, type: (m.type || 'text') as FieldDefinition['type'], label: m.id }),
      id: m.id,
      type: (m.type || base?.type || 'text') as FieldDefinition['type'],
      props: { ...(base?.props || {}), ...(m.props || {}) },
      label: base?.label || m.id,
    })
  }
  const ids = opts.fieldIds?.length ? opts.fieldIds : [...byId.keys()]
  const out = { ...current }
  for (const id of ids) {
    if (!isEmptyValue(out[id])) continue
    // 方案管理：下单日期即使旧快照缺 props 也默认当天
    const f = byId.get(id) || (
      id === 'order_date'
        ? { id, type: 'date' as const, label: '下单日期', props: { default_today: true, date_only: true } }
        : null
    )
    if (!f) continue
    const props = (f.props || {}) as Record<string, unknown>
    const wantToday = props.default_today || id === 'order_date'
    if (wantToday && (f.type === 'date' || f.type === 'datetime' || id === 'order_date')) {
      out[id] = dayjs().format(dateFieldFormat({
        ...f,
        type: f.type === 'datetime' ? 'datetime' : 'date',
        props: { date_only: true, show_time: false, ...(f.props || {}) },
      }))
    } else if (f.default_value !== undefined && f.default_value !== null && f.default_value !== '') {
      out[id] = f.default_value
    }
  }
  return out
}
