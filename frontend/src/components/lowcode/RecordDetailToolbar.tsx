/**
 * 简道云式详情工具栏：左侧链接/分享 + 操作按钮，右侧上一条/下一条。
 */
import type { ReactNode } from 'react'
import { Button, Tooltip } from 'antd'
import { LinkOutlined, ShareAltOutlined } from '@ant-design/icons'
import RecordPrevNextNav from '@/components/RecordPrevNextNav'

export type RecordToolbarAction = {
  key: string
  label: ReactNode
  icon?: ReactNode
  onClick?: () => void
  danger?: boolean
  disabled?: boolean
  hidden?: boolean
  /** 自定义渲染（如 Popconfirm 包裹删除） */
  render?: () => ReactNode
}

export default function RecordDetailToolbar({
  actions,
  onCopyLink,
  onShare,
  nav,
}: {
  actions: RecordToolbarAction[]
  onCopyLink?: () => void
  onShare?: () => void
  nav?: {
    index: number
    total: number
    disabled?: boolean
    onPrev: () => void
    onNext: () => void
  }
}) {
  const visible = actions.filter((a) => !a.hidden)

  return (
    <div className="spt-record-detail-toolbar">
      <div className="spt-record-detail-toolbar__left">
        {onCopyLink ? (
          <Tooltip title="复制链接">
            <Button
              type="text"
              size="small"
              className="spt-record-detail-toolbar__icon-btn"
              icon={<LinkOutlined />}
              aria-label="复制链接"
              onClick={onCopyLink}
            />
          </Tooltip>
        ) : null}
        {onShare ? (
          <Tooltip title="分享">
            <Button
              type="text"
              size="small"
              className="spt-record-detail-toolbar__icon-btn"
              icon={<ShareAltOutlined />}
              aria-label="分享"
              onClick={onShare}
            />
          </Tooltip>
        ) : null}
        {(onCopyLink || onShare) && visible.length > 0 ? (
          <span className="spt-record-detail-toolbar__sep" aria-hidden />
        ) : null}
        {visible.map((a) => (
          a.render ? (
            <span key={a.key} className="inline-flex">{a.render()}</span>
          ) : (
            <Button
              key={a.key}
              type="text"
              icon={a.icon}
              danger={a.danger}
              disabled={a.disabled}
              onClick={a.onClick}
            >
              {a.label}
            </Button>
          )
        ))}
      </div>
      {nav ? (
        <RecordPrevNextNav
          index={nav.index}
          total={nav.total}
          disabled={nav.disabled}
          onPrev={nav.onPrev}
          onNext={nav.onNext}
          className="spt-record-detail-toolbar__nav"
        />
      ) : null}
    </div>
  )
}
