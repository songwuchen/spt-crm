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
