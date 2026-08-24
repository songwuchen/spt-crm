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

/** 明细子表新行：按列 props 写入 default_today / default_value 等。 */
export function buildDetailRowDefaults(cols: FieldDefinition[] = []): Record<string, unknown> {
  const row: Record<string, unknown> = {}
  for (const col of cols) {
    if (col.default_value !== undefined && col.default_value !== null && col.default_value !== '') {
      row[col.id] = col.default_value
      continue
    }
    const props = (col.props || {}) as Record<string, unknown>
    if (props.default_today && (col.type === 'date' || col.type === 'datetime')) {
      row[col.id] = dayjs().format(dateFieldFormat(col))
    }
  }
  return row
}

/** 已有明细行：空单元格补列默认值（不覆盖已填值）。 */
export function applyDetailRowDefaults(
  rows: Record<string, unknown>[],
  cols: FieldDefinition[] = [],
): Record<string, unknown>[] {
  if (!cols.length || !rows.length) return rows
  return rows.map((row) => {
    const defaults = buildDetailRowDefaults(cols)
    const out = { ...(row && typeof row === 'object' ? row : {}) }
    for (const [k, v] of Object.entries(defaults)) {
      if (isEmptyValue(out[k])) out[k] = v
    }
    return out
  })
}

export function buildLowcodeInitialValues(
  fields: FieldDefinition[],
  currentUser?: {
    id?: string
    real_name?: string
    username?: string
    department_id?: string
    department_ids?: string[]
  } | null,
): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  const primaryDept = currentUser?.department_id
    || (currentUser?.department_ids && currentUser.department_ids[0])
    || undefined
  for (const f of fields) {
    if (f.type === 'detail_table') {
      if (Array.isArray(f.default_value) && f.default_value.length) {
        const meaningful = f.default_value.filter((row) => {
          if (!row || typeof row !== 'object') return false
          return Object.values(row as Record<string, unknown>).some(
            (v) => v != null && v !== '' && !(Array.isArray(v) && v.length === 0),
          )
        })
        if (meaningful.length) {
          out[f.id] = meaningful
          continue
        }
      }
      // 对齐简道云：出方案图明细等默认带一行空记录，避免「请填写至少一条」却看不到行
      const ensureMin = Math.max(0, Number((f.props as { ensure_min_rows?: number } | undefined)?.ensure_min_rows ?? 0) || 0)
      if (ensureMin > 0) {
        const cols = f.detail_table_columns || []
        out[f.id] = Array.from({ length: ensureMin }, () => buildDetailRowDefaults(cols))
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
      continue
    }
    if (props.default_current_dept && (f.type === 'department' || f.type === 'department_multi') && primaryDept) {
      out[f.id] = f.type === 'department_multi' ? [primaryDept] : primaryDept
    }
  }
  return out
}

/** 审批本节点填写：下单日期等强制为处理当天；其它空值补 default_today / default_value。 */
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
    // 方案管理/安装图：下单日期=本审批节点处理当天（设计指派安排等），非发起日
    const f = byId.get(id) || (
      id === 'order_date'
        ? { id, type: 'date' as const, label: '下单日期', props: { default_today_on_approve: true, date_only: true } }
        : null
    )
    if (!f) continue
    if (f.type === 'detail_table') {
      const cols = f.detail_table_columns || []
      const raw = out[id]
      if (Array.isArray(raw) && raw.length) {
        out[id] = applyDetailRowDefaults(raw as Record<string, unknown>[], cols)
      }
      continue
    }
    const props = (f.props || {}) as Record<string, unknown>
    const wantTodayOnApprove = id === 'order_date' || id === 'order_datetime' || props.default_today_on_approve === true
    if (wantTodayOnApprove && (f.type === 'date' || f.type === 'datetime' || id === 'order_date')) {
      out[id] = dayjs().format(dateFieldFormat({
        ...f,
        type: f.type === 'datetime' ? 'datetime' : 'date',
        props: { date_only: true, show_time: false, ...(f.props || {}) },
      }))
      continue
    }
    if (!isEmptyValue(out[id])) continue
    if (props.default_today && (f.type === 'date' || f.type === 'datetime')) {
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
