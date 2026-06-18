import { Table, Input, InputNumber, DatePicker, Button } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import DataView, { formatMoney, formatScalar } from './DataView'

/**
 * 合同条款（收款计划 / 合同明细）的查看 + 录入编辑。
 *
 * 新录入的数据用干净的语义字段名（name/spec/qty...），同时兼容迁移自简道云的
 * `_widget_*` 旧字段（通过 aliases 解析），新旧数据都能正常展示。
 */

type Row = Record<string, unknown>
type Kind = 'text' | 'number' | 'money' | 'pct' | 'date'

interface FieldSpec {
  key: string
  label: string
  kind: Kind
  aliases?: string[]
  width?: number
  align?: 'left' | 'right' | 'center'
  computed?: boolean // 金额 = 数量 × 单价，自动计算
}

// 合同明细（结构化条款）
export const LINE_FIELDS: FieldSpec[] = [
  { key: 'name', label: '名称', kind: 'text', aliases: ['_widget_1561431500376'] },
  { key: 'spec', label: '规格型号', kind: 'text', aliases: ['_widget_1561431500392'] },
  { key: 'unit', label: '单位', kind: 'text', aliases: ['_widget_1561431500419'], width: 70, align: 'center' },
  { key: 'qty', label: '数量', kind: 'number', aliases: ['_widget_1561431500458'], width: 90, align: 'right' },
  { key: 'price', label: '单价', kind: 'money', aliases: ['_widget_1561431500490'], width: 120, align: 'right' },
  { key: 'amount', label: '金额', kind: 'money', aliases: ['_widget_1561431500514'], width: 130, align: 'right', computed: true },
  { key: 'remark', label: '备注', kind: 'text', aliases: ['_widget_1561431500595'] },
  { key: 'standard', label: '技术标准/参照', kind: 'text', aliases: ['_widget_1565223122750'] },
]

// 收款计划（付款条款）
export const PAY_FIELDS: FieldSpec[] = [
  { key: 'kind', label: '款项性质', kind: 'text', aliases: ['_widget_1561431500818'], width: 110 },
  { key: 'ratio', label: '付款比例', kind: 'pct', aliases: ['_widget_1561431500832'], width: 110, align: 'right' },
  { key: 'amount', label: '金额', kind: 'money', aliases: ['_widget_1561431500855'], width: 130, align: 'right' },
  { key: 'due_date', label: '到期日期', kind: 'date', aliases: ['_widget_1661242797064'], width: 150 },
  { key: 'note', label: '说明', kind: 'text', aliases: ['_widget_1665380027757'] },
]

const SUM_KEY = 'amount'

function resolve(row: Row, f: FieldSpec): unknown {
  if (row[f.key] != null && row[f.key] !== '') return row[f.key]
  for (const a of f.aliases || []) if (row[a] != null && row[a] !== '') return row[a]
  return row[f.key]
}

const numOf = (v: unknown): number => {
  const n = Number(String(v ?? '').replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}

function fmt(kind: Kind, v: unknown): string {
  if (v == null || v === '') return '-'
  if (kind === 'money') return formatMoney(v)
  if (kind === 'pct') {
    const n = Number(v)
    if (Number.isFinite(n)) return n > 0 && n <= 1 ? `${+(n * 100).toFixed(2)}%` : `${n}`
    return formatScalar(v)
  }
  return formatScalar(v)
}

// ---- 查看（只读） -------------------------------------------------------

function TermsTable({ rows, fields }: { rows: Row[]; fields: FieldSpec[] }) {
  const cols = fields
    .filter((f) => rows.some((r) => { const v = resolve(r, f); return v != null && v !== '' }))
    .map((f) => ({
      title: f.label,
      key: f.key,
      align: f.align,
      width: f.width,
      render: (_: unknown, r: Row) => fmt(f.kind, resolve(r, f)),
    }))
  const total = rows.reduce((s, r) => s + numOf(resolve(r, { key: SUM_KEY, label: '', kind: 'money', aliases: fields.find((x) => x.key === SUM_KEY)?.aliases })), 0)
  const keyMap = new WeakMap<object, string>()
  rows.forEach((r, i) => keyMap.set(r, String(r._id ?? i)))

  return (
    <Table
      size="small"
      rowKey={(r) => keyMap.get(r as object) ?? '0'}
      dataSource={rows}
      columns={cols}
      pagination={false}
      scroll={{ x: 'max-content' }}
      summary={() =>
        rows.length > 1 ? (
          <Table.Summary.Row>
            {cols.map((c, i) => (
              <Table.Summary.Cell key={c.key} index={i} align={c.align}>
                {i === 0 ? <span className="font-bold">合计</span> : c.key === SUM_KEY ? (
                  <span className="font-bold text-primary">{formatMoney(total)}</span>
                ) : null}
              </Table.Summary.Cell>
            ))}
          </Table.Summary.Row>
        ) : null
      }
    />
  )
}

function isRowArray(v: unknown): v is Row[] {
  return Array.isArray(v) && v.length > 0 && v.every((x) => x && typeof x === 'object')
}

/** 收款计划 / 付款条款（只读） */
export function PaymentTermsView({ value }: { value: unknown }) {
  return isRowArray(value) ? <TermsTable rows={value} fields={PAY_FIELDS} /> : <DataView value={value} />
}

/** 合同明细 / 结构化条款（只读） */
export function ClauseTermsView({ value }: { value: unknown }) {
  return isRowArray(value) ? <TermsTable rows={value} fields={LINE_FIELDS} /> : <DataView value={value} />
}

// ---- 录入编辑 -----------------------------------------------------------

/** 把任意行（含旧 _widget_* 数据）规整成干净字段，供编辑器使用 */
export function toCanonicalRows(value: unknown, fields: FieldSpec[]): Row[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((r) => r && typeof r === 'object')
    .map((r) => {
      const out: Row = {}
      for (const f of fields) out[f.key] = resolve(r as Row, f)
      return out
    })
}

function EditableTermsTable({
  fields,
  rows,
  onChange,
}: {
  fields: FieldSpec[]
  rows: Row[]
  onChange: (rows: Row[]) => void
}) {
  const update = (i: number, key: string, val: unknown) => {
    const next = rows.map((r, j) => (j === i ? { ...r, [key]: val } : r))
    // 金额 = 数量 × 单价 自动计算
    if (key === 'qty' || key === 'price') {
      const r = next[i]
      const amt = numOf(r.qty) * numOf(r.price)
      next[i] = { ...r, amount: amt || null }
    }
    onChange(next)
  }
  const addRow = () => onChange([...rows, {}])
  const delRow = (i: number) => onChange(rows.filter((_, j) => j !== i))

  const cols = [
    ...fields.map((f) => ({
      title: f.label,
      key: f.key,
      width: f.width,
      align: f.align,
      render: (_: unknown, _r: Row, i: number) => {
        const v = rows[i][f.key]
        if (f.computed) return <span className="text-slate-600">{formatMoney(numOf(rows[i].qty) * numOf(rows[i].price)) }</span>
        if (f.kind === 'number') return <InputNumber size="small" value={v as number} onChange={(x) => update(i, f.key, x)} style={{ width: '100%' }} />
        if (f.kind === 'money') return <InputNumber size="small" value={v as number} min={0} onChange={(x) => update(i, f.key, x)} style={{ width: '100%' }} />
        if (f.kind === 'pct') return <InputNumber size="small" value={v == null ? null : Number(v) * 100} min={0} max={100} addonAfter="%" onChange={(x) => update(i, f.key, x == null ? null : Number(x) / 100)} style={{ width: '100%' }} />
        if (f.kind === 'date') return <DatePicker size="small" value={v ? dayjs(v as string) : null} onChange={(d) => update(i, f.key, d ? d.toISOString() : null)} style={{ width: '100%' }} />
        return <Input size="small" value={v as string} onChange={(e) => update(i, f.key, e.target.value)} />
      },
    })),
    {
      title: '',
      key: '__op',
      width: 44,
      render: (_: unknown, _r: Row, i: number) => (
        <Button type="text" size="small" danger icon={<DeleteOutlined />} onClick={() => delRow(i)} />
      ),
    },
  ]

  return (
    <div>
      <Table
        size="small"
        rowKey={(_r, i) => String(i)}
        dataSource={rows}
        columns={cols}
        pagination={false}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: '暂无明细，点击下方「添加一行」' }}
      />
      <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={addRow} className="mt-2">添加一行</Button>
    </div>
  )
}

/** 付款条款（收款计划）编辑器 */
export function PaymentTermsEditor({ value, onChange }: { value: Row[]; onChange: (v: Row[]) => void }) {
  return <EditableTermsTable fields={PAY_FIELDS} rows={value} onChange={onChange} />
}

/** 合同明细（结构化条款）编辑器 */
export function LineItemsEditor({ value, onChange }: { value: Row[]; onChange: (v: Row[]) => void }) {
  return <EditableTermsTable fields={LINE_FIELDS} rows={value} onChange={onChange} />
}
