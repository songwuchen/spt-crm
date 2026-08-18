/** 填报页轻量公式：明细行乘积（改数量/单价时）+ SUM($明细表.列#) 实时汇总。 */
import type { FieldDefinition } from '@/types/lowcode'

const SUM_DETAIL_RE = /^SUM\(\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*\)$/i
const ROW_MUL_RE = /^\$([a-zA-Z0-9_]+)#\s*\*\s*\$([a-zA-Z0-9_]+)#$/

function toNum(v: unknown): number | null {
  if (v == null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function round2(n: number): number {
  return Math.round((n + Number.EPSILON) * 100) / 100
}

function formulaOf(col: FieldDefinition): string {
  return String((col.props as { formula?: string } | undefined)?.formula || '').trim()
}

function productOf(row: Record<string, unknown>, a: string, b: string): number {
  return round2((toNum(row[a]) ?? 0) * (toNum(row[b]) ?? 0))
}

function productTargets(cols: FieldDefinition[]): Array<{ id: string; a: string; b: string }> {
  const out: Array<{ id: string; a: string; b: string }> = []
  const ids = new Set(cols.map((c) => c.id))
  for (const c of cols) {
    const m = formulaOf(c).match(ROW_MUL_RE)
    if (m) out.push({ id: c.id, a: m[1], b: m[2] })
  }
  if (ids.has('qty') && ids.has('unit_price') && ids.has('line_amount')
    && !out.some((t) => t.id === 'line_amount')) {
    out.push({ id: 'line_amount', a: 'qty', b: 'unit_price' })
  }
  return out
}

/**
 * 改数量/单价时重算合计；直接改合计则保留手填值。
 */
export function recomputeDetailRowOnColChange(
  row: Record<string, unknown>,
  cols: FieldDefinition[],
  changedColId: string,
): Record<string, unknown> {
  const targets = productTargets(cols)
  const hit = targets.filter((t) => t.a === changedColId || t.b === changedColId)
  if (!hit.length) return row
  const next = { ...row }
  for (const t of hit) next[t.id] = productOf(next, t.a, t.b)
  return next
}

function sumDetailCol(values: Record<string, unknown>, tableId: string, colId: string): number {
  const rows = values[tableId]
  if (!Array.isArray(rows)) return 0
  let total = 0
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    const n = Number((row as Record<string, unknown>)[colId])
    if (!Number.isNaN(n)) total += n
  }
  return round2(total)
}

/** 按字段定义重算可识别的公式字段；无变化时返回原对象。 */
export function applySimpleFormulas(
  fields: FieldDefinition[],
  values: Record<string, unknown>,
): Record<string, unknown> {
  let next: Record<string, unknown> | null = null
  for (const f of fields) {
    if (f.type !== 'formula') continue
    const formula = String((f.props as { formula?: string } | undefined)?.formula || '').trim()
    const m = formula.match(SUM_DETAIL_RE)
    if (!m) continue
    const computed = sumDetailCol(values, m[1], m[2])
    const cur = (next || values)[f.id]
    if (cur === computed) continue
    if (!next) next = { ...values }
    next[f.id] = computed
  }
  return next || values
}
