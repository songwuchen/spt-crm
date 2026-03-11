import { useRef, useCallback, useEffect } from 'react'
import { Modal } from 'antd'

interface CountdownConfirmOptions {
  title: string
  content: string
  okText?: string
  okType?: 'primary' | 'danger'
  countdown?: number // seconds, default 3
  onOk: () => void | Promise<void>
}

/**
 * Hook for destructive action confirmation with a countdown timer.
 * The OK button is disabled for `countdown` seconds to prevent accidental clicks.
 */
export function useCountdownConfirm() {
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return clearTimer
  }, [clearTimer])

  const confirm = useCallback((opts: CountdownConfirmOptions) => {
    clearTimer()
    const seconds = opts.countdown ?? 3
    let remaining = seconds

    const modal = Modal.confirm({
      title: opts.title,
      content: opts.content,
      okText: `${opts.okText || '确认'} (${remaining}s)`,
      okType: opts.okType || 'danger',
      okButtonProps: { disabled: true },
      onOk: opts.onOk,
      onCancel: clearTimer,
    })

    timerRef.current = setInterval(() => {
      remaining -= 1
      if (remaining <= 0) {
        clearTimer()
        modal.update({
          okText: opts.okText || '确认',
          okButtonProps: { disabled: false },
        })
      } else {
        modal.update({
          okText: `${opts.okText || '确认'} (${remaining}s)`,
        })
      }
    }, 1000)
  }, [clearTimer])

  return confirm
}
