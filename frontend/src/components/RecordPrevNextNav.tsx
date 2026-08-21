/** 详情弹窗：上一条 / 下一条（对齐简道云，支持 ← →） */
import { useEffect } from 'react'
import { Button, Tooltip } from 'antd'
import { LeftOutlined, RightOutlined } from '@ant-design/icons'

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false
  const tag = el.tagName
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true
  if (el.isContentEditable) return true
  return Boolean(el.closest(
    'input, textarea, select, [contenteditable="true"], .ant-select-dropdown, .ant-picker-dropdown, .ant-mentions',
  ))
}

export default function RecordPrevNextNav({
  index,
  total,
  onPrev,
  onNext,
  disabled,
  className,
}: {
  /** 当前下标，0-based；未知时传 -1 */
  index: number
  total: number
  onPrev: () => void
  onNext: () => void
  disabled?: boolean
  className?: string
}) {
  const current = index >= 0 ? index + 1 : 0
  const canPrev = !disabled && index > 0
  const canNext = !disabled && index >= 0 && index < total - 1

  useEffect(() => {
    if (disabled || total <= 0 || index < 0) return
    const onKey = (e: KeyboardEvent) => {
      if (e.isComposing || e.altKey || e.ctrlKey || e.metaKey) return
      if (isTypingTarget(e.target)) return
      if (e.key === 'ArrowLeft' && canPrev) {
        e.preventDefault()
        onPrev()
      } else if (e.key === 'ArrowRight' && canNext) {
        e.preventDefault()
        onNext()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [disabled, total, index, canPrev, canNext, onPrev, onNext])

  if (total <= 0) return null

  return (
    <div className={`inline-flex items-center gap-0.5 text-slate-600 ${className || ''}`}>
      <Tooltip title="查看上一条数据，快捷键「←」">
        <Button
          type="text"
          size="small"
          icon={<LeftOutlined />}
          disabled={!canPrev}
          onClick={onPrev}
          aria-label="上一条"
        />
      </Tooltip>
      <span className="min-w-[3.5rem] text-center text-sm tabular-nums select-none">
        {current > 0 ? `${current} / ${total}` : `— / ${total}`}
      </span>
      <Tooltip title="查看下一条数据，快捷键「→」">
        <Button
          type="text"
          size="small"
          icon={<RightOutlined />}
          disabled={!canNext}
          onClick={onNext}
          aria-label="下一条"
        />
      </Tooltip>
    </div>
  )
}
