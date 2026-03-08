import { useRef, useCallback } from 'react'
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

  const confirm = useCallback((opts: CountdownConfirmOptions) => {
    const seconds = opts.countdown ?? 3
    let remaining = seconds

    const modal = Modal.confirm({
      title: opts.title,
      content: opts.content,
      okText: `${opts.okText || '确认'} (${remaining}s)`,
      okType: opts.okType || 'danger',
      okButtonProps: { disabled: true },
      onOk: opts.onOk,
    })

    timerRef.current = setInterval(() => {
      remaining -= 1
      if (remaining <= 0) {
        if (timerRef.current) clearInterval(timerRef.current)
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
  }, [])

  return confirm
}
