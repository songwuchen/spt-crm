import { Table, Input, InputNumber, DatePicker, Button, Select, Radio } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import DataView, { formatMoney, formatScalar } from './DataView'
import {
  LINE_PRODUCT_TYPE_OPTS,
  LINE_ELEC_CTRL_OPTS,
  LINE_YES_NO_OPTS,
  PAY_KIND_OPTS,
} from '@/constants/contractRegistration'

/**
 * 合同条款（收款计划 / 合同明细）的查看 + 录入编辑。
 *
 * 控件类型对齐简道云：产品类型/电控/付款方式=下拉，是否外币/是否提醒=单选；
 * 外币相关列随「是否外币合同=是」动态显示。
 */

type Row = Record<string, unknown>
type Kind = 'text' | 'number' | 'money' | 'pct' | 'date' | 'select' | 'radio'

interface FieldSpec {
  key: string
  label: string
  kind: Kind
  aliases?: string[]
  width?: number
  align?: 'left' | 'right' | 'center'
  computed?: boolean
  options?: { value: string; label: string }[]
  /** 行内动态显隐：依赖本行字段 */
  showWhen?: { field: string; equals: string[] }
}

// 合同明细（结构化条款）
export const LINE_FIELDS: FieldSpec[] = [
  {
    key: 'is_fx', label: '是否外币合同', kind: 'radio', aliases: ['_widget_1621411268784'],
    width: 120, align: 'center', options: LINE_YES_NO_OPTS,
  },
  {
    key: 'product_type', label: '产品类型', kind: 'select', aliases: ['_widget_1561431500162'],
    width: 130, options: LINE_PRODUCT_TYPE_OPTS,
  },
  { key: 'name', label: '产品名称', kind: 'text', aliases: ['_widget_1561431500376'], width: 140 },
  { key: 'spec', label: '规格型号', kind: 'text', aliases: ['_widget_1561431500392'], width: 120 },
  { key: 'unit', label: '单位', kind: 'text', aliases: ['_widget_1561431500419'], width: 70, align: 'center' },
  { key: 'qty', label: '数量', kind: 'number', aliases: ['_widget_1561431500458'], width: 90, align: 'right' },
  {
    key: 'fx_price', label: '外币单价', kind: 'number', aliases: ['_widget_1621411268153'],
    width: 110, align: 'right', showWhen: { field: 'is_fx', equals: ['是'] },
  },
  {
    key: 'fx_rate', label: '汇率', kind: 'number', aliases: ['_widget_1621411269220'],
    width: 90, align: 'right', showWhen: { field: 'is_fx', equals: ['是'] },
  },
  { key: 'price', label: '单价', kind: 'money', aliases: ['_widget_1561431500490'], width: 120, align: 'right' },
  { key: 'amount', label: '总价', kind: 'money', aliases: ['_widget_1561431500514'], width: 130, align: 'right', computed: true },
  {
    key: 'fx_amount', label: '外币总价', kind: 'number', aliases: ['_widget_1621411268210'],
    width: 120, align: 'right', showWhen: { field: 'is_fx', equals: ['是'] },
  },
  {
    key: 'elec_ctrl', label: '电控装置', kind: 'select', aliases: ['_widget_1561431500595'],
    width: 150, options: LINE_ELEC_CTRL_OPTS,
  },
  { key: 'standard', label: '技术参数及要求', kind: 'text', aliases: ['_widget_1565223122750'], width: 160 },
  { key: 'line_remark', label: '备注', kind: 'text', aliases: ['_widget_1697420581927'], width: 140 },
]

// 收款计划（付款条款）
export const PAY_FIELDS: FieldSpec[] = [
  { key: 'due_date', label: '日期时间', kind: 'date', aliases: ['_widget_1661242797064'], width: 150 },
  {
    key: 'kind', label: '付款方式', kind: 'select',
    aliases: ['_widget_1561431500818', '付款方式', '款项性质'],
    width: 110, options: PAY_KIND_OPTS,
  },
  { key: 'ratio', label: '付款比例', kind: 'pct', aliases: ['_widget_1561431500832', '付款比例（%）'], width: 110, align: 'right' },
  { key: 'amount', label: '付款金额', kind: 'money', aliases: ['_widget_1561431500855', '付款金额'], width: 130, align: 'right' },
  {
    key: 'remind', label: '是否提醒', kind: 'radio',
    aliases: ['_widget_1665380028160', '是否提醒'],
    width: 110, align: 'center', options: LINE_YES_NO_OPTS,
  },
  { key: 'note', label: '消息辅助', kind: 'text', aliases: ['_widget_1665380027757'], width: 140 },
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

function rowShows(f: FieldSpec, row: Row): boolean {
  if (!f.showWhen) return true
  const v = row[f.showWhen.field]
  return f.showWhen.equals.includes(v == null ? '' : String(v))
}

function fmt(kind: Kind, v: unknown, opts?: { value: string; label: string }[]): string {
  if (v == null || v === '') return '-'
  if (opts?.length) {
    const hit = opts.find((o) => o.value === String(v))
    if (hit) return hit.label
  }
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
    .filter((f) => rows.some((r) => {
      if (!rowShows(f, r) && f.showWhen) return false
      const v = resolve(r, f)
      return v != null && v !== ''
    }))
    .map((f) => ({
      title: f.label,
      key: f.key,
      align: f.align,
      width: f.width,
      render: (_: unknown, r: Row) => {
        if (f.showWhen && !rowShows(f, r)) return '-'
        return fmt(f.kind, resolve(r, f), f.options)
      },
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

function CellEditor({
  f, value, row, onChange,
}: {
  f: FieldSpec
  value: unknown
  row: Row
  onChange: (v: unknown) => void
}) {
  if (f.computed) {
    return <span className="text-slate-600">{formatMoney(numOf(row.qty) * numOf(row.price))}</span>
  }
  if (f.kind === 'radio' && f.options) {
    return (
      <Radio.Group
        size="small"
        value={value as string}
        onChange={(e) => onChange(e.target.value)}
        optionType="button"
        buttonStyle="solid"
      >
        {f.options.map((o) => (
          <Radio.Button key={o.value} value={o.value}>{o.label}</Radio.Button>
        ))}
      </Radio.Group>
    )
  }
  if (f.kind === 'select') {
    return (
      <Select
        size="small"
        allowClear
        showSearch
        optionFilterProp="label"
        value={(value as string) || undefined}
        options={f.options || []}
        onChange={(v) => onChange(v ?? null)}
        style={{ width: '100%' }}
        placeholder="请选择"
      />
    )
  }
  if (f.kind === 'number') {
    return <InputNumber size="small" value={value as number} onChange={(x) => onChange(x)} style={{ width: '100%' }} />
  }
  if (f.kind === 'money') {
    return <InputNumber size="small" value={value as number} min={0} onChange={(x) => onChange(x)} style={{ width: '100%' }} />
  }
  if (f.kind === 'pct') {
    return (
      <InputNumber
        size="small"
        value={value == null ? null : Number(value) * 100}
        min={0}
        max={100}
        addonAfter="%"
        onChange={(x) => onChange(x == null ? null : Number(x) / 100)}
        style={{ width: '100%' }}
      />
    )
  }
  if (f.kind === 'date') {
    return (
      <DatePicker
        size="small"
        value={value ? dayjs(value as string) : null}
        onChange={(d) => onChange(d ? d.toISOString() : null)}
        style={{ width: '100%' }}
      />
    )
  }
  return <Input size="small" value={value as string} onChange={(e) => onChange(e.target.value)} />
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
    if (key === 'qty' || key === 'price') {
      const r = next[i]
      const amt = numOf(r.qty) * numOf(r.price)
      next[i] = { ...r, amount: amt || null }
    }
    // 切回非外币时清空外币列，避免脏数据
    if (key === 'is_fx' && val !== '是') {
      next[i] = { ...next[i], fx_price: null, fx_rate: null, fx_amount: null }
    }
    onChange(next)
  }
  const addRow = () => onChange([...rows, {}])
  const delRow = (i: number) => onChange(rows.filter((_, j) => j !== i))

  // 列：无 showWhen 的固定列 + 任意行需要外币时显示外币列（表头级）
  const anyFx = rows.some((r) => String(r.is_fx || '') === '是')
  const visibleFields = fields.filter((f) => {
    if (!f.showWhen) return true
    if (f.showWhen.field === 'is_fx') return anyFx
    return true
  })

  const cols = [
    ...visibleFields.map((f) => ({
      title: f.label,
      key: f.key,
      width: f.width,
      align: f.align,
      render: (_: unknown, _r: Row, i: number) => {
        const row = rows[i]
        if (f.showWhen && !rowShows(f, row)) {
          return <span className="text-slate-300">—</span>
        }
        return (
          <CellEditor
            f={f}
            value={row[f.key]}
            row={row}
            onChange={(v) => update(i, f.key, v)}
          />
        )
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
