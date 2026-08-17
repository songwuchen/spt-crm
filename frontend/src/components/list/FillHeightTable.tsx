import { Table } from 'antd'
import type { ColumnsType, ColumnType, TableProps } from 'antd/es/table'
import { useEffect, useMemo, useRef, useState } from 'react'
import ResizableTitle from './ResizableTitle'
import { clampColWidth, getColumnResizeStop } from './columnResize'

/** 列表主表默认表体高度：保证小屏也能看清多行，横向滚动条落在表体底部 */
export const DEFAULT_TABLE_BODY_HEIGHT = 480

/** 表头左右边缘多少 px 内算「可拖分隔线」 */
const EDGE_PX = 12

export type FillHeightTableProps<RecordType extends object = Record<string, unknown>> = TableProps<RecordType> & {
  /** 表体内滚动高度，默认 480 */
  bodyHeight?: number
  /** 关闭表头列宽拖拽（默认开启，配合 useListView 持久化宽度） */
  resizableColumns?: boolean
  /** 优先于内部 registry：列宽松手回调 */
  onColumnWidthChange?: (colKey: string, width: number) => void
}

function colKeyOf(c: ColumnType<unknown>): string {
  return String((c as any).key ?? (c as any).dataIndex ?? '')
}

function findResizeTarget(th: HTMLElement, clientX: number): HTMLElement | null {
  const rect = th.getBoundingClientRect()
  if (rect.right - clientX <= EDGE_PX) {
    return th.dataset.resizable === '1' ? th : null
  }
  if (clientX - rect.left <= EDGE_PX) {
    let prev = th.previousElementSibling as HTMLElement | null
    while (prev) {
      if (prev.tagName === 'TH' && prev.dataset.resizable === '1') return prev
      prev = prev.previousElementSibling as HTMLElement | null
    }
  }
  return null
}

function sumWidths(cols: ColumnsType<unknown>): number {
  let sum = 0
  for (const c of cols) {
    if (!c || typeof c !== 'object') continue
    if ('children' in c && Array.isArray((c as any).children)) {
      sum += sumWidths((c as any).children)
      continue
    }
    const w = (c as ColumnType<unknown>).width
    sum += typeof w === 'number' ? w : 120
  }
  return Math.max(sum, 800)
}

/**
 * 固定表体高度的 Table。
 * 列宽拖拽只改 columns.width（经 React 重渲染），避免手改 DOM 导致表头/表体错位。
 */
export default function FillHeightTable<RecordType extends object = Record<string, unknown>>({
  scroll,
  className,
  bodyHeight = DEFAULT_TABLE_BODY_HEIGHT,
  components,
  resizableColumns = true,
  onColumnWidthChange,
  columns,
  ...rest
}: FillHeightTableProps<RecordType>) {
  const wrapRef = useRef<HTMLDivElement>(null)
  const onWidthChangeRef = useRef(onColumnWidthChange)
  onWidthChangeRef.current = onColumnWidthChange

  // 拖拽中的临时列宽；松手后清空，改由上层 columns 持久化
  const [dragWidths, setDragWidths] = useState<Record<string, number>>({})
  // 首次拖宽后锁定 fixed + 按列宽求和，避免松手后被 scroll.x=1050 压回去
  const [pinWideLayout, setPinWideLayout] = useState(false)
  const dragWidthsRef = useRef(dragWidths)
  dragWidthsRef.current = dragWidths
  const rafRef = useRef(0)

  const mergedColumns = useMemo(() => {
    if (!resizableColumns || !columns?.length) return columns
    if (!Object.keys(dragWidths).length) return columns
    return (columns as ColumnsType<RecordType>).map((c) => {
      const k = colKeyOf(c as ColumnType<unknown>)
      if (!k || dragWidths[k] == null) return c
      return { ...c, width: dragWidths[k] }
    }) as ColumnsType<RecordType>
  }, [columns, dragWidths, resizableColumns])

  const useSumScroll =
    pinWideLayout
    || Object.keys(dragWidths).length > 0
    || scroll?.x == null
    || scroll.x === 'max-content'

  const scrollX = useMemo(() => {
    // 与线上一致：显式传数字（如线索 1050）时先按该宽度布局；拖过后再按列宽求和
    if (!useSumScroll && scroll?.x != null && scroll.x !== 'max-content') return scroll.x
    if (!mergedColumns?.length) return scroll?.x ?? 'max-content'
    const selectionW = rest.rowSelection ? 48 : 0
    return sumWidths(mergedColumns as ColumnsType<unknown>) + selectionW
  }, [mergedColumns, scroll?.x, rest.rowSelection, useSumScroll])

  const mergedScroll = {
    x: scrollX,
    y: typeof scroll?.y === 'number' ? scroll.y : bodyHeight,
  }

  const mergedComponents = resizableColumns
    ? {
        ...components,
        header: {
          ...components?.header,
          cell: ResizableTitle,
        },
      }
    : components

  useEffect(() => {
    if (!resizableColumns) return
    const root = wrapRef.current
    if (!root) return

    const onDown = (e: MouseEvent) => {
      if (e.button !== 0) return
      const raw = e.target
      if (!(raw instanceof Element)) return
      const th = raw.closest('thead th') as HTMLElement | null
      if (!th || !root.contains(th)) return

      const target = findResizeTarget(th, e.clientX)
      if (!target) return
      const colKey = target.dataset.colKey
      if (!colKey) return
      if (!onWidthChangeRef.current && !getColumnResizeStop(colKey)) return

      e.preventDefault()
      e.stopPropagation()

      setPinWideLayout(true)
      const startX = e.clientX
      const startW = target.getBoundingClientRect().width
      document.body.classList.add('spt-col-resizing')

      const onMove = (ev: MouseEvent) => {
        const next = clampColWidth(startW + (ev.clientX - startX))
        if (rafRef.current) cancelAnimationFrame(rafRef.current)
        rafRef.current = requestAnimationFrame(() => {
          setDragWidths((prev) => (
            prev[colKey] === next ? prev : { ...prev, [colKey]: next }
          ))
        })
      }
      const onUp = (ev: MouseEvent) => {
        document.removeEventListener('mousemove', onMove, true)
        document.removeEventListener('mouseup', onUp, true)
        document.body.classList.remove('spt-col-resizing')
        if (rafRef.current) cancelAnimationFrame(rafRef.current)
        const next = clampColWidth(startW + (ev.clientX - startX))
        // 先清临时宽，再交给上层持久化，避免两套宽度打架
        setDragWidths({})
        if (onWidthChangeRef.current) onWidthChangeRef.current(colKey, next)
        else getColumnResizeStop(colKey)?.(next)
      }

      document.addEventListener('mousemove', onMove, true)
      document.addEventListener('mouseup', onUp, true)
    }

    const onHover = (e: MouseEvent) => {
      if (document.body.classList.contains('spt-col-resizing')) return
      const raw = e.target
      if (!(raw instanceof Element)) {
        root.classList.remove('spt-col-resize-cursor')
        return
      }
      const th = raw.closest('thead th') as HTMLElement | null
      if (!th || !root.contains(th)) {
        root.classList.remove('spt-col-resize-cursor')
        return
      }
      const target = findResizeTarget(th, e.clientX)
      root.classList.toggle('spt-col-resize-cursor', Boolean(target?.dataset.colKey))
    }

    root.addEventListener('mousedown', onDown, true)
    root.addEventListener('mousemove', onHover)
    return () => {
      root.removeEventListener('mousedown', onDown, true)
      root.removeEventListener('mousemove', onHover)
      document.body.classList.remove('spt-col-resizing')
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [resizableColumns])

  return (
    <div ref={wrapRef} className="fill-height-table-wrap">
      <Table<RecordType>
        {...rest}
        columns={mergedColumns}
        tableLayout={useSumScroll ? 'fixed' : undefined}
        scroll={mergedScroll}
        components={mergedComponents}
        className={['fill-height-table-inner', className].filter(Boolean).join(' ')}
      />
    </div>
  )
}
