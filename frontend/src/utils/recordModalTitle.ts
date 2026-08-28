/** 记录弹窗标题：优先流水号 / business_no（对齐简道云顶栏编号）。 */
export function resolveRecordDisplayNo(opts: {
  businessNo?: string | null
  formData?: Record<string, unknown> | null
  fallback?: string
}): string {
  const fd = opts.formData || {}
  for (const key of ['serial_no', 'business_no', 'review_code']) {
    const raw = fd[key]
    if (typeof raw === 'string' && raw.trim()) return raw.trim()
  }
  const bn = (opts.businessNo || '').trim()
  if (bn) return bn
  return opts.fallback || '查看记录'
}
