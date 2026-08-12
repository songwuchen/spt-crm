/** 填报页轻量公式：支持 SUM($明细表.列#) 实时汇总（对齐后端 formula_engine）。 */
import type { FieldDefinition } from '@/types/lowcode'

const SUM_DETAIL_RE = /^SUM\(\s*\$([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)#\s*\)$/i

function sumDetailCol(values: Record<string, unknown>, tableId: string, colId: string): number {
  const rows = values[tableId]
  if (!Array.isArray(rows)) return 0
  let total = 0
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    const n = Number((row as Record<string, unknown>)[colId])
    if (!Number.isNaN(n)) total += n
  }
  return total
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
