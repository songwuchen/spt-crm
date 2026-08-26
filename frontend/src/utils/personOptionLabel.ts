/** 人员下拉：姓名 + 所属部门（多部门用 / 连接） */
export function formatPersonOptionLabel(
  name: string,
  departments?: string[] | null,
): string {
  const base = String(name || '').trim()
  const depts = (departments || []).map((d) => String(d).trim()).filter(Boolean)
  if (!base) return depts.join('/') || ''
  if (!depts.length) return base
  return `${base} · ${depts.join('/')}`
}

/** 打印/导出：只要姓名，去掉「 · 部门」后缀 */
export function plainPersonDisplayName(label: unknown): string {
  const s = String(label ?? '').trim()
  const dot = s.indexOf(' · ')
  return dot >= 0 ? s.slice(0, dot).trim() : s
}
