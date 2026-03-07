import { useState, useEffect } from 'react'
import { Calendar, Badge, Select, Tag } from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'

interface CalendarEvent {
  id: string
  date: string
  type: string
  title: string
  color: string
}

const typeLabels: Record<string, { label: string; icon: string }> = {
  follow_up: { label: '跟进计划', icon: 'event' },
  payment_due: { label: '回款到期', icon: 'payments' },
  contract_expiry: { label: '合同到期', icon: 'description' },
  milestone: { label: '里程碑', icon: 'flag' },
}

const typeFilters = [
  { value: '', label: '全部类型' },
  { value: 'follow_up', label: '跟进计划' },
  { value: 'payment_due', label: '回款到期' },
  { value: 'contract_expiry', label: '合同到期' },
  { value: 'milestone', label: '里程碑' },
]

export default function CalendarPage() {
  usePageTitle('日程日历')
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [currentDate, setCurrentDate] = useState(dayjs())
  const [typeFilter, setTypeFilter] = useState('')

  const fetchEvents = (d: Dayjs) => {
    dashboardApi.calendarEvents({ year: d.year(), month: d.month() + 1 })
      .then((r: any) => setEvents(r.data || []))
      .catch(() => {})
  }

  useEffect(() => { fetchEvents(currentDate) }, [currentDate.year(), currentDate.month()])

  const filteredEvents = typeFilter ? events.filter((e) => e.type === typeFilter) : events

  const eventsByDate: Record<string, CalendarEvent[]> = {}
  filteredEvents.forEach((e) => {
    if (!eventsByDate[e.date]) eventsByDate[e.date] = []
    eventsByDate[e.date].push(e)
  })

  const dateCellRender = (value: Dayjs) => {
    const dateStr = value.format('YYYY-MM-DD')
    const dayEvents = eventsByDate[dateStr]
    if (!dayEvents || dayEvents.length === 0) return null
    return (
      <ul className="list-none p-0 m-0">
        {dayEvents.slice(0, 3).map((e) => (
          <li key={e.id} className="mb-0.5">
            <Badge color={e.color} text={
              <span className="text-[10px] text-slate-600 truncate block max-w-full">{e.title}</span>
            } />
          </li>
        ))}
        {dayEvents.length > 3 && (
          <li className="text-[10px] text-slate-400">+{dayEvents.length - 3} 更多</li>
        )}
      </ul>
    )
  }

  // Summary stats
  const totalByType: Record<string, number> = {}
  events.forEach((e) => {
    totalByType[e.type] = (totalByType[e.type] || 0) + 1
  })

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">日程日历</h1>
          <p className="text-sm text-slate-500 mt-0.5">跟进计划、回款到期、合同到期、交付里程碑</p>
        </div>
        <Select value={typeFilter} onChange={setTypeFilter} options={typeFilters} style={{ width: 140 }} />
      </div>

      {/* Quick Stats */}
      <div className="flex gap-3 flex-wrap mb-4">
        {Object.entries(totalByType).map(([type, count]) => {
          const tl = typeLabels[type]
          return tl ? (
            <div key={type} className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg border border-slate-200 shadow-sm">
              <span className="material-symbols-outlined text-base text-slate-400">{tl.icon}</span>
              <span className="text-xs font-bold text-slate-700">{tl.label}</span>
              <span className="text-xs font-black text-primary">{count}</span>
            </div>
          ) : null
        })}
        {Object.keys(totalByType).length === 0 && (
          <span className="text-sm text-slate-400">本月暂无日程</span>
        )}
      </div>

      {/* Calendar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <Calendar
          value={currentDate}
          onPanelChange={(d) => setCurrentDate(d)}
          cellRender={(current, info) => {
            if (info.type === 'date') return dateCellRender(current)
            return null
          }}
        />
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4 flex-wrap">
        <div className="flex items-center gap-1.5"><Badge color="#3b82f6" /><span className="text-xs text-slate-500">跟进计划</span></div>
        <div className="flex items-center gap-1.5"><Badge color="#f59e0b" /><span className="text-xs text-slate-500">回款到期</span></div>
        <div className="flex items-center gap-1.5"><Badge color="#ef4444" /><span className="text-xs text-slate-500">合同到期</span></div>
        <div className="flex items-center gap-1.5"><Badge color="#8b5cf6" /><span className="text-xs text-slate-500">里程碑</span></div>
      </div>
    </div>
  )
}
