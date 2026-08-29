/**
 * 合同明细 / 收款计划列定义的前端 fallback。
 * 权威源：backend native_field_catalog._CONTRACT_LINE_COLUMNS / _CONTRACT_PAY_COLUMNS。
 * FieldPolicy 拉取成功时以 schema 为准；失败时用本文件，须与目录保持同步。
 */
import type { FieldDefinition } from '@/types/lowcode'
import {
  LINE_PRODUCT_TYPE_OPTS,
  LINE_ELEC_CTRL_OPTS,
  LINE_YES_NO_OPTS,
  PAY_KIND_OPTS,
} from '@/constants/contractRegistration'

type SimpleOption = { label: string; value: string }

function col(
  id: string,
  label: string,
  type: FieldDefinition['type'] = 'text',
  props: Record<string, unknown> = {},
  options?: SimpleOption[],
  required = false,
): FieldDefinition {
  const fd: FieldDefinition = {
    id, label, type, required,
    props: { system_column: true, ...props },
  }
  if (options) fd.options = options
  return fd
}

const FX_SHOW = { field: 'is_fx', equals: ['是'] }

function isBlank(v: unknown): boolean {
  if (v == null || v === '') return true
  if (Array.isArray(v) && v.length === 0) return true
  return false
}

function colVisible(col: FieldDefinition, row: Record<string, unknown>): boolean {
  const showWhen = (col.props as { show_when?: { field: string; equals: string[] } } | undefined)?.show_when
  if (!showWhen?.field) return true
  const v = row[showWhen.field]
  return showWhen.equals.includes(v == null ? '' : String(v))
}

/** 校验合同明细行必填列；通过返回 null，否则返回提示文案。 */
export function validateContractLineRows(
  rows: Record<string, unknown>[],
  columns: FieldDefinition[],
  tableLabel = '合同明细',
): string | null {
  const nonEmpty = rows.filter((r) => Object.values(r).some((x) => x != null && x !== ''))
  if (!nonEmpty.length) return `请填写${tableLabel}`
  for (let i = 0; i < nonEmpty.length; i++) {
    const row = nonEmpty[i]
    for (const c of columns) {
      if (c.type === 'formula') continue
      if ((c.props as { computed?: boolean } | undefined)?.computed) continue
      if (c.available_on_create === false || c.fill_stage === 'approver') continue
      if (!c.required) continue
      if (!colVisible(c, row)) continue
      if (isBlank(row[c.id])) {
        return `「${tableLabel}」第 ${i + 1} 行「${c.label || c.id}」为必填项`
      }
    }
  }
  return null
}

/** 与目录 line_items.detail_table_columns 对齐 */
export const FALLBACK_LINE_COLUMNS: FieldDefinition[] = [
  col('is_fx', '是否外币合同', 'radio', { aliases: ['_widget_1621411268784'], width: 120, align: 'center' }, LINE_YES_NO_OPTS, true),
  col('product_type', '产品类型', 'select', { aliases: ['_widget_1561431500162'], width: 130 }, LINE_PRODUCT_TYPE_OPTS, true),
  col('name', '产品名称', 'text', { aliases: ['_widget_1561431500376'], width: 140 }, undefined, true),
  col('spec', '规格型号', 'text', { aliases: ['_widget_1561431500392'], width: 120 }, undefined, true),
  col('unit', '单位', 'text', { aliases: ['_widget_1561431500419'], width: 70, align: 'center' }, undefined, true),
  col('qty', '数量', 'number', { aliases: ['_widget_1561431500458'], width: 90, align: 'right' }, undefined, true),
  col('fx_price', '外币单价', 'number', { aliases: ['_widget_1621411268153'], width: 110, align: 'right', show_when: FX_SHOW }, undefined, true),
  col('fx_rate', '汇率', 'number', { aliases: ['_widget_1621411269220'], width: 90, align: 'right', show_when: FX_SHOW }, undefined, true),
  col('price', '单价', 'amount', { aliases: ['_widget_1561431500490'], width: 120, align: 'right' }, undefined, true),
  col('amount', '总价', 'amount', { aliases: ['_widget_1561431500514'], width: 130, align: 'right', computed: true }),
  col('fx_amount', '外币总价', 'number', { aliases: ['_widget_1621411268210'], width: 120, align: 'right', computed: true, show_when: FX_SHOW }),
  col('elec_ctrl', '电控装置', 'select', { aliases: ['_widget_1561431500595'], width: 150 }, LINE_ELEC_CTRL_OPTS),
  col('standard', '技术参数及要求', 'text', { aliases: ['_widget_1565223122750'], width: 160 }),
  col('line_remark', '备注', 'text', { aliases: ['_widget_1697420581927'], width: 140 }),
]

/** 与目录 payment_terms.detail_table_columns 对齐 */
export const FALLBACK_PAY_COLUMNS: FieldDefinition[] = [
  col('due_date', '日期时间', 'date', { aliases: ['_widget_1661242797064'], width: 150 }),
  col('kind', '付款方式', 'select', { aliases: ['_widget_1561431500818', '付款方式', '款项性质'], width: 110 }, PAY_KIND_OPTS),
  col('ratio', '付款比例', 'number', { aliases: ['_widget_1561431500832', '付款比例（%）'], width: 110, align: 'right', percent: true }),
  // 简道云：合同总金额 × 付款比例
  col('amount', '付款金额', 'amount', { aliases: ['_widget_1561431500855', '付款金额'], width: 130, align: 'right', computed: true }),
  // 发起不展示；财务维护时填写
  col('remind', '是否提醒', 'radio', { aliases: ['_widget_1665380028160', '是否提醒'], width: 110, align: 'center', available_on_create: false }, LINE_YES_NO_OPTS),
  col('note', '消息辅助', 'text', { aliases: ['_widget_1665380027757'], width: 140, available_on_create: false }),
]

export const LINE_ITEMS_FIELD_ID = 'line_items'
export const PAYMENT_TERMS_FIELD_ID = 'payment_terms'
