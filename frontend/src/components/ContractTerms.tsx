import { useEffect, useState } from 'react'
import { Table, Input, InputNumber, DatePicker, Button, Select, Radio, Space } from 'antd'
import { PlusOutlined, DeleteOutlined, TableOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import DataView, { formatMoney, formatScalar } from './DataView'
import ContractSectionTitle from './ContractSectionTitle'
import DetailQuickFillModal from './DetailQuickFillModal'
import { useFieldPolicy } from '@/components/lowcode/FieldPolicy'
import { lowcodeApi } from '@/api/lowcode'
import type { FieldDefinition } from '@/types/lowcode'
import {
  FALLBACK_LINE_COLUMNS,
  FALLBACK_PAY_COLUMNS,
  LINE_ITEMS_FIELD_ID,
  PAYMENT_TERMS_FIELD_ID,
} from '@/constants/contractDetailTables'

/**
 * 合同条款（收款计划 / 合同明细）的查看 + 录入编辑。
 *
 * 列定义来自 FieldPolicy（native_field_catalog 的 detail_table）或本地 fallback；
 * 外币公式 / JDY aliases / 独立 JSON 存储列逻辑保留在此组件。
 */

type Row = Record<string, unknown>
type Kind = 'text' | 'number' | 'money' | 'pct' | 'date' | 'select' | 'radio'
type Align = 'left' | 'right' | 'center'

export interface FieldSpec {
  key: string
  label: string
  kind: Kind
  aliases?: string[]
  width?: number
  align?: Align
  computed?: boolean
  options?: { value: string; label: string }[]
  showWhen?: { field: string; equals: string[] }
}

function typeToKind(type: string, props?: Record<string, unknown>): Kind {
  if (props?.percent) return 'pct'
  if (type === 'amount') return 'money'
  if (type === 'number') return 'number'
  if (type === 'date' || type === 'datetime') return 'date'
  if (type === 'select') return 'select'
  if (type === 'radio') return 'radio'
  return 'text'
}

/** FieldDefinition 列 → 内部 FieldSpec（兼容旧 toCanonicalRows / 测试） */
export function columnsToFieldSpecs(columns: FieldDefinition[]): FieldSpec[] {
  return columns.map((c) => {
    const props = (c.props || {}) as Record<string, unknown>
    const showWhen = props.show_when as { field: string; equals: string[] } | undefined
    const aliases = props.aliases as string[] | undefined
    const width = typeof props.width === 'number' ? props.width : undefined
    const align = props.align as Align | undefined
    return {
      key: c.id,
      label: c.label,
      kind: typeToKind(c.type, props),
      aliases: Array.isArray(aliases) ? aliases : undefined,
      width,
      align,
      computed: props.computed === true,
      options: c.options?.map((o) => ({ value: String(o.value), label: o.label })),
      showWhen: showWhen?.field ? showWhen : undefined,
    }
  })
}

/** @deprecated 使用 FALLBACK_LINE_COLUMNS / resolveLineColumns；保留给旧调用方 */
export const LINE_FIELDS: FieldSpec[] = columnsToFieldSpecs(FALLBACK_LINE_COLUMNS)
/** @deprecated 使用 FALLBACK_PAY_COLUMNS / resolvePayColumns */
export const PAY_FIELDS: FieldSpec[] = columnsToFieldSpecs(FALLBACK_PAY_COLUMNS)

function columnsFromPolicy(
  nativeFields: FieldDefinition[] | undefined,
  fieldId: string,
  fallback: FieldDefinition[],
): FieldDefinition[] {
  const fd = nativeFields?.find((f) => f.id === fieldId)
  const cols = fd?.detail_table_columns
  return cols?.length ? cols : fallback
}

export function resolveLineColumns(nativeFields?: FieldDefinition[]): FieldDefinition[] {
  return columnsFromPolicy(nativeFields, LINE_ITEMS_FIELD_ID, FALLBACK_LINE_COLUMNS)
}

export function resolvePayColumns(nativeFields?: FieldDefinition[]): FieldDefinition[] {
  return columnsFromPolicy(nativeFields, PAYMENT_TERMS_FIELD_ID, FALLBACK_PAY_COLUMNS)
}

/** 子表区块标题：读已发布/策略中的字段 label（设计器改「收款计划→收款2」后业务页同步） */
export function useContractSubtableTitle(fieldId: string, fallback: string): string {
  const policy = useFieldPolicy()
  const [remoteLabel, setRemoteLabel] = useState<string | null>(null)

  useEffect(() => {
    if (policy.loaded && !policy.failed && policy.nativeFields.length) return
    let alive = true
    lowcodeApi.entityFormSchema('contract')
      .then((r) => {
        if (!alive) return
        const fd = (r.data.native_fields || []).find((f) => f.id === fieldId)
        const name = (typeof fd?.label_override === 'string' && fd.label_override.trim())
          || (typeof fd?.label === 'string' && fd.label.trim())
          || ''
        if (name) setRemoteLabel(name)
      })
      .catch(() => { /* fallback */ })
    return () => { alive = false }
  }, [fieldId, policy.loaded, policy.failed, policy.nativeFields.length])

  if (policy.loaded && !policy.failed) {
    const fromPolicy = policy.labelOf(fieldId)
    if (fromPolicy?.trim()) return fromPolicy.trim()
    const fd = policy.nativeFields.find((f) => f.id === fieldId)
    const name = (typeof fd?.label_override === 'string' && fd.label_override.trim())
      || (typeof fd?.label === 'string' && fd.label.trim())
    if (name) return name
  }
  return remoteLabel || fallback
}

/** 合同明细 / 收款计划分区标题（跟随设计器字段 label） */
export function ContractSubtableTitle({
  fieldId, fallback, className,
}: {
  fieldId: string
  fallback: string
  className?: string
}) {
  const title = useContractSubtableTitle(fieldId, fallback)
  return <ContractSectionTitle title={title} className={className} />
}

/** 优先 FieldPolicy；无 Provider 时拉 entityFormSchema；再失败用 fallback */
function useDetailColumns(
  fieldId: string,
  fallback: FieldDefinition[],
  columnsOverride?: FieldDefinition[],
): FieldDefinition[] {
  const policy = useFieldPolicy()
  const [remote, setRemote] = useState<FieldDefinition[] | null>(null)

  useEffect(() => {
    if (columnsOverride?.length) return
    if (policy.loaded && !policy.failed && policy.nativeFields.length) return
    let alive = true
    lowcodeApi.entityFormSchema('contract')
      .then((r) => {
        if (!alive) return
        const fd = (r.data.native_fields || []).find((f) => f.id === fieldId)
        if (fd?.detail_table_columns?.length) setRemote(fd.detail_table_columns)
      })
      .catch(() => { /* 用 fallback */ })
    return () => { alive = false }
  }, [fieldId, columnsOverride, policy.loaded, policy.failed, policy.nativeFields.length])

  if (columnsOverride?.length) return columnsOverride
  if (policy.loaded && !policy.failed && policy.nativeFields.length) {
    return columnsFromPolicy(policy.nativeFields, fieldId, fallback)
  }
  return remote?.length ? remote : fallback
}

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
  const total = rows.reduce((s, r) => s + numOf(resolve(r, {
    key: SUM_KEY, label: '', kind: 'money',
    aliases: fields.find((x) => x.key === SUM_KEY)?.aliases,
  })), 0)
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
export function PaymentTermsView({ value, columns }: { value: unknown; columns?: FieldDefinition[] }) {
  const cols = useDetailColumns(PAYMENT_TERMS_FIELD_ID, FALLBACK_PAY_COLUMNS, columns)
  const fields = columnsToFieldSpecs(cols)
  return isRowArray(value) ? <TermsTable rows={value} fields={fields} /> : <DataView value={value} />
}

/** 合同明细 / 结构化条款（只读） */
export function ClauseTermsView({ value, columns }: { value: unknown; columns?: FieldDefinition[] }) {
  const cols = useDetailColumns(LINE_ITEMS_FIELD_ID, FALLBACK_LINE_COLUMNS, columns)
  const fields = columnsToFieldSpecs(cols)
  return isRowArray(value) ? <TermsTable rows={value} fields={fields} /> : <DataView value={value} />
}

// ---- 录入编辑 -----------------------------------------------------------

/** 把任意行（含旧 _widget_* 数据）规整成干净字段，供编辑器使用 */
export function toCanonicalRows(value: unknown, fields: FieldSpec[] | FieldDefinition[]): Row[] {
  if (!Array.isArray(value)) return []
  if (!fields.length) return []
  const specs = 'key' in fields[0]
    ? (fields as FieldSpec[])
    : columnsToFieldSpecs(fields as FieldDefinition[])
  const known = new Set(specs.map((f) => f.key))
  const aliasKeys = new Set(specs.flatMap((f) => f.aliases || []))
  return value
    .filter((r) => r && typeof r === 'object')
    .map((r) => {
      const src = r as Row
      const out: Row = {}
      for (const f of specs) out[f.key] = resolve(src, f)
      // 保留设计器新增的自定义列（不在目录里的 key）
      for (const [k, v] of Object.entries(src)) {
        if (known.has(k) || aliasKeys.has(k)) continue
        if (k.startsWith('_widget_')) continue
        out[k] = v
      }
      return out
    })
}

/** 对齐简道云明细公式后回写行内计算列 */
export function recomputeLineRow(row: Row): Row {
  const next = { ...row }
  const isFx = String(next.is_fx || '') === '是'
  if (isFx) {
    const fxPrice = numOf(next.fx_price)
    const fxRate = numOf(next.fx_rate)
    if (fxPrice && fxRate) {
      next.price = Math.round(fxPrice * fxRate * 100) / 100
    }
    next.fx_amount = fxPrice && numOf(next.qty)
      ? Math.round(fxPrice * numOf(next.qty) * 100) / 100
      : null
  } else {
    next.fx_amount = null
  }
  const amt = Math.round(numOf(next.qty) * numOf(next.price) * 100) / 100
  next.amount = amt || null
  return next
}

export function sumLineAmounts(rows: Row[]): number {
  return rows.reduce((s, r) => s + numOf(r.amount), 0)
}

/** 对齐简道云：付款金额 = 合同总金额 × 付款比例（比例存 0~1） */
export function recomputePayRow(row: Row, contractTotal: number): Row {
  const ratio = numOf(row.ratio)
  const total = numOf(contractTotal)
  if (!ratio && !total) {
    return { ...row, amount: row.amount ?? null }
  }
  const amount = Math.round(total * ratio * 100) / 100
  return { ...row, amount }
}

export function recomputePayRows(rows: Row[], contractTotal: number): Row[] {
  return rows.map((r) => recomputePayRow(r, contractTotal))
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
    if (f.key === 'fx_amount') {
      return <span className="text-slate-600">{formatScalar(row.fx_amount ?? '-')}</span>
    }
    return <span className="text-slate-600">{formatMoney(numOf(row.amount))}</span>
  }
  if (f.key === 'price' && String(row.is_fx || '') === '是') {
    return <span className="text-slate-600">{formatMoney(numOf(row.price))}</span>
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
  onTotalChange,
  recompute = false,
  contractTotal,
  quickFill = false,
}: {
  fields: FieldSpec[]
  rows: Row[]
  onChange: (rows: Row[]) => void
  onTotalChange?: (total: number) => void
  /** 合同明细行需要外币/总价重算 */
  recompute?: boolean
  /** 收款计划：传入合同总金额后按比例重算付款金额 */
  contractTotal?: number
  /** 显示「快速填报」入口（合同明细） */
  quickFill?: boolean
}) {
  const [qfOpen, setQfOpen] = useState(false)
  const emit = (next: Row[]) => {
    onChange(next)
    onTotalChange?.(sumLineAmounts(next))
  }
  const update = (i: number, key: string, val: unknown) => {
    let row: Row = { ...rows[i], [key]: val }
    if (recompute) {
      if (key === 'is_fx' && val !== '是') {
        row = { ...row, fx_price: null, fx_rate: null, fx_amount: null }
      }
      if (['qty', 'price', 'fx_price', 'fx_rate', 'is_fx'].includes(key)) {
        row = recomputeLineRow(row)
      }
    }
    if (contractTotal != null && key === 'ratio') {
      row = recomputePayRow(row, contractTotal)
    }
    emit(rows.map((r, j) => (j === i ? row : r)))
  }
  const addRow = () => emit([...rows, {}])
  const delRow = (i: number) => emit(rows.filter((_, j) => j !== i))
  const applyQuickFill = (incoming: Row[], mode: 'append' | 'replace') => {
    const normalized = recompute
      ? incoming.map((r) => recomputeLineRow(r))
      : incoming
    const base = mode === 'replace' ? [] : rows
    emit([...base, ...normalized])
  }

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
      <Space className="mt-2">
        <Button size="small" type="dashed" icon={<PlusOutlined />} onClick={addRow}>添加一行</Button>
        {quickFill && (
          <Button size="small" type="link" icon={<TableOutlined />} onClick={() => setQfOpen(true)}>
            快速填报
          </Button>
        )}
      </Space>
      {quickFill && (
        <DetailQuickFillModal
          open={qfOpen}
          fields={fields}
          existingRows={rows}
          onClose={() => setQfOpen(false)}
          onConfirm={applyQuickFill}
        />
      )}
    </div>
  )
}

/** 付款条款（收款计划）编辑器 */
export function PaymentTermsEditor({
  value, onChange, columns, contractTotal, hideFinanceFields = false,
}: {
  value: Row[]
  onChange: (v: Row[]) => void
  columns?: FieldDefinition[]
  /** 合同总金额；有值时付款金额 = 总金额 × 比例（只读） */
  contractTotal?: number
  /** 新建/发起：隐藏「是否提醒」「消息辅助」（留给财务维护） */
  hideFinanceFields?: boolean
}) {
  const cols = useDetailColumns(PAYMENT_TERMS_FIELD_ID, FALLBACK_PAY_COLUMNS, columns)
  const visibleCols = hideFinanceFields
    ? cols.filter((c) => {
      const props = (c.props || {}) as { available_on_create?: boolean }
      if (props.available_on_create === false) return false
      if (c.id === 'remind' || c.id === 'note') return false
      return true
    })
    : cols

  useEffect(() => {
    if (contractTotal == null || !value.length) return
    const next = recomputePayRows(value, contractTotal)
    const changed = next.some((r, i) => numOf(r.amount) !== numOf(value[i]?.amount))
    if (changed) onChange(next)
    // 仅随合同总额变化重算；行内改比例在 EditableTermsTable.update 处理
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [contractTotal])

  return (
    <EditableTermsTable
      fields={columnsToFieldSpecs(visibleCols)}
      rows={value}
      onChange={onChange}
      contractTotal={contractTotal}
    />
  )
}

/** 合同明细编辑器；onTotalChange 对齐简道云 SUM(总价)→合同总金额 */
export function LineItemsEditor({
  value,
  onChange,
  onTotalChange,
  columns,
}: {
  value: Row[]
  onChange: (v: Row[]) => void
  onTotalChange?: (total: number) => void
  columns?: FieldDefinition[]
}) {
  const cols = useDetailColumns(LINE_ITEMS_FIELD_ID, FALLBACK_LINE_COLUMNS, columns)
  return (
    <EditableTermsTable
      fields={columnsToFieldSpecs(cols)}
      rows={value}
      onChange={onChange}
      onTotalChange={onTotalChange}
      recompute
      quickFill
    />
  )
}
