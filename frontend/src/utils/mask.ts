// 字段脱敏哨兵值的统一判定与格式化。
//
// 后端把用户无权查看的字段值整体替换成 "***"：
// - 按权限脱敏 app/common/field_mask.py（成本/毛利/折扣等嵌套响应体）
// - 按角色脱敏 app/domains/lowcode/field_permission.py（实体的原生与扩展字段）
// 对数字字段来说这意味着接口返回的是字符串，前端直接 Number() 会得到 NaN，页面上就出现「¥NaN」。
//
// 这套判定此前在 QuoteDetail / MobileQuoteDetail / QuoteList / ContractList 各写了一份，
// 新页面很容易漏掉。统一收在这里。
export const MASK_VALUE = '***'

/** 是否为后端下发的脱敏哨兵（严格匹配）。 */
export function isMaskValue(v: unknown): boolean {
  return v === MASK_VALUE
}

/**
 * 数值字段是否被脱敏 —— 刻意比严格匹配更宽：任何无法转成有限数的字符串都当作脱敏。
 * 这样即便后端换了哨兵写法，也不会退化成页面上显示 NaN。
 */
export function isMasked(v: unknown): boolean {
  return typeof v === 'string' && !Number.isFinite(Number(v))
}

/** 金额格式化，脱敏时输出 "***"，空值输出 "-"。 */
export function fmtMoney(v: unknown): string {
  if (v == null) return '-'
  if (isMasked(v)) return MASK_VALUE
  const n = Number(v)
  return Number.isFinite(n) ? `¥${n.toLocaleString()}` : '-'
}

/** 百分比格式化(入参为小数，如 0.15 → 15.0%)，脱敏时输出 "***"。 */
export function fmtPct(v: unknown): string {
  if (v == null) return '-'
  if (isMasked(v)) return MASK_VALUE
  const n = Number(v)
  return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%` : '-'
}
