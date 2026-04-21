import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { serviceTicketApi } from '@/api/serviceTicket'
import { usePageTitle } from '@/hooks/usePageTitle'

interface TicketItem {
  id: string; ticket_no: string; description?: string
  type: string; priority: string; status: string
  assigned_to_name?: string; created_at: string
}

const statusLabels: Record<string, { label: string; color: string; bg: string }> = {
  open: { label: '待处理', color: 'text-blue-700', bg: 'bg-blue-50' },
  assigned: { label: '已指派', color: 'text-indigo-700', bg: 'bg-indigo-50' },
  in_progress: { label: '处理中', color: 'text-amber-700', bg: 'bg-amber-50' },
  resolved: { label: '已解决', color: 'text-emerald-700', bg: 'bg-emerald-50' },
  closed: { label: '已关闭', color: 'text-slate-600', bg: 'bg-slate-100' },
}

const priorityIcons: Record<string, { icon: string; color: string }> = {
  low: { icon: 'arrow_downward', color: 'text-slate-400' },
  medium: { icon: 'remove', color: 'text-blue-500' },
  high: { icon: 'arrow_upward', color: 'text-amber-500' },
  critical: { icon: 'priority_high', color: 'text-red-500' },
}

const typeLabels: Record<string, string> = {
  fault: '故障', maintenance: '维护', consultation: '咨询', complaint: '投诉', other: '其他',
}

export default function MobileServiceTickets() {
  usePageTitle('售后工单')
  const navigate = useNavigate()
  const [tickets, setTickets] = useState<TicketItem[]>([])
  const [loading, setLoading] = useState(false)
  const [filterStatus, setFilterStatus] = useState<string>('all')

  const fetchTickets = async (st?: string) => {
    setLoading(true)
    try {
      const r = await serviceTicketApi.list({
        pageNo: 1, pageSize: 50,
        status: st && st !== 'all' ? st : undefined,
      })
      setTickets(r.data?.items || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchTickets() }, [])

  const statuses = ['all', 'open', 'in_progress', 'resolved', 'closed']

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100">
        <h1 className="text-lg font-bold text-slate-900">售后工单</h1>
      </div>

      {/* Status Filter Tabs */}
      <div className="bg-white px-4 py-2 border-b border-slate-100 flex gap-2 overflow-x-auto">
        {statuses.map((s) => (
          <button key={s} onClick={() => { setFilterStatus(s); fetchTickets(s) }}
            className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-bold transition-colors ${
              filterStatus === s ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
            }`}>
            {s === 'all' ? '全部' : statusLabels[s]?.label || s}
          </button>
        ))}
      </div>

      {/* Ticket List */}
      <div className="p-4 space-y-3">
        {loading && <div className="text-center py-8 text-slate-400 text-sm">加载中...</div>}
        {!loading && tickets.length === 0 && (
          <div className="text-center py-8 text-slate-400 text-sm">暂无工单</div>
        )}
        {tickets.map((t) => {
          const st = statusLabels[t.status] || statusLabels.open
          const pri = priorityIcons[t.priority] || priorityIcons.medium
          return (
            <div key={t.id} onClick={() => navigate(`/m/service-tickets/${t.id}`)}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 active:bg-slate-50">
              <div className="flex items-center justify-between mb-2">
                <span className="font-mono text-sm font-bold text-primary">{t.ticket_no}</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${st.color} ${st.bg}`}>
                  {st.label}
                </span>
              </div>
              <p className="text-sm text-slate-700 line-clamp-2 mb-2">{t.description || '-'}</p>
              <div className="flex items-center justify-between text-sm text-slate-400">
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1">
                    <span className={`material-symbols-outlined ${pri.color}`} style={{ fontSize: 14 }}>{pri.icon}</span>
                    {typeLabels[t.type] || t.type}
                  </span>
                  {t.assigned_to_name && <span>{t.assigned_to_name}</span>}
                </div>
                <span>{t.created_at ? new Date(t.created_at).toLocaleDateString('zh-CN') : ''}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
