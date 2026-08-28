/** 简道云式记录弹窗/侧边栏标题：编号 + 操作图标 + 关闭（同一行对齐）。 */
import type { ReactNode } from 'react'
import { Button } from 'antd'
import {
  BorderOutlined,
  CloseOutlined,
  ExportOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
} from '@ant-design/icons'

const iconBtnClass = 'spt-jdy-modal-title__btn text-slate-500 hover:text-slate-800'

export default function JdyRecordModalTitle({
  title,
  editing,
  fullscreen,
  onToggleFullscreen,
  onClose,
  variant = 'modal',
  onOpenInSidebar,
  onOpenInModal,
}: {
  title: ReactNode
  editing?: boolean
  fullscreen: boolean
  onToggleFullscreen: () => void
  onClose?: () => void
  /** modal：居中弹窗；drawer：右侧侧边栏 */
  variant?: 'modal' | 'drawer'
  /** 居中弹窗 → 侧边打开（仅 modal） */
  onOpenInSidebar?: () => void
  /** 侧边栏 → 居中弹窗（仅 drawer） */
  onOpenInModal?: () => void
}) {
  return (
    <div className="spt-jdy-modal-title">
      <div className="spt-jdy-modal-title__label">
        <span className="spt-jdy-modal-title__no truncate">{title}</span>
        {editing ? (
          <span className="shrink-0 rounded px-1.5 py-0.5 text-xs bg-sky-50 text-sky-700 border border-sky-100">
            编辑中
          </span>
        ) : null}
      </div>
      <div className="spt-jdy-modal-title__actions">
        {variant === 'modal' && onOpenInSidebar ? (
          <Button
            type="text"
            size="small"
            className={iconBtnClass}
            icon={<ExportOutlined />}
            title="从侧边打开页面"
            aria-label="从侧边打开页面"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onOpenInSidebar()
            }}
          />
        ) : null}
        {variant === 'drawer' && onOpenInModal ? (
          <Button
            type="text"
            size="small"
            className={iconBtnClass}
            icon={<BorderOutlined />}
            title="居中打开"
            aria-label="居中打开"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onOpenInModal()
            }}
          />
        ) : null}
        <Button
          type="text"
          size="small"
          className={iconBtnClass}
          icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
          title={fullscreen ? '退出全屏' : '全屏查看'}
          aria-label={fullscreen ? '退出全屏' : '全屏查看'}
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onToggleFullscreen()
          }}
        />
        {onClose ? (
          <Button
            type="text"
            size="small"
            className={iconBtnClass}
            icon={<CloseOutlined />}
            title="关闭"
            aria-label="关闭"
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              onClose()
            }}
          />
        ) : null}
      </div>
    </div>
  )
}
