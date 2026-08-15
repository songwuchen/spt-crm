import { useEffect, useState } from 'react'
import { notificationApi } from '@/api/notification'

export const NOTIFICATION_UNREAD_CHANGED = 'spt:notification-unread-changed'

export function notifyNotificationUnreadChanged() {
  window.dispatchEvent(new Event(NOTIFICATION_UNREAD_CHANGED))
}

/**
 * 当前用户未读通知数。侧栏「通知中心」角标；失败时保持上次值。
 */
export function useNotificationUnreadCount(pollMs = 60_000, refreshKey?: string) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const r = await notificationApi.unreadCount()
        if (alive) setCount(r.data?.count ?? 0)
      } catch {
        /* 角标非关键路径，静默失败 */
      }
    }
    void load()
    const timer = window.setInterval(() => { void load() }, pollMs)
    const onFocus = () => { void load() }
    const onChanged = () => { void load() }
    window.addEventListener('focus', onFocus)
    window.addEventListener(NOTIFICATION_UNREAD_CHANGED, onChanged)
    return () => {
      alive = false
      window.clearInterval(timer)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener(NOTIFICATION_UNREAD_CHANGED, onChanged)
    }
  }, [pollMs, refreshKey])

  return count
}
