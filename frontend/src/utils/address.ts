// 结构化地址的唯一规范化展示工具。所有列表/详情/导出/移动端都应经由此函数拼接，
// 避免出现「编辑写一套形状、展示读另一套形状」导致空白的问题。

export interface RegionParts {
  province?: string | null
  city?: string | null
  district?: string | null
  /** legacy 自由文本地区，作为无结构化省市区时的回退 */
  region?: string | null
}

/** 将省/市/区县拼成展示字符串；无结构化数据时回退到 legacy region 文本；都没有则空串。 */
export function formatRegion(p: RegionParts | null | undefined, sep = ' · '): string {
  if (!p) return ''
  const parts = [p.province, p.city, p.district].filter(Boolean)
  if (parts.length > 0) return parts.join(sep)
  return p.region || ''
}
