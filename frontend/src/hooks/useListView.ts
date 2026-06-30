import { useState, useMemo, useCallback } from 'react'
import type { ColumnsType } from 'antd/es/table'
import type { FilterDsl } from '@/api/searchSchema'

const PREFIX = 'spt_listcfg_'

export interface ColumnState {
  hidden: string[]
  order: string[]
}

export interface ListSort {
  by: string
  order: 'asc' | 'desc'
}

/** 一个「视图」的完整内容：高级筛选 + 列配置 + 排序。 */
export interface ListViewPayload {
  filters: { advanced: FilterDsl | null }
  columns: ColumnState
  sort_by: string | null
  sort_order: string | null
}

function colKey(c: any): string {
  return String(c?.key ?? c?.dataIndex ?? '')
}

/**
 * 列表视图控制器：统一管理高级筛选条件、列配置（显隐+排序）与排序，
 * 列配置默认持久化到 localStorage；可被「保存视图」整体读写。
 */
export function useListView<T = any>(
  resource: string,
  baseColumns: ColumnsType<T>,
  opts: { pageKey: string },
) {
  const storageKey = PREFIX + opts.pageKey

  const [advanced, setAdvanced] = useState<FilterDsl | null>(null)
  const [sort, setSort] = useState<ListSort | null>(null)
  const [colState, setColStateRaw] = useState<ColumnState>(() => {
    try {
      const s = localStorage.getItem(storageKey)
      return s ? JSON.parse(s) : { hidden: [], order: [] }
    } catch {
      return { hidden: [], order: [] }
    }
  })

  const setColState = useCallback((cs: ColumnState) => {
    setColStateRaw(cs)
    try { localStorage.setItem(storageKey, JSON.stringify(cs)) } catch { /* ignore */ }
  }, [storageKey])

  // 全部列的元信息（key + 标题），用于列配置面板
  const allMeta = useMemo(
    () => baseColumns
      .map((c) => ({ key: colKey(c), title: (c as any).settingTitle ?? (c as any).title }))
      .filter((c) => c.key && c.title),
    [baseColumns],
  )

  // 应用「排序 + 显隐」后用于 <Table> 的列
  const columns = useMemo(() => {
    const byKey = new Map(baseColumns.map((c) => [colKey(c), c]))
    const ordered: ColumnsType<T> = []
    const seen = new Set<string>()
    for (const k of colState.order) {
      const c = byKey.get(k)
      if (c) { ordered.push(c); seen.add(k) }
    }
    for (const c of baseColumns) {
      const k = colKey(c)
      if (!seen.has(k)) ordered.push(c)
    }
    return ordered.filter((c) => {
      const k = colKey(c)
      return !k || !colState.hidden.includes(k)
    })
  }, [baseColumns, colState])

  // 合并进列表请求的参数
  const buildParams = useCallback((): Record<string, unknown> => {
    const p: Record<string, unknown> = {}
    if (advanced && advanced.rules.length) p.filter = JSON.stringify(advanced)
    if (sort) { p.sort_by = sort.by; p.sort_order = sort.order }
    return p
  }, [advanced, sort])

  // 应用一个保存的视图
  const applyView = useCallback((v: any) => {
    const adv = v?.filters?.advanced ?? null
    setAdvanced(adv && Array.isArray(adv.rules) ? adv : null)
    if (v?.columns) setColState({ hidden: v.columns.hidden || [], order: v.columns.order || [] })
    if (v?.sort_by) setSort({ by: v.sort_by, order: v.sort_order === 'asc' ? 'asc' : 'desc' })
    else setSort(null)
  }, [setColState])

  // 当前视图内容（用于保存）
  const currentPayload = useCallback((): ListViewPayload => ({
    filters: { advanced },
    columns: colState,
    sort_by: sort?.by ?? null,
    sort_order: sort?.order ?? null,
  }), [advanced, colState, sort])

  const resetColumns = useCallback(() => setColState({ hidden: [], order: [] }), [setColState])

  return {
    resource,
    advanced, setAdvanced,
    sort, setSort,
    colState, setColState, resetColumns,
    columns, allMeta,
    buildParams, applyView, currentPayload,
    activeCount: advanced?.rules?.length ?? 0,
  }
}

export type ListViewController<T = any> = ReturnType<typeof useListView<T>>
