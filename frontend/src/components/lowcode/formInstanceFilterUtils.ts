/**
 * 表单列表筛选：规则校验 + localStorage 记忆（仅在有条件项时写入）。
 */
import type { FieldDefinition } from '@/types/lowcode'

export type FormFilterRule = { field: string; op: string; value?: unknown }
export type FormFilterDsl = { match: 'all' | 'any'; rules: FormFilterRule[] }

/** 主表 + 明细子表列（与后端 FILTERABLE_FIELD_TYPES / expand_filterable_form_fields 对齐） */
export const FILTERABLE_FIELD_TYPES = new Set([
  'text', 'textarea', 'auto_number', 'number', 'amount',
  'select', 'radio', 'date', 'datetime',
  'person', 'department', 'project', 'contract', 'customer',
])

export function expandFilterableFormFields(fields: FieldDefinition[]): FieldDefinition[] {
  const labelCount = new Map<string, number>()
  for (const f of fields) {
    if (f.type !== 'detail_table') continue
    for (const col of f.detail_table_columns || []) {
      if (col?.label) labelCount.set(col.label, (labelCount.get(col.label) || 0) + 1)
    }
  }
  const out: FieldDefinition[] = []
  const seen = new Set<string>()
  const push = (f: FieldDefinition) => {
    if (!f.id || seen.has(f.id) || !FILTERABLE_FIELD_TYPES.has(f.type)) return
    seen.add(f.id)
    out.push(f)
  }
  for (const f of fields) {
    if (f.type === 'detail_table') {
      const parent = f.label || f.id || '明细'
      for (const col of f.detail_table_columns || []) {
        if (!col?.id || seen.has(col.id) || !FILTERABLE_FIELD_TYPES.has(col.type)) continue
        const label = (labelCount.get(col.label) || 0) > 1 ? `${parent}·${col.label}` : col.label
        push({ ...col, label })
      }
      continue
    }
    push(f)
  }
  return out
}

const APPLIED_PREFIX = 'spt_formlist_filters_v1_'
const DRAFT_PREFIX = 'spt_formlist_filters_draft_v1_'

export function needsFilterValue(op: string): boolean {
  return op !== 'is_empty' && op !== 'is_not_empty'
}

export function ruleValid(r: FormFilterRule): boolean {
  if (!r.field || !r.op) return false
  if (!needsFilterValue(r.op)) return true
  if (r.op === 'between') {
    return Array.isArray(r.value) && r.value.length >= 2 && r.value[0] != null && r.value[1] != null
      && r.value[0] !== '' && r.value[1] !== ''
  }
  if (r.op === 'in') {
    return Array.isArray(r.value) ? r.value.length > 0 : !!r.value
  }
  return r.value !== undefined && r.value !== null && r.value !== ''
}

/** 至少选了字段+运算符，才算「有条件项」（可记草稿）。 */
export function ruleHasItem(r: FormFilterRule): boolean {
  return !!(r.field && r.op)
}

export function normalizeFilterDsl(dsl: FormFilterDsl | null | undefined): FormFilterDsl | null {
  if (!dsl?.rules?.length) return null
  const rules = dsl.rules.filter(ruleValid)
  if (!rules.length) return null
  return { match: dsl.match === 'any' ? 'any' : 'all', rules }
}

export function normalizeDraftDsl(dsl: FormFilterDsl | null | undefined): FormFilterDsl | null {
  if (!dsl?.rules?.length) return null
  const rules = dsl.rules.filter(ruleHasItem)
  if (!rules.length) return null
  return { match: dsl.match === 'any' ? 'any' : 'all', rules }
}

function storageKey(prefix: string, key: string) {
  return prefix + key
}

function readDsl(raw: string | null): FormFilterDsl | null {
  if (!raw) return null
  try {
    return JSON.parse(raw) as FormFilterDsl
  } catch {
    return null
  }
}

export function loadAppliedFilters(key: string): FormFilterDsl | null {
  try {
    return normalizeFilterDsl(readDsl(localStorage.getItem(storageKey(APPLIED_PREFIX, key))))
  } catch {
    return null
  }
}

export function saveAppliedFilters(key: string, dsl: FormFilterDsl | null) {
  try {
    const norm = normalizeFilterDsl(dsl)
    const sk = storageKey(APPLIED_PREFIX, key)
    if (norm) localStorage.setItem(sk, JSON.stringify(norm))
    else localStorage.removeItem(sk)
  } catch { /* ignore */ }
}

export function loadDraftFilters(key: string): FormFilterDsl | null {
  try {
    return normalizeDraftDsl(readDsl(localStorage.getItem(storageKey(DRAFT_PREFIX, key))))
  } catch {
    return null
  }
}

export function saveDraftFilters(key: string, dsl: FormFilterDsl | null) {
  try {
    const norm = normalizeDraftDsl(dsl)
    const sk = storageKey(DRAFT_PREFIX, key)
    if (norm) localStorage.setItem(sk, JSON.stringify(norm))
    else localStorage.removeItem(sk)
  } catch { /* ignore */ }
}

export function clearFilterMemory(key: string) {
  try {
    localStorage.removeItem(storageKey(APPLIED_PREFIX, key))
    localStorage.removeItem(storageKey(DRAFT_PREFIX, key))
  } catch { /* ignore */ }
}
