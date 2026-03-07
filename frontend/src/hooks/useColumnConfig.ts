import { useState, useCallback } from 'react'
import type { ColumnsType } from 'antd/es/table'

const STORAGE_PREFIX = 'spt_columns_'

/**
 * Manage visible columns for a list page.
 * Usage:
 *   const { visibleColumns, columnConfig, setColumnConfig } = useColumnConfig('customers', allColumns)
 *   <Table columns={visibleColumns} ... />
 *   <ColumnConfigDropdown allColumns={allColumns} config={columnConfig} onChange={setColumnConfig} />
 */
export function useColumnConfig<T = unknown>(
  pageKey: string,
  allColumns: ColumnsType<T>,
) {
  const storageKey = STORAGE_PREFIX + pageKey

  const [hiddenKeys, setHiddenKeys] = useState<string[]>(() => {
    try {
      const saved = localStorage.getItem(storageKey)
      return saved ? JSON.parse(saved) : []
    } catch {
      return []
    }
  })

  const visibleColumns = allColumns.filter((col) => {
    const key = (col as any).key || (col as any).dataIndex
    return !key || !hiddenKeys.includes(key)
  })

  const setColumnConfig = useCallback((newHiddenKeys: string[]) => {
    setHiddenKeys(newHiddenKeys)
    try {
      localStorage.setItem(storageKey, JSON.stringify(newHiddenKeys))
    } catch { /* ignore */ }
  }, [storageKey])

  const allColumnKeys = allColumns
    .map((col) => ({ key: (col as any).key || (col as any).dataIndex, title: (col as any).title }))
    .filter((c) => c.key && c.title)

  return { visibleColumns, hiddenKeys, setColumnConfig, allColumnKeys }
}
