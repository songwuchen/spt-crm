import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { serviceTicketApi } from '@/api/serviceTicket'
import { usePageTitle } from '@/hooks/usePageTitle'
import { ticketTypeLabels } from '@/constants/labels'

interface TicketDetail {
  id: string; ticket_no: string; title: string; description?: string
  type: string; priority: string; status: string
  customer_name?: string; assigned_to_name?: string
  created_by_name?: string; created_at: string; resolved_at?: string
}

const statusLabels: Record<string, { label: string; color: string }> = {
  open: { label: '待处理', color: 'bg-blue-50 text-blue-700' },
  in_progress: { label: '处理中', color: 'bg-amber-50 text-amber-700' },
  resolved: { label: '已解决', color: 'bg-emerald-50 text-emerald-700' },
  closed: { label: '已关闭', color: 'bg-slate-100 text-slate-600' },
}

const priorityLabels: Record<string, { label: string; color: string }> = {
  low: { label: '低', color: 'text-slate-500' },
  normal: { label: '中', color: 'text-blue-600' },
  high: { label: '高', color: 'text-amber-600' },
  urgent: { label: '紧急', color: 'text-red-600' },
}

export default function MobileServiceTicketDetail() {
  usePageTitle('工单详情')
  const { id } = useParams()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState<TicketDetail | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    serviceTicketApi.get(id)
      .then((r: any) => setTicket(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="text-center py-12 text-slate-400">加载中...</div>
  if (!ticket) return <div className="text-center py-12 text-slate-400 text-sm">工单不存在</div>

  const sc = statusLabels[ticket.status] || statusLabels.open
  const pc = priorityLabels[ticket.priority] || priorityLabels.normal

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <h1 className="text-lg font-extrabold text-slate-900">{ticket.ticket_no}</h1>
        <span className={`px-2 py-0.5 rounded text-[12px] font-bold ${sc.color}`}>{sc.label}</span>
      </div>

      {/* Header card */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 mb-4">
        <h2 className="text-base font-bold text-slate-900 mb-2">{ticket.title}</h2>
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <span className={`font-bold ${pc.color}`}>优先级: {pc.label}</span>
          <span>类型: {ticketTypeLabels[ticket.type] || ticket.type}</span>
        </div>
      </div>

      {/* Info */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 mb-4 space-y-3">
        {ticket.description && (
          <div>
            <div className="text-[12px] font-bold text-slate-400 mb-1">问题描述</div>
            <div className="text-sm text-slate-700 whitespace-pre-wrap">{ticket.description}</div>
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          {ticket.customer_name && (
            <div>
              <div className="text-[12px] font-bold text-slate-400">客户</div>
              <div className="text-sm text-slate-800">{ticket.customer_name}</div>
            </div>
          )}
          {ticket.assigned_to_name && (
            <div>
              <div className="text-[12px] font-bold text-slate-400">负责人</div>
              <div className="text-sm text-slate-800">{ticket.assigned_to_name}</div>
            </div>
          )}
          <div>
            <div className="text-[12px] font-bold text-slate-400">创建人</div>
            <div className="text-sm text-slate-800">{ticket.created_by_name || '-'}</div>
          </div>
          <div>
            <div className="text-[12px] font-bold text-slate-400">创建时间</div>
            <div className="text-sm text-slate-800">{ticket.created_at?.slice(0, 16)}</div>
          </div>
          {ticket.resolved_at && (
            <div>
              <div className="text-[12px] font-bold text-slate-400">解决时间</div>
              <div className="text-sm text-slate-800">{ticket.resolved_at.slice(0, 16)}</div>
            </div>
          )}
        </div>
      </div>

      {/* Status timeline */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
        <div className="text-[12px] font-bold text-slate-400 mb-3">状态流转</div>
        <div className="flex items-center gap-1">
          {['open', 'in_progress', 'resolved', 'closed'].map((step, i) => {
            const steps = ['open', 'in_progress', 'resolved', 'closed']
            const currentIdx = steps.indexOf(ticket.status)
            const isActive = i <= currentIdx
            const sl = statusLabels[step]
            return (
              <div key={step} className="flex items-center gap-1 flex-1">
                <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold ${
                  isActive ? 'bg-primary text-white' : 'bg-slate-100 text-slate-400'
                }`}>{i + 1}</div>
                <span className={`text-[9px] ${isActive ? 'text-slate-700 font-medium' : 'text-slate-400'}`}>{sl.label}</span>
                {i < 3 && <div className={`flex-1 h-0.5 ${isActive && i < currentIdx ? 'bg-primary' : 'bg-slate-100'}`} />}
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
