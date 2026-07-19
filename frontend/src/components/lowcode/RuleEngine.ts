// 表单规则引擎(显隐/只读/必填 + 嵌套条件组 + 子表任一行 + 级联隐藏)。
// 移植自 spt-lowcode components/FormRenderer/RuleEngine.ts。
import type {
  FieldDefinition, FieldPermission, FormRule, RuleCondition, RuleConditionNode, FieldState,
} from '@/types/lowcode'
import { isConditionGroup } from '@/types/lowcode'

function buildSubFieldMap(fields: FieldDefinition[]): Record<string, string> {
  const map: Record<string, string> = {}
  for (const f of fields) {
    if (f.detail_table_columns?.length) {
      for (const col of f.detail_table_columns) map[col.id] = f.id
    }
  }
  return map
}

export function computeFieldStates(
  fields: FieldDefinition[],
  values: Record<string, unknown>,
  rules: FormRule[],
  permissions?: FieldPermission[],
): Record<string, FieldState> {
  const states: Record<string, FieldState> = {}
  const subMap = buildSubFieldMap(fields)

  for (const field of fields) {
    states[field.id] = {
      masked: false,
      visible: (field.props?.hidden as boolean) !== true,
      readonly: (field.props?.readonly as boolean) === true,
      required: !!field.required,
    }
    for (const col of field.detail_table_columns || []) {
      states[col.id] = {
        masked: false,
        visible: (col.props?.hidden as boolean) !== true,
        readonly: (col.props?.readonly as boolean) === true,
        required: !!col.required,
      }
    }
  }

  if (permissions) {
    for (const perm of permissions) {
      if (!states[perm.fieldId]) continue
      switch (perm.access) {
        case 'hidden': states[perm.fieldId].visible = false; break
        // 脱敏：仍显示但只给 "***"，且一律不可编辑
        case 'masked': states[perm.fieldId].masked = true; states[perm.fieldId].readonly = true; break
        case 'readonly': states[perm.fieldId].readonly = true; break
        case 'required': states[perm.fieldId].required = true; break
        case 'editable': states[perm.fieldId].readonly = false; break
      }
    }
  }

  const targetsOf = (rule: FormRule): string[] =>
    rule.target_field_ids?.length ? rule.target_field_ids : rule.target_field_id ? [rule.target_field_id] : []

  const visRules = rules.filter(
    (r) => r.type === 'visibility' && (r.action as { visible?: boolean }).visible !== undefined,
  )
  if (visRules.length) {
    let hidden = new Set<string>()
    const cap = Math.min(visRules.length + 2, 50)
    for (let iter = 0; iter < cap; iter++) {
      const vis: Record<string, boolean> = {}
      for (const rule of visRules) {
        const want = (rule.action as { visible?: boolean }).visible as boolean
        const match = evaluateCondition(rule.condition, values, subMap, hidden)
        for (const fieldId of targetsOf(rule)) if (states[fieldId]) vis[fieldId] = match ? want : !want
      }
      const next = new Set<string>()
      for (const [fid, v] of Object.entries(vis)) if (!v) next.add(fid)
      const stable = next.size === hidden.size && [...next].every((x) => hidden.has(x))
      if (stable || iter === cap - 1) {
        for (const [fid, v] of Object.entries(vis)) states[fid].visible = v
        break
      }
      hidden = next
    }
  }

  for (const rule of rules) {
    if (rule.type !== 'required') continue
    const want = (rule.action as { required?: boolean }).required !== false
    const match = evaluateCondition(rule.condition, values, subMap)
    for (const fieldId of targetsOf(rule)) if (states[fieldId]) states[fieldId].required = match ? want : !want
  }

  for (const rule of rules) {
    if (rule.type !== 'readonly') continue
    const want = (rule.action as { readonly?: boolean }).readonly !== false
    const match = evaluateCondition(rule.condition, values, subMap)
    for (const fieldId of targetsOf(rule)) if (states[fieldId]) states[fieldId].readonly = match ? want : !want
  }

  return states
}

const EMPTY_HIDDEN: ReadonlySet<string> = new Set()

function evaluateCondition(condition: RuleCondition, values: Record<string, unknown>, subMap: Record<string, string>, hidden: ReadonlySet<string> = EMPTY_HIDDEN): boolean {
  if (condition.cond && condition.cond.length > 0) return evalGroup(condition.rel || 'and', condition.cond, values, subMap, hidden)
  if (condition.field && condition.operator) return evaluateSingle(condition.field, condition.operator, condition.value, values, subMap, hidden)
  return false
}

function evalNode(node: RuleConditionNode, values: Record<string, unknown>, subMap: Record<string, string>, hidden: ReadonlySet<string>): boolean {
  if (isConditionGroup(node)) return evalGroup(node.rel || 'and', node.cond, values, subMap, hidden)
  if (!node.field || !node.operator) return false
  return evaluateSingle(node.field, node.operator, node.value, values, subMap, hidden)
}

function evalGroup(rel: 'and' | 'or', cond: RuleConditionNode[], values: Record<string, unknown>, subMap: Record<string, string>, hidden: ReadonlySet<string>): boolean {
  if (cond.length === 0) return rel === 'and'
  return rel === 'and' ? cond.every((c) => evalNode(c, values, subMap, hidden)) : cond.some((c) => evalNode(c, values, subMap, hidden))
}

function getActuals(field: string, values: Record<string, unknown>, subMap: Record<string, string>): unknown[] {
  const parent = subMap[field]
  if (parent) {
    const rows = values[parent]
    if (!Array.isArray(rows) || rows.length === 0) return [undefined]
    return rows.map((r) => (r && typeof r === 'object' ? (r as Record<string, unknown>)[field] : undefined))
  }
  return [values[field]]
}

function evaluateSingle(field: string, operator: string, expected: unknown, values: Record<string, unknown>, subMap: Record<string, string>, hidden: ReadonlySet<string> = EMPTY_HIDDEN): boolean {
  if (hidden.has(field) || hidden.has(subMap[field])) return false
  return getActuals(field, values, subMap).some((actual) => testOp(actual, operator, expected))
}

function looseEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true
  if (a == null && b == null) return true
  if (a == null || b == null) return false
  if (Array.isArray(a) && Array.isArray(b)) return JSON.stringify([...a].sort()) === JSON.stringify([...b].sort())
  return String(a) === String(b)
}

function isEmpty(val: unknown): boolean {
  if (val === null || val === undefined || val === '') return true
  if (Array.isArray(val) && val.length === 0) return true
  return false
}

function compareVals(a: unknown, b: unknown): number {
  const na = Number(a), nb = Number(b)
  if (a !== '' && b !== '' && !Number.isNaN(na) && !Number.isNaN(nb)) return na < nb ? -1 : na > nb ? 1 : 0
  const sa = String(a), sb = String(b)
  return sa < sb ? -1 : sa > sb ? 1 : 0
}

function testOp(actual: unknown, operator: string, expected: unknown): boolean {
  switch (operator) {
    case 'eq': return looseEqual(actual, expected)
    case 'ne': return !looseEqual(actual, expected)
    case 'is_empty': return isEmpty(actual)
    case 'is_not_empty': return !isEmpty(actual)
    case 'gt': return actual != null && actual !== '' && compareVals(actual, expected) > 0
    case 'gte': return actual != null && actual !== '' && compareVals(actual, expected) >= 0
    case 'lt': return actual != null && actual !== '' && compareVals(actual, expected) < 0
    case 'lte': return actual != null && actual !== '' && compareVals(actual, expected) <= 0
    case 'in': {
      const list = Array.isArray(expected) ? expected : String(expected ?? '').split(',').map((s) => s.trim()).filter(Boolean)
      if (Array.isArray(actual)) return actual.some((v) => list.some((e) => looseEqual(v, e)))
      return list.some((e) => looseEqual(actual, e))
    }
    case 'not_in': {
      const list = Array.isArray(expected) ? expected : String(expected ?? '').split(',').map((s) => s.trim()).filter(Boolean)
      if (Array.isArray(actual)) return !actual.some((v) => list.some((e) => looseEqual(v, e)))
      return !list.some((e) => looseEqual(actual, e))
    }
    case 'contains': {
      if (Array.isArray(actual)) return actual.some((v) => looseEqual(v, expected))
      return String(actual ?? '').includes(String(expected ?? ''))
    }
    case 'not_contains': {
      if (Array.isArray(actual)) return !actual.some((v) => looseEqual(v, expected))
      return !String(actual ?? '').includes(String(expected ?? ''))
    }
    case 'starts_with': return String(actual ?? '').startsWith(String(expected ?? ''))
    case 'ends_with': return String(actual ?? '').endsWith(String(expected ?? ''))
    default: return false
  }
}
