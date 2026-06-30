export const OP_LABELS: Record<string, string> = {
  eq: '等于',
  ne: '不等于',
  contains: '包含',
  not_contains: '不包含',
  starts_with: '开头是',
  ends_with: '结尾是',
  in: '属于',
  not_in: '不属于',
  gt: '大于',
  gte: '大于等于',
  lt: '小于',
  lte: '小于等于',
  between: '区间',
  before: '早于',
  after: '晚于',
  relative: '相对时间',
  is_empty: '为空',
  is_not_empty: '不为空',
  me: '是我',
}

export type ValueKind = 'none' | 'single' | 'pair' | 'list'

/** 操作符需要什么样的值输入。 */
export function valueKind(op: string): ValueKind {
  if (op === 'is_empty' || op === 'is_not_empty' || op === 'me') return 'none'
  if (op === 'between') return 'pair'
  if (op === 'in' || op === 'not_in') return 'list'
  return 'single'
}

export const RELATIVE_OPTIONS: { value: string; label: string }[] = [
  { value: 'today', label: '今天' },
  { value: 'yesterday', label: '昨天' },
  { value: 'last7', label: '近 7 天' },
  { value: 'last30', label: '近 30 天' },
  { value: 'this_week', label: '本周' },
  { value: 'this_month', label: '本月' },
  { value: 'last_month', label: '上月' },
  { value: 'this_year', label: '今年' },
]
