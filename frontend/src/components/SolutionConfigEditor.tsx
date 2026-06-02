import { useMemo } from 'react'
import { Button, Input, Tooltip } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'

/**
 * Structured editor for a solution version's 配置/选型清单 (config_json).
 *
 * The data is fundamentally a table (a BOM / selection list) so we model it as
 * an array of row objects with a shared, user-managed set of columns. This keeps
 * the saved shape (an array of records) aligned with how SolutionDetail renders
 * config_json in read mode, replacing the old raw-JSON textarea.
 */

export type ConfigRow = Record<string, string>

const DEFAULT_COLUMNS = ['名称', '规格/型号', '数量', '备注']

const cellToString = (v: unknown): string =>
  v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v)

/** Best-effort coercion of arbitrary stored config_json into {columns, rows}. */
export function normalizeConfig(value: unknown): { columns: string[]; rows: ConfigRow[] } {
  let arr: unknown[] = []
  if (Array.isArray(value)) {
    arr = value
  } else if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    // Common wrapper shapes: {items:[...]}, {rows:[...]}, {list:[...]}, ...
    const wrapped = ['items', 'rows', 'list', 'data', 'lines', 'configs'].map((k) => obj[k]).find(Array.isArray)
    if (wrapped) arr = wrapped as unknown[]
    else arr = [obj] // plain key/value object -> single row
  }

  const columns: string[] = []
  arr.forEach((row) => {
    if (row && typeof row === 'object' && !Array.isArray(row)) {
      Object.keys(row as Record<string, unknown>).forEach((k) => {
        if (!columns.includes(k)) columns.push(k)
      })
    }
  })

  const rows: ConfigRow[] = arr.map((row) => {
    const o = (row && typeof row === 'object' && !Array.isArray(row) ? row : {}) as Record<string, unknown>
    const r: ConfigRow = {}
    columns.forEach((c) => { r[c] = cellToString(o[c]) })
    return r
  })

  return { columns, rows }
}

/**
 * Persist as a rectangular array of rows with a consistent key set (so the
 * read-mode table, whose header is derived from the first row, stays correct).
 * Empty columns and empty rows are dropped; returns null when nothing remains.
 */
export function serializeConfig(columns: string[], rows: ConfigRow[]): ConfigRow[] | null {
  const namedCols = columns.filter((c) => c.trim())
  const usedCols = namedCols.filter((c) => rows.some((r) => cellToString(r[c]).trim()))
  if (!usedCols.length) return null
  const cleaned = rows
    .filter((r) => usedCols.some((c) => cellToString(r[c]).trim()))
    .map((r) => {
      const out: ConfigRow = {}
      usedCols.forEach((c) => { out[c] = cellToString(r[c]) })
      return out
    })
  return cleaned.length ? cleaned : null
}

interface Props {
  columns: string[]
  rows: ConfigRow[]
  onChange: (columns: string[], rows: ConfigRow[]) => void
}

export default function SolutionConfigEditor({ columns, rows, onChange }: Props) {
  const cols = useMemo(() => (columns.length ? columns : DEFAULT_COLUMNS), [columns])

  const setCell = (rowIdx: number, col: string, val: string) => {
    const next = rows.map((r, i) => (i === rowIdx ? { ...r, [col]: val } : r))
    onChange(cols, next)
  }

  // Operate on columns by index (not name): names are mutable and may collide
  // mid-edit, and an index key keeps the header input from remounting (which
  // would drop focus) while the user types a new column name.
  const renameColumn = (colIdx: number, newName: string) => {
    const oldName = cols[colIdx]
    const nextCols = cols.map((c, i) => (i === colIdx ? newName : c))
    const nextRows = rows.map((r) => {
      const { [oldName]: oldVal, ...rest } = r
      return { ...rest, [newName]: oldVal ?? '' }
    })
    onChange(nextCols, nextRows)
  }

  const addColumn = () => {
    let name = '新列'
    let n = 1
    while (cols.includes(name)) { name = `新列${++n}` }
    onChange([...cols, name], rows.map((r) => ({ ...r, [name]: '' })))
  }

  const removeColumn = (colIdx: number) => {
    const target = cols[colIdx]
    const nextCols = cols.filter((_, i) => i !== colIdx)
    const nextRows = rows.map((r) => {
      const { [target]: _drop, ...rest } = r
      return rest
    })
    onChange(nextCols, nextRows)
  }

  const addRow = () => {
    const blank: ConfigRow = {}
    cols.forEach((c) => { blank[c] = '' })
    onChange(cols, [...rows, blank])
  }

  const removeRow = (idx: number) => onChange(cols, rows.filter((_, i) => i !== idx))

  return (
    <div className="border border-slate-200 rounded-lg overflow-hidden">
      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200">
              {cols.map((col, ci) => (
                <th key={ci} className="p-1.5 text-left font-bold text-slate-500 min-w-[140px]">
                  <div className="flex items-center gap-1">
                    <Input
                      size="small"
                      value={col}
                      variant="borderless"
                      className="font-bold !px-1"
                      onChange={(e) => renameColumn(ci, e.target.value)}
                    />
                    <Tooltip title="删除该列">
                      <Button
                        size="small"
                        type="text"
                        danger
                        disabled={cols.length <= 1}
                        icon={<DeleteOutlined />}
                        onClick={() => removeColumn(ci)}
                      />
                    </Tooltip>
                  </div>
                </th>
              ))}
              <th className="p-1.5 w-12 text-center">
                <Tooltip title="添加列">
                  <Button size="small" type="text" icon={<PlusOutlined />} onClick={addColumn} />
                </Tooltip>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td colSpan={cols.length + 1} className="text-center text-sm text-slate-400 py-6">
                  暂无明细，点击下方“添加行”开始填写
                </td>
              </tr>
            )}
            {rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="border-b border-slate-100 last:border-0">
                {cols.map((col, ci) => (
                  <td key={ci} className="p-1">
                    <Input
                      size="small"
                      variant="borderless"
                      value={row[col] ?? ''}
                      onChange={(e) => setCell(rowIdx, col, e.target.value)}
                    />
                  </td>
                ))}
                <td className="p-1 text-center">
                  <Button size="small" type="text" danger icon={<DeleteOutlined />} onClick={() => removeRow(rowIdx)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="p-2 bg-slate-50 border-t border-slate-200">
        <Button block size="small" type="dashed" icon={<PlusOutlined />} onClick={addRow}>
          添加行
        </Button>
      </div>
    </div>
  )
}
