import { Table } from 'antd'
import type { TableProps } from 'antd'

/** 列表主表默认表体高度：保证小屏也能看清多行，横向滚动条落在表体底部 */
export const DEFAULT_TABLE_BODY_HEIGHT = 480

export type FillHeightTableProps<RecordType extends object = Record<string, unknown>> = TableProps<RecordType> & {
  /** 表体内滚动高度，默认 480 */
  bodyHeight?: number
}

/**
 * 固定表体高度的 Table：内部竖滚，横向滚动条在表体底部。
 * 不占用「剩余视口」，避免小屏/筛选区较高时表被压扁看不见。
 */
export default function FillHeightTable<RecordType extends object = Record<string, unknown>>({
  scroll,
  className,
  bodyHeight = DEFAULT_TABLE_BODY_HEIGHT,
  ...rest
}: FillHeightTableProps<RecordType>) {
  const mergedScroll = {
    x: scroll?.x ?? 'max-content',
    y: typeof scroll?.y === 'number' ? scroll.y : bodyHeight,
  }

  return (
    <Table<RecordType>
      {...rest}
      scroll={mergedScroll}
      className={['fill-height-table-inner', className].filter(Boolean).join(' ')}
    />
  )
}
