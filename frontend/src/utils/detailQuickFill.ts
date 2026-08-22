import type { FieldSpec } from '@/components/ContractTerms'

type Row = Record<string, unknown>

/** 快速填报可编辑列：排除计算列 */
export function getPasteableFields(fields: FieldSpec[]): FieldSpec[] {
  return fields.filter((f) => !f.computed)
}

export function parseClipboardText(text: string): string[][] {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n')
  const rows: string[][] = []
  for (const line of lines) {
    if (!line.trim()) continue
    rows.push(line.split('\t').map((c) => c.trim()))
  }
  return rows
}

function norm(s: string): string {
  return s.trim().toLowerCase()
}

function matchOption(raw: string, options?: { value: string; label: string }[]): string | null {
  if (!raw.trim()) return null
  if (!options?.length) return raw.trim()
  const hit = options.find((o) => norm(o.value) === norm(raw) || norm(o.label) === norm(raw))
  return hit ? hit.value : raw.trim()
}

export function coerceCellValue(field: FieldSpec, raw: string): unknown {
  const s = raw.trim()
  if (!s) return null
  if (field.kind === 'radio' || field.kind === 'select') {
    return matchOption(s, field.options)
  }
  if (field.kind === 'number' || field.kind === 'money' || field.kind === 'pct') {
    const n = Number(s.replace(/,/g, '').replace(/%/g, ''))
    if (!Number.isFinite(n)) return null
    if (field.kind === 'pct') return n > 1 ? n / 100 : n
    return n
  }
  return s
}

export function emptyGridRows(cols: number, rows = 8): string[][] {
  return Array.from({ length: rows }, () => Array.from({ length: cols }, () => ''))
}

export function rowsToGrid(rows: Row[], fields: FieldSpec[]): string[][] {
  if (!rows.length) return emptyGridRows(fields.length)
  return rows.map((row) => fields.map((f) => {
    const v = row[f.key]
    if (v == null || v === '') return ''
    if (f.kind === 'pct' && typeof v === 'number') return String(+(v * 100).toFixed(4).replace(/\.?0+$/, ''))
    return String(v)
  }))
}

export function gridToRows(grid: string[][], fields: FieldSpec[]): Row[] {
  const out: Row[] = []
  for (const cells of grid) {
    const row: Row = {}
    let hasValue = false
    fields.forEach((f, i) => {
      const raw = cells[i] ?? ''
      if (!raw.trim()) return
      const val = coerceCellValue(f, raw)
      if (val != null && val !== '') {
        row[f.key] = val
        hasValue = true
      }
    })
    if (hasValue) out.push(row)
  }
  return out
}

export interface QuickFillIssue {
  row: number
  field: string
  label: string
  message: string
}

export function validateQuickFillRows(rows: Row[], allFields: FieldSpec[]): QuickFillIssue[] {
  const issues: QuickFillIssue[] = []
  rows.forEach((row, ri) => {
    for (const f of allFields) {
      if (f.computed) continue
      if (f.showWhen && !f.showWhen.equals.includes(String(row[f.showWhen.field] ?? ''))) continue
      const v = row[f.key]
      if (v == null || v === '') continue
      if ((f.kind === 'select' || f.kind === 'radio') && f.options?.length) {
        const ok = f.options.some((o) => o.value === String(v))
        if (!ok) {
          issues.push({
            row: ri + 1,
            field: f.key,
            label: f.label,
            message: `「${v}」不在可选项内`,
          })
        }
      }
    }
  })
  return issues
}

/** 将剪贴板矩阵写入网格，从 (row,col) 起始覆盖 */
export function applyPasteToGrid(
  grid: string[][],
  paste: string[][],
  startRow: number,
  startCol: number,
): string[][] {
  if (!paste.length) return grid
  const colCount = grid[0]?.length ?? paste[0]?.length ?? 0
  const needRows = startRow + paste.length
  const next = grid.map((r) => [...r])
  while (next.length < needRows) {
    next.push(Array.from({ length: colCount }, () => ''))
  }
  paste.forEach((cells, ri) => {
    const tr = startRow + ri
    cells.forEach((cell, ci) => {
      const tc = startCol + ci
      if (tc >= colCount) return
      if (!next[tr]) next[tr] = Array.from({ length: colCount }, () => '')
      next[tr][tc] = cell
    })
  })
  return next
}
