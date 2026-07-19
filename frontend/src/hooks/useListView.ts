import { useState, useMemo, useCallback, useEffect } from 'react'
import type { ColumnsType } from 'antd/es/table'
import type { FilterDsl } from '@/api/searchSchema'
import { lowcodeApi } from '@/api/lowcode'
import { buildCustomFieldColumns, type CustomFieldDef } from '@/components/list/customFieldColumns'

const PREFIX = 'spt_listcfg_'

export interface ColumnState {
  hidden: string[]
  order: string[]
  /** 「调出显示」白名单：自定义(扩展)字段列默认隐藏，仅当其 key 在此列表时才显示。 */
  shown?: string[]
}

export interface ColMeta {
  key: string
  title: React.ReactNode
  /** 是否为可选调出的列（默认隐藏，用 shown 而非 hidden 控制显隐）。 */
  optIn?: boolean
  /** 是否来自扩展(自定义)字段，仅用于在列配置面板打「自定义」标签。 */
  custom?: boolean
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
 *
 * 传入 opts.entityType 时，自动拉取该实体的扩展(自定义)字段并追加为列，
 * 这些列默认隐藏，可在「列配置」中勾选调出显示。
 */
export function useListView<T = any>(
  resource: string,
  baseColumns: ColumnsType<T>,
  opts: { pageKey: string; entityType?: string },
) {
  const storageKey = PREFIX + opts.pageKey
  const entityType = opts.entityType

  const [advanced, setAdvanced] = useState<FilterDsl | null>(null)
  const [sort, setSort] = useState<ListSort | null>(null)
  const [customCols, setCustomCols] = useState<ColumnsType<T>>([])
  const [colState, setColStateRaw] = useState<ColumnState>(() => {
    try {
      const s = localStorage.getItem(storageKey)
      return s ? JSON.parse(s) : { hidden: [], order: [], shown: [] }
    } catch {
      return { hidden: [], order: [], shown: [] }
    }
  })

  // 拉取实体扩展字段，生成「可调出」的自定义字段列
  useEffect(() => {
    if (!entityType) { setCustomCols([]); return }
    let alive = true
    lowcodeApi.entityFields(entityType)
      .then((r) => {
        if (!alive) return
        const defs = (r.data?.field_definitions as unknown as CustomFieldDef[]) || []
        setCustomCols(buildCustomFieldColumns<T>(defs))
      })
      .catch(() => { /* 扩展字段不可用时静默跳过，不影响列表 */ })
    return () => { alive = false }
  }, [entityType])

  // 全部列 = 业务列 + 自定义字段列。自定义列插到末尾「固定右侧」列(如操作列)之前，
  // 否则固定列后出现非固定列会导致 antd 布局告警/横向滚动异常。
  const allColumns = useMemo(() => {
    if (!customCols.length) return baseColumns
    const cols = [...baseColumns]
    let insertAt = cols.length
    while (insertAt > 0 && (cols[insertAt - 1] as any)?.fixed === 'right') insertAt--
    return [...cols.slice(0, insertAt), ...customCols, ...cols.slice(insertAt)] as ColumnsType<T>
  }, [baseColumns, customCols])

  const setColState = useCallback((cs: ColumnState) => {
    setColStateRaw(cs)
    try { localStorage.setItem(storageKey, JSON.stringify(cs)) } catch { /* ignore */ }
  }, [storageKey])

  // 全部列的元信息（key + 标题 + 是否为可调出的自定义列），用于列配置面板
  const allMeta = useMemo<ColMeta[]>(
    () => allColumns
      .map((c) => ({
        key: colKey(c),
        title: (c as any).settingTitle ?? (c as any).title,
        // 扩展字段列天然可调出；原生列可用 __optIn 单独声明为「默认隐藏、可调出」
        optIn: !!((c as any).__optIn || (c as any).__customField),
        custom: !!(c as any).__customField,
      }))
      .filter((c) => c.key && c.title),
    [allColumns],
  )

  // 应用「排序 + 显隐」后用于 <Table> 的列
  const columns = useMemo(() => {
    const shown = colState.shown || []
    const byKey = new Map(allColumns.map((c) => [colKey(c), c]))
    const ordered: ColumnsType<T> = []
    const seen = new Set<string>()
    for (const k of colState.order) {
      const c = byKey.get(k)
      if (c) { ordered.push(c); seen.add(k) }
    }
    for (const c of allColumns) {
      const k = colKey(c)
      if (!seen.has(k)) ordered.push(c)
    }
    return ordered.filter((c) => {
      const k = colKey(c)
      if (!k) return true
      // 可调出的列（扩展字段列 + 声明了 __optIn 的原生列）：默认隐藏，需在 shown 白名单里才显示
      if ((c as any).__optIn || (c as any).__customField) return shown.includes(k)
      return !colState.hidden.includes(k)
    })
  }, [allColumns, colState])

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
    if (v?.columns) setColState({
      hidden: v.columns.hidden || [],
      order: v.columns.order || [],
      shown: v.columns.shown || [],
    })
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

  const resetColumns = useCallback(() => setColState({ hidden: [], order: [], shown: [] }), [setColState])

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
