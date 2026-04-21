import { useState, useEffect, useRef, useCallback } from 'react'
import { Badge, Spin, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { notificationApi, type NotificationItem } from '@/api/notification'
import { useWebSocket } from '@/hooks/useWebSocket'

const typeIcons: Record<string, { icon: string; color: string }> = {
  approval_pending: { icon: 'pending_actions', color: '#f59e0b' },
  approval_decided: { icon: 'task_alt', color: '#10b981' },
  stage_advance: { icon: 'swap_horiz', color: '#6366f1' },
  stage_change: { icon: 'swap_horiz', color: '#6366f1' },
  contract_signed: { icon: 'verified', color: '#059669' },
  ticket_assigned: { icon: 'support_agent', color: '#0ea5e9' },
  payment_overdue: { icon: 'warning', color: '#ef4444' },
  ai_task_complete: { icon: 'smart_toy', color: '#8b5cf6' },
  gate_blocked: { icon: 'block', color: '#f97316' },
  system: { icon: 'info', color: '#64748b' },
}

export default function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(false)
  const panelRef = useRef<HTMLDivElement>(null)

  const fetchCount = async () => {
    try {
      const res = await notificationApi.unreadCount()
      setUnread(res.data.count)
    } catch {}
  }

  const fetchItems = async () => {
    setLoading(true)
    try {
      const res = await notificationApi.list()
      setItems(res.data)
    } finally {
      setLoading(false)
    }
  }

  // Real-time WebSocket push handler
  const handleWsMessage = useCallback((data: Record<string, unknown>) => {
    if (data.event === 'notification') {
      const n = data.data as NotificationItem
      setItems((prev) => [n, ...prev])
      setUnread((c) => c + 1)
      message.info({ content: n.title, duration: 4, key: n.id })
    }
  }, [])

  useWebSocket(handleWsMessage)

  useEffect(() => {
    fetchCount()
    // Fallback polling every 60s (WS handles real-time)
    const timer = setInterval(fetchCount, 60000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (open) fetchItems()
  }, [open])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const handleClick = (item: NotificationItem) => {
    if (!item.is_read) {
      notificationApi.markRead([item.id])
      setItems((prev) => prev.map((n) => n.id === item.id ? { ...n, is_read: true } : n))
      setUnread((c) => Math.max(0, c - 1))
    }
    setOpen(false)

    if (item.biz_type === 'approval_flow' || item.biz_type === 'approval') {
      navigate('/approvals')
    } else if (item.biz_type === 'service_ticket') {
      navigate(`/service-tickets/${item.biz_id}`)
    } else if (item.biz_type === 'project') {
      navigate(`/opportunities/${item.biz_id}`)
    } else if (item.biz_type === 'contract' && item.biz_id) {
      navigate(`/opportunities/contracts/${item.biz_id}`)
    } else if (item.biz_type === 'customer' && item.biz_id) {
      navigate(`/customers/${item.biz_id}`)
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllRead()
      setItems((prev) => prev.map((n) => ({ ...n, is_read: true })))
      setUnread(0)
    } catch {
      message.error('操作失败，请重试')
    }
  }

  const timeAgo = (dateStr: string) => {
    const d = new Date(dateStr)
    const diff = Date.now() - d.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return '刚刚'
    if (mins < 60) return `${mins}分钟前`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}小时前`
    const days = Math.floor(hrs / 24)
    return `${days}天前`
  }

  return (
    <div ref={panelRef} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(!open)}
        className="relative flex items-center justify-center w-9 h-9 rounded-lg hover:bg-slate-100 transition-colors"
      >
        <Badge count={unread} size="small" offset={[-2, 2]}>
          <span className="material-symbols-outlined" style={{ fontSize: 22, color: '#475569' }}>notifications</span>
        </Badge>
      </button>

      {open && (
        <div
          className="absolute right-0 top-full mt-2 bg-white rounded-xl border border-slate-200 shadow-xl overflow-hidden"
          style={{ width: 380, maxHeight: 480, zIndex: 1000 }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
            <h3 className="text-sm font-bold text-slate-900">通知</h3>
            {unread > 0 && (
              <button onClick={handleMarkAllRead}
                className="text-sm font-semibold text-primary hover:underline bg-transparent border-none cursor-pointer">
                全部已读
              </button>
            )}
          </div>

          {/* List */}
          <div className="overflow-y-auto" style={{ maxHeight: 360 }}>
            {loading ? (
              <div className="flex justify-center py-8"><Spin /></div>
            ) : items.length === 0 ? (
              <div className="text-center py-10 text-slate-400 text-sm">暂无通知</div>
            ) : (
              items.slice(0, 20).map((item) => {
                const t = typeIcons[item.type] || typeIcons.system
                return (
                  <div
                    key={item.id}
                    onClick={() => handleClick(item)}
                    className={`flex gap-3 px-4 py-3 cursor-pointer transition-colors hover:bg-slate-50 ${
                      !item.is_read ? 'bg-blue-50/50' : ''
                    }`}
                  >
                    <div
                      className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
                      style={{ background: `${t.color}15` }}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 18, color: t.color }}>{t.icon}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-[13px] leading-tight ${!item.is_read ? 'font-bold text-slate-900' : 'text-slate-700'}`}>
                          {item.title}
                        </span>
                        {!item.is_read && <span className="w-2 h-2 rounded-full bg-primary flex-shrink-0" />}
                      </div>
                      {item.content && (
                        <div className="text-[11px] text-slate-500 mt-0.5 truncate">{item.content}</div>
                      )}
                      <div className="text-[10px] text-slate-400 mt-1">{timeAgo(item.created_at)}</div>
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Footer */}
          {items.length > 0 && (
            <div className="border-t border-slate-100 px-4 py-2 text-center">
              <button
                onClick={() => { setOpen(false); navigate('/notifications') }}
                className="text-sm font-semibold text-primary hover:underline bg-transparent border-none cursor-pointer"
              >
                查看全部通知
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
