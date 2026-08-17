import type { CSSProperties, ReactNode } from 'react'
import { useLayoutEffect } from 'react'
import { registerColumnResizeStop } from './columnResize'

export type ResizableTitleProps = {
  width?: number
  colKey?: string
  onResizeStop?: (width: number) => void
  children?: ReactNode
  className?: string
  style?: CSSProperties
  [key: string]: unknown
}

/**
 * 表头单元格：写入 data-col-key，供 FillHeightTable 按「列缝」事件委托拖拽。
 * 只要有 colKey + width 即可拖（松手回调可走 props 或 FillHeightTable.onColumnWidthChange）。
 */
export default function ResizableTitle({
  onResizeStop,
  width,
  colKey,
  children,
  className,
  style,
  ...rest
}: ResizableTitleProps) {
  const fromData = rest['data-col-key']
  const key = colKey || (typeof fromData === 'string' ? fromData : undefined)
  const canResize = Boolean(key && typeof width === 'number' && width > 0)

  useLayoutEffect(() => {
    if (canResize && key && onResizeStop) {
      registerColumnResizeStop(key, onResizeStop)
    }
  }, [canResize, key, onResizeStop])

  return (
    <th
      {...rest}
      className={[canResize ? 'spt-resizable-th' : '', className].filter(Boolean).join(' ')}
      style={{ ...style, ...(typeof width === 'number' ? { width } : null), position: 'relative' }}
      data-col-key={canResize ? key : undefined}
      data-resizable={canResize ? '1' : undefined}
    >
      {children}
      {canResize ? <span className="spt-col-resize-handle" aria-hidden /> : null}
    </th>
  )
}
