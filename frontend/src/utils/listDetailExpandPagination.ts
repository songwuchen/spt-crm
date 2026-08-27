/**
 * Ant Design Table 异步分页陷阱：
 * 当 dataSource.length < pagination.total 且 dataSource.length > pageSize 时，
 * 表格会把当前 dataSource 再切成 pageSize 行（见 antd InternalTable pageData）。
 *
 * 明细展开（rowSpan 合并）后，单页 flat 行数常大于主表 pageSize，
 * 需临时抬高 pageSize，保证同一 API 页上的全部明细可见。
 */
export function resolveExpandDetailTablePageSize(
  basePageSize: number,
  flatRowCount: number | null | undefined,
): number {
  if (flatRowCount == null) return basePageSize
  return Math.max(basePageSize, flatRowCount)
}
