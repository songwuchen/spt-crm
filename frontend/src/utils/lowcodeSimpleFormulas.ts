/** 填报页轻量公式：明细行乘积 + SUM($明细表.列#) + $a#±$b# 实时汇总。 */
import type { FieldDefinition } from '@/types/lowcode'

const SUM_DETAIL_RE = /^SUM\(\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*\)$/i
const ROW_MUL_RE = /^\$([a-zA-Z0-9_]+)#\s*\*\s*\$([a-zA-Z0-9_]+)#$/
const BINARY_FIELD_RE = /^\$([a-zA-Z0-9_]+)#\s*([+\-])\s*\$([a-zA-Z0-9_]+)#$/

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

function evalBinary(values: Record<string, unknown>, left: string, op: string, right: string): number {
  const a = toNum(values[left]) ?? 0
  const b = toNum(values[right]) ?? 0
  return round2(op === '-' ? a - b : a + b)
}

/** 按字段定义重算可识别的公式字段；无变化时返回原对象。 */
export function applySimpleFormulas(
  fields: FieldDefinition[],
  values: Record<string, unknown>,
): Record<string, unknown> {
  let next = values
  // 多轮：SUM → 加减依赖（如累计=历史+本次、未发货=合同−累计）
  for (let pass = 0; pass < 4; pass += 1) {
    let changed = false
    const base = next
    for (const f of fields) {
      if (f.type !== 'formula') continue
      const formula = String((f.props as { formula?: string } | undefined)?.formula || '').trim()
      let computed: number | null = null
      const sum = formula.match(SUM_DETAIL_RE)
      if (sum) {
        computed = sumDetailCol(base, sum[1], sum[2])
      } else {
        const bin = formula.match(BINARY_FIELD_RE)
        if (bin) computed = evalBinary(base, bin[1], bin[2], bin[3])
      }
      if (computed == null) continue
      if (base[f.id] === computed) continue
      if (next === values || next === base) next = { ...base }
      next[f.id] = computed
      changed = true
    }
    if (!changed) break
  }
  return next
}
