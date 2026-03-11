import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { notificationApi, type NotificationItem } from '@/api/notification'
import { usePageTitle } from '@/hooks/usePageTitle'

const typeConfig: Record<string, { label: string; icon: string; color: string }> = {
  approval_pending: { label: '审批待处理', icon: 'pending_actions', color: 'text-orange-500' },
  approval_decided: { label: '审批已决定', icon: 'task_alt', color: 'text-green-500' },
  approval_sla_overdue: { label: '审批超时', icon: 'warning', color: 'text-red-500' },
  stage_advance: { label: '阶段推进', icon: 'trending_up', color: 'text-blue-500' },
  stage_change: { label: '阶段变化', icon: 'swap_horiz', color: 'text-blue-500' },
  contract_signed: { label: '合同签署', icon: 'description', color: 'text-green-500' },
  ticket_assigned: { label: '工单分配', icon: 'assignment_ind', color: 'text-cyan-500' },
  payment_overdue: { label: '回款逾期', icon: 'payments', color: 'text-red-500' },
  payment_received: { label: '收到回款', icon: 'paid', color: 'text-green-500' },
  ai_task_complete: { label: 'AI完成', icon: 'smart_toy', color: 'text-purple-500' },
  system: { label: '系统', icon: 'info', color: 'text-slate-400' },
}

export default function MobileNotifications() {
  usePageTitle('通知')
  const navigate = useNavigate()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [loading, setLoading] = useState(false)

  const fetchNotifications = async () => {
    setLoading(true)
    try {
      const r = await notificationApi.list()
      setItems(r.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchNotifications() }, [])

  const handleMarkRead = async (id: string) => {
    await notificationApi.markRead([id])
    setItems(prev => prev.map(i => i.id === id ? { ...i, is_read: true } : i))
  }

  const handleMarkAllRead = async () => {
    const unreadIds = items.filter(i => !i.is_read).map(i => i.id)
    if (unreadIds.length === 0) return
    await notificationApi.markRead(unreadIds)
    setItems(prev => prev.map(i => ({ ...i, is_read: true })))
  }

  const unreadCount = items.filter(i => !i.is_read).length

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900">
          通知 {unreadCount > 0 && <span className="text-xs text-red-500 font-bold ml-1">({unreadCount})</span>}
        </h1>
        {unreadCount > 0 && (
          <button onClick={handleMarkAllRead} className="text-xs text-primary font-bold">全部已读</button>
        )}
      </div>

      <div className="p-4 space-y-2">
        {loading && <div className="text-center py-8 text-slate-400 text-sm">加载中...</div>}
        {!loading && items.length === 0 && (
          <div className="text-center py-8 text-slate-400 text-sm">暂无通知</div>
        )}
        {items.map((n) => {
          const cfg = typeConfig[n.type] || typeConfig.system
          return (
            <div key={n.id} role="button" tabIndex={0} onClick={() => !n.is_read && handleMarkRead(n.id)}
              onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !n.is_read) { e.preventDefault(); handleMarkRead(n.id) } }}
              className={`bg-white rounded-xl border shadow-sm p-4 ${n.is_read ? 'border-slate-100 opacity-60' : 'border-primary/20'}`}>
              <div className="flex items-start gap-3">
                <span className={`material-symbols-outlined ${cfg.color} mt-0.5`} style={{ fontSize: 20 }}>{cfg.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{cfg.label}</span>
                    {!n.is_read && <span className="w-2 h-2 rounded-full bg-primary shrink-0" />}
                  </div>
                  <p className="text-sm text-slate-800 font-medium">{n.title}</p>
                  {n.content && <p className="text-xs text-slate-500 mt-1 line-clamp-2">{n.content}</p>}
                  <span className="text-[10px] text-slate-400 mt-1 block">
                    {n.created_at ? new Date(n.created_at).toLocaleString('zh-CN') : ''}
                  </span>
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
