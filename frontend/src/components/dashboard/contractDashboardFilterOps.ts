/** 合同管理仪表盘 — 筛选运算符定义 */

export type TextFilterOp =
  | 'eq' | 'ne' | 'contains' | 'not_contains' | 'in' | 'nin' | 'is_empty' | 'is_not_empty'

export type DateFilterOp =
  | 'preset' | 'between' | 'eq' | 'ne' | 'gte' | 'lte' | 'is_empty' | 'is_not_empty'

export type RefFilterOp =
  | 'eq' | 'ne' | 'in' | 'nin' | 'is_empty' | 'is_not_empty'

export const TEXT_FILTER_OPS: { value: TextFilterOp; label: string }[] = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'in', label: '等于任意一个' },
  { value: 'nin', label: '不等于任意一个' },
  { value: 'contains', label: '包含' },
  { value: 'not_contains', label: '不包含' },
  { value: 'is_empty', label: '为空' },
  { value: 'is_not_empty', label: '不为空' },
]

export const DATE_FILTER_OPS: { value: DateFilterOp; label: string }[] = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lte', label: '小于等于' },
  { value: 'between', label: '选择范围' },
  { value: 'preset', label: '动态筛选' },
  { value: 'is_empty', label: '为空' },
  { value: 'is_not_empty', label: '不为空' },
]

export const REF_FILTER_OPS: { value: RefFilterOp; label: string }[] = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
  { value: 'in', label: '等于任意一个' },
  { value: 'nin', label: '不等于任意一个' },
  { value: 'is_empty', label: '为空' },
  { value: 'is_not_empty', label: '不为空' },
]

export function needsTextValue(op: TextFilterOp) {
  return !['is_empty', 'is_not_empty'].includes(op)
}

export function needsDateValue(op: DateFilterOp) {
  return !['is_empty', 'is_not_empty'].includes(op)
}

export function needsRefValue(op: RefFilterOp) {
  return !['is_empty', 'is_not_empty'].includes(op)
}

export function isMultiTextOp(op: TextFilterOp) {
  return op === 'in' || op === 'nin'
}

export function isMultiRefOp(op: RefFilterOp) {
  return op === 'in' || op === 'nin'
}

export function isSingleRefOp(op: RefFilterOp) {
  return op === 'eq' || op === 'ne'
}
