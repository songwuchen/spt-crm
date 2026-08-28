/** 关联字段（客户/商机等）只读回显：UUID 解析失败时的友好文案 */

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isRefUuid(value: unknown): boolean {
  if (value == null || value === '') return false
  return UUID_RE.test(String(value).trim())
}

export const MISSING_CUSTOMER_LABEL = '（客户不存在或已删除）'
export const MISSING_PROJECT_LABEL = '（商机不存在或已删除）'

/** 客户字段只读展示：非 UUID 视为已是名称；UUID 未解析则友好提示 */
export function customerReadonlyLabel(
  raw: string | undefined,
  resolvedLabel: string | undefined,
  loading?: boolean,
): string {
  if (!raw) return '—'
  if (!isRefUuid(raw)) return raw
  if (loading) return '…'
  if (resolvedLabel && resolvedLabel !== raw && !isRefUuid(resolvedLabel)) return resolvedLabel
  return MISSING_CUSTOMER_LABEL
}

export function missingRefPlaceholder(kind: 'customer' | 'project'): string {
  return kind === 'customer' ? MISSING_CUSTOMER_LABEL : MISSING_PROJECT_LABEL
}
