import { Table } from 'antd'
import DataView, { formatMoney, formatScalar } from './DataView'

/**
 * 合同条款渲染：把迁移自简道云的「合同明细 / 收款计划」子表单数组
 * 渲染成规整表格（中文表头 + ¥ 金额 + 合计），而不是原始 JSON。
 * 非数组（对象 / 脱敏字符串）时回退到通用 DataView。
 */

type Row = Record<string, unknown>

const num = (v: unknown): number => {
  const n = Number(String(v ?? '').replace(/,/g, ''))
  return Number.isFinite(n) ? n : 0
}

function ratioText(v: unknown): string {
  if (v == null || v === '') return '-'
  const n = Number(v)
  if (Number.isFinite(n) && n > 0 && n <= 1) return `${+(n * 100).toFixed(2)}%`
  return formatScalar(v)
}

// 合同明细列
const CLAUSE_COLS = [
  { id: '_widget_1561431500376', title: '名称', minWidth: 140 },
  { id: '_widget_1561431500392', title: '规格型号', minWidth: 140 },
  { id: '_widget_1561431500419', title: '单位', align: 'center' as const, width: 64 },
  { id: '_widget_1561431500458', title: '数量', align: 'right' as const, width: 72, kind: 'num' as const },
  { id: '_widget_1561431500490', title: '单价', align: 'right' as const, width: 110, kind: 'money' as const },
  { id: '_widget_1561431500514', title: '金额', align: 'right' as const, width: 120, kind: 'money' as const },
  { id: '_widget_1561431500595', title: '备注', minWidth: 120 },
  { id: '_widget_1565223122750', title: '技术标准/参照', minWidth: 120 },
]

// 收款计划列
const PAY_COLS = [
  { id: '_widget_1561431500818', title: '款项性质', width: 100 },
  { id: '_widget_1561431500832', title: '付款比例', align: 'right' as const, width: 90, kind: 'pct' as const },
  { id: '_widget_1561431500855', title: '金额', align: 'right' as const, width: 120, kind: 'money' as const },
  { id: '_widget_1661242797064', title: '到期日期', width: 120, kind: 'date' as const },
  { id: '_widget_1665380027757', title: '说明', minWidth: 200 },
]

function renderCell(kind: string | undefined, v: unknown) {
  if (kind === 'money') return formatMoney(v)
  if (kind === 'pct') return ratioText(v)
  if (kind === 'num') return v == null || v === '' ? '-' : formatScalar(v)
  return formatScalar(v)
}

function TermsTable({
  rows,
  spec,
  sumKey,
}: {
  rows: Row[]
  spec: typeof CLAUSE_COLS | typeof PAY_COLS
  sumKey: string
}) {
  // 仅保留至少有一行有值的列
  const cols = spec
    .filter((c) => rows.some((r) => r[c.id] != null && r[c.id] !== ''))
    .map((c) => ({
      title: c.title,
      dataIndex: c.id,
      key: c.id,
      align: 'align' in c ? c.align : undefined,
      width: 'width' in c ? c.width : undefined,
      render: (v: unknown) => renderCell('kind' in c ? c.kind : undefined, v),
    }))

  const total = rows.reduce((s, r) => s + num(r[sumKey]), 0)
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
                {i === 0 ? <span className="font-bold">合计</span> : c.dataIndex === sumKey ? (
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

/** 收款计划 / 付款条款 */
export function PaymentTermsView({ value }: { value: unknown }) {
  if (Array.isArray(value) && value.length > 0 && value.every((v) => v && typeof v === 'object')) {
    return <TermsTable rows={value as Row[]} spec={PAY_COLS} sumKey="_widget_1561431500855" />
  }
  return <DataView value={value} />
}

/** 合同明细 / 结构化条款 */
export function ClauseTermsView({ value }: { value: unknown }) {
  if (Array.isArray(value) && value.length > 0 && value.every((v) => v && typeof v === 'object')) {
    return <TermsTable rows={value as Row[]} spec={CLAUSE_COLS} sumKey="_widget_1561431500514" />
  }
  return <DataView value={value} />
}
