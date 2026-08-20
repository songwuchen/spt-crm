import type { FieldDefinition, WfRoute } from '@/types/lowcode'

type CondLeaf = { field: string; operator: string; value?: unknown }

const OP_SHORT: Record<string, string> = {
  eq: '=', ne: '≠', in: '=', not_in: '≠',
  gt: '>', gte: '≥', lt: '<', lte: '≤',
  contains: '含', is_empty: '为空', is_not_empty: '不为空',
}

export function formatCondValue(v: unknown, field?: FieldDefinition): string {
  if (v == null || v === '') return ''
  if (typeof v === 'boolean') return v ? '是' : '否'
  const opts = field?.options || []
  const mapOne = (x: unknown) => {
    const s = String(x)
    const hit = opts.find((o) => String(o.value) === s)
    if (hit?.label) return hit.label
    if (/^[0-9a-f-]{20,}$/i.test(s)) return '…'
    return s.length > 10 ? `${s.slice(0, 8)}…` : s
  }
  if (Array.isArray(v)) {
    if (!v.length) return ''
    if (v.length === 1) return mapOne(v[0])
    if (v.length === 2) return `${mapOne(v[0])},${mapOne(v[1])}`
    return `${mapOne(v[0])}等${v.length}项`
  }
  return mapOne(v)
}

function leafCondText(leaf: CondLeaf, fields: FieldDefinition[]): string {
  if (!leaf.field || leaf.field === '__always') return ''
  const fd = fields.find((f) => f.id === leaf.field)
  const name = fd?.label || leaf.field
  const op = leaf.operator || 'eq'
  if (op === 'is_empty' || op === 'is_not_empty') {
    return `${name}${OP_SHORT[op] || op}`
  }
  const val = formatCondValue(leaf.value, fd)
  const sym = OP_SHORT[op] || op
  if (op === 'eq' || op === 'in') return val ? `${name}=${val}` : name
  if (op === 'ne' || op === 'not_in') return val ? `${name}≠${val}` : name
  return val ? `${name}${sym}${val}` : `${name}${sym}`
}

export function condLeaves(cond: WfRoute['condition']): CondLeaf[] {
  if (!cond) return []
  if (Array.isArray(cond.cond) && cond.cond.length) {
    return cond.cond.map((n) => ({
      field: n.field || '',
      operator: n.operator || 'eq',
      value: n.value,
    }))
  }
  const single = cond as { field?: string; operator?: string; value?: unknown }
  if (single.field) {
    return [{ field: single.field, operator: single.operator || 'eq', value: single.value }]
  }
  return []
}

/** 条件译成人话，如「是否是小萌=否 且 区域经理/组长不为空」 */
export function condHumanLabel(cond: WfRoute['condition'], fields: FieldDefinition[]): string {
  if (!cond) return '条件'
  const leaves = condLeaves(cond).filter((l) => l.field && l.field !== '__always')
  if (!leaves.length) {
    const raw = cond as { field?: string }
    if (raw.field === '__always') return ''
    return '条件'
  }
  const parts = leaves.map((l) => leafCondText(l, fields)).filter(Boolean)
  if (!parts.length) return '条件'
  const joiner = cond.rel === 'or' ? ' 或 ' : ' 且 '
  return parts.join(joiner)
}

export function truncateLabel(s: string, max = 24): { text: string; title: string } {
  if (s.length <= max) return { text: s, title: s }
  return { text: `${s.slice(0, max - 1)}…`, title: s }
}

/** 画布连线文案：可读条件 / else / 旁路；有激活序时带「序N」 */
export function routeEdgeLabel(
  route: WfRoute,
  all: WfRoute[],
  fields: FieldDefinition[] = [],
): { text: string; title: string } | undefined {
  const ord = typeof route.activate_order === 'number' ? `序${route.activate_order}` : ''
  const withOrd = (base: string) => {
    if (!base) return ord || undefined
    return ord ? `${base}·${ord}` : base
  }
  if (route.always) {
    if (route.condition) {
      const hum = condHumanLabel(route.condition, fields)
      return truncateLabel(withOrd(hum ? `旁路·${hum}` : '旁路·条件') || '旁路')
    }
    const t = withOrd('旁路')
    return t ? { text: t, title: t } : undefined
  }
  if (route.condition) {
    const hum = condHumanLabel(route.condition, fields)
    const raw = withOrd(hum || '条件')
    if (!raw) return undefined
    return truncateLabel(raw)
  }
  const siblings = all.filter((r) => r.source === route.source && !r.always && r.id !== route.id)
  if (route.exclusive_group || siblings.some((s) => !!s.condition || !!s.exclusive_group)) {
    const t = withOrd('else')
    return t ? { text: t, title: t } : undefined
  }
  return ord ? { text: ord, title: ord } : undefined
}

export function edgeStroke(route: WfRoute): string {
  if (route.always) return '#52c41a'
  if (route.condition) {
    const leaves = condLeaves(route.condition)
    if (leaves.length === 1 && leaves[0].field === '__always') return '#94a3b8'
    return '#7c3aed'
  }
  return '#94a3b8'
}
