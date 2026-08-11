/** Modal 标题栏右侧全屏切换（避开右上角关闭按钮）。 */
import type { CSSProperties, ReactNode } from 'react'
import { Button } from 'antd'
import { FullscreenOutlined, FullscreenExitOutlined } from '@ant-design/icons'

export default function ModalFullscreenTitle({
  title,
  fullscreen,
  onToggle,
}: {
  title: ReactNode
  fullscreen: boolean
  onToggle: () => void
}) {
  return (
    <div className="flex items-center gap-2 min-w-0 pr-8">
      <span className="truncate">{title}</span>
      <Button
        type="text"
        size="small"
        className="shrink-0 ml-auto text-slate-500 hover:text-slate-800"
        icon={fullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
        onClick={(e) => {
          e.preventDefault()
          e.stopPropagation()
          onToggle()
        }}
        title={fullscreen ? '退出全屏' : '全屏查看'}
        aria-label={fullscreen ? '退出全屏' : '全屏查看'}
      />
    </div>
  )
}

/** Ant Design Modal 全屏样式参数 */
export function modalFullscreenProps(fullscreen: boolean, normalWidth: number | string) {
  if (!fullscreen) {
    return {
      width: normalWidth as number | string,
      style: undefined as CSSProperties | undefined,
      styles: { body: { paddingTop: 8 } } as Record<string, CSSProperties>,
      wrapClassName: undefined as string | undefined,
    }
  }
  return {
    width: '100%' as const,
    style: { top: 0, paddingBottom: 0, maxWidth: '100vw', margin: 0 } as CSSProperties,
    styles: {
      body: {
        paddingTop: 8,
        height: 'calc(100vh - 110px)',
        maxHeight: 'calc(100vh - 110px)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
      },
    } as Record<string, CSSProperties>,
    wrapClassName: 'spt-modal-fullscreen',
  }
}
