import { useEffect, useState } from 'react'
import {
  fetchUnifiedPending,
  APPROVAL_PENDING_CHANGED,
} from '@/api/unifiedApprovals'

export { APPROVAL_PENDING_CHANGED }

export function notifyApprovalPendingChanged() {
  window.dispatchEvent(new Event(APPROVAL_PENDING_CHANGED))
}

/**
 * 当前用户待审批数量（新旧引擎合计）。
 * 用于侧栏角标；失败时保持上次值，避免闪成 0。
 * @param refreshKey 变化时立即重拉（如路由 pathname）
 */
export function useApprovalPendingCount(pollMs = 60_000, refreshKey?: string) {
  const [count, setCount] = useState(0)

  useEffect(() => {
    let alive = true
    const load = async () => {
      try {
        const r = await fetchUnifiedPending()
        if (alive) setCount(r.total || 0)
      } catch {
        /* 角标非关键路径，静默失败 */
      }
    }
    void load()
    const timer = window.setInterval(() => { void load() }, pollMs)
    const onFocus = () => { void load() }
    const onChanged = () => { void load() }
    window.addEventListener('focus', onFocus)
    window.addEventListener(APPROVAL_PENDING_CHANGED, onChanged)
    return () => {
      alive = false
      window.clearInterval(timer)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener(APPROVAL_PENDING_CHANGED, onChanged)
    }
  }, [pollMs, refreshKey])

  return count
}
