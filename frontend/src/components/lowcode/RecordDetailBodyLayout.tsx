/** 简道云式详情弹窗主体：左表单 + 右流程/日志侧栏。 */
import type { ReactNode } from 'react'

export default function RecordDetailBodyLayout({
  /** 全屏弹窗：占满剩余高度，左右栏可独立滚动 */
  fillHeight,
  fullscreen,
  contentMaxH,
  main,
  side,
  showSide,
}: {
  /** @deprecated 同 fillHeight */
  fullscreen?: boolean
  fillHeight?: boolean
  contentMaxH?: number | string
  main: ReactNode
  side?: ReactNode
  showSide?: boolean
}) {
  const stretch = fillHeight ?? fullscreen ?? false
  const paneH = contentMaxH
    ? { height: contentMaxH, maxHeight: contentMaxH, minHeight: 0 }
    : undefined
  return (
    <div
      className={`spt-record-detail-body${stretch ? ' spt-record-detail-body--fill' : ''}`}
      style={stretch && paneH ? { minHeight: 0, flex: 1 } : undefined}
    >
      <div
        className="spt-record-detail-body__main"
        style={paneH}
      >
        {main}
      </div>
      {showSide && side ? (
        <div
          className="spt-record-detail-body__side"
          style={paneH}
        >
          {side}
        </div>
      ) : null}
    </div>
  )
}
