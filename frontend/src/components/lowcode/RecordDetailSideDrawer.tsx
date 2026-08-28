/** 简道云式侧边详情：列表保留左侧，记录从右侧滑出（默认占视口 70%）。 */
import type { ReactNode } from 'react'
import { Drawer } from 'antd'
import JdyRecordModalTitle from '@/components/lowcode/JdyRecordModalTitle'

/** 非全屏侧边详情宽度：简道云「从侧边打开」约占视口 75%，左侧列表约 25% */
export const RECORD_DETAIL_DRAWER_WIDTH = '75vw'

export default function RecordDetailSideDrawer({
  open,
  title,
  editing,
  fullscreen,
  onToggleFullscreen,
  onClose,
  onOpenInModal,
  footer,
  width = RECORD_DETAIL_DRAWER_WIDTH,
  children,
}: {
  open: boolean
  title: ReactNode
  editing?: boolean
  fullscreen: boolean
  onToggleFullscreen: () => void
  onClose: () => void
  /** 侧边栏 → 居中弹窗 */
  onOpenInModal?: () => void
  footer?: ReactNode
  /** 默认 70vw；全屏时仍为 100% */
  width?: number | string
  children: ReactNode
}) {
  return (
    <Drawer
      open={open}
      placement="right"
      width={fullscreen ? '100%' : width}      className={
        fullscreen
          ? 'spt-jdy-record-drawer spt-jdy-record-drawer--fill'
          : 'spt-jdy-record-drawer'
      }
      rootClassName={
        fullscreen
          ? 'spt-jdy-record-drawer-root spt-drawer-fullscreen'
          : 'spt-jdy-record-drawer-root'
      }
      closable={false}
      mask
      maskClosable
      destroyOnClose
      onClose={onClose}
      title={(
        <JdyRecordModalTitle
          variant="drawer"
          title={title}
          editing={editing}
          fullscreen={fullscreen}
          onToggleFullscreen={onToggleFullscreen}
          onOpenInModal={onOpenInModal}
          onClose={onClose}
        />
      )}
      footer={footer}
      styles={{
        body: {
          padding: '0 16px 16px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          maxHeight: fullscreen ? 'calc(100vh - 110px)' : 'calc(100vh - 120px)',
        },
      }}
    >
      {children}
    </Drawer>
  )
}
