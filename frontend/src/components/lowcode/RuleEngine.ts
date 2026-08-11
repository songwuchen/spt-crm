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
      // form_editable=false：系统只读列（流水号、公式回填的区域经理等），对齐简道云 view 权限
      readonly: (field.props?.readonly as boolean) === true
        || field.form_editable === false
        || !!(field.props as { read_only?: boolean } | undefined)?.read_only,
      required: !!field.required,
    }
    for (const col of field.detail_table_columns || []) {
      states[col.id] = {
        masked: false,
        visible: (col.props?.hidden as boolean) !== true,
        readonly: (col.props?.readonly as boolean) === true
          || col.form_editable === false
          || !!(col.props as { read_only?: boolean } | undefined)?.read_only,
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
        // editable = 可填非必填（审批节点 field_perms）；勿沿用字段定义上的 required
        case 'editable':
          states[perm.fieldId].readonly = false
          states[perm.fieldId].required = false
          break
      }
    }
  }

  const targetsOf = (rule: FormRule): string[] =>
    rule.target_field_ids?.length ? rule.target_field_ids : rule.target_field_id ? [rule.target_field_id] : []

  const visRules = rules.filter(
    (r) => r.enabled !== false && r.type === 'visibility' && (r.action as { visible?: boolean }).visible !== undefined,
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

  // 被隐藏的字段一律非必填，避免静态 required + 显隐规则不同步时误拦
  for (const st of Object.values(states)) {
    if (!st.visible) st.required = false
  }

  for (const rule of rules) {
    if (rule.enabled === false || rule.type !== 'required') continue
    const want = (rule.action as { required?: boolean }).required !== false
    const match = evaluateCondition(rule.condition, values, subMap)
    for (const fieldId of targetsOf(rule)) {
      if (!states[fieldId]) continue
      if (!states[fieldId].visible) states[fieldId].required = false
      else states[fieldId].required = match ? want : !want
    }
  }

  for (const rule of rules) {
    if (rule.enabled === false || rule.type !== 'readonly') continue
    const want = (rule.action as { readonly?: boolean }).readonly !== false
    const match = evaluateCondition(rule.condition, values, subMap)
    for (const fieldId of targetsOf(rule)) if (states[fieldId]) states[fieldId].readonly = match ? want : !want
  }

  return states
}

/** 按给定 values 判断字段/明细列当前是否可见（供明细表按行显隐）。 */
export function isFieldVisibleByRules(
  fieldId: string,
  fields: FieldDefinition[],
  values: Record<string, unknown>,
  rules: FormRule[],
): boolean {
  const st = computeFieldStates(fields, values, rules)[fieldId]
  return !st || st.visible !== false
}

/** 明细列在某一行是否可见：把子表收成仅含该行再求值。 */
export function isDetailColVisibleInRow(
  colId: string,
  detailFieldId: string,
  row: Record<string, unknown>,
  formValues: Record<string, unknown>,
  fields: FieldDefinition[],
  rules: FormRule[],
): boolean {
  const scoped = { ...formValues, [detailFieldId]: [row] }
  return isFieldVisibleByRules(colId, fields, scoped, rules)
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
  // 简道云「是/否」与布尔互认
  const na = ynNorm(a)
  const nb = ynNorm(b)
  if (na !== null && nb !== null) return na === nb
  return String(a) === String(b)
}

function ynNorm(v: unknown): boolean | null {
  if (typeof v === 'boolean') return v
  if (typeof v === 'number' && (v === 0 || v === 1)) return v === 1
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase()
    if (['是', 'true', 'yes', 'y', '1'].includes(s)) return true
    if (['否', 'false', 'no', 'n', '0'].includes(s)) return false
  }
  return null
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
