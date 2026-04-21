import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'

interface CalendarEvent {
  id: string; date: string; type: string; title: string; color: string
}

const typeLabels: Record<string, { label: string; icon: string; color: string }> = {
  follow_up: { label: '跟进', icon: 'event', color: '#3b82f6' },
  payment_due: { label: '回款', icon: 'payments', color: '#f59e0b' },
  contract_expiry: { label: '合同到期', icon: 'description', color: '#ef4444' },
  milestone: { label: '里程碑', icon: 'flag', color: '#8b5cf6' },
}

export default function MobileCalendar() {
  usePageTitle('日程')
  const navigate = useNavigate()
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [currentMonth, setCurrentMonth] = useState(dayjs())
  const [selectedDate, setSelectedDate] = useState<string | null>(null)

  useEffect(() => {
    dashboardApi.calendarEvents({ year: currentMonth.year(), month: currentMonth.month() + 1 })
      .then((r: any) => setEvents(r.data || []))
      .catch(() => {})
  }, [currentMonth.year(), currentMonth.month()])

  const daysInMonth = currentMonth.daysInMonth()
  const firstDayOfWeek = currentMonth.startOf('month').day()
  const today = dayjs().format('YYYY-MM-DD')

  const eventsByDate = events.reduce<Record<string, CalendarEvent[]>>((acc, e) => {
    const d = e.date?.slice(0, 10)
    if (d) { acc[d] = acc[d] || []; acc[d].push(e) }
    return acc
  }, {})

  const selectedEvents = selectedDate ? eventsByDate[selectedDate] || [] : []

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <h1 className="text-lg font-extrabold text-slate-900">日程</h1>
      </div>

      {/* Month nav */}
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => setCurrentMonth(m => m.subtract(1, 'month'))} className="text-slate-500 active:bg-slate-100 rounded-lg p-1">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>chevron_left</span>
        </button>
        <span className="text-sm font-bold text-slate-900">{currentMonth.format('YYYY年M月')}</span>
        <button onClick={() => setCurrentMonth(m => m.add(1, 'month'))} className="text-slate-500 active:bg-slate-100 rounded-lg p-1">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>chevron_right</span>
        </button>
      </div>

      {/* Calendar grid */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 mb-4">
        <div className="grid grid-cols-7 text-center mb-2">
          {['日', '一', '二', '三', '四', '五', '六'].map(d => (
            <div key={d} className="text-[10px] font-bold text-slate-400 py-1">{d}</div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {Array.from({ length: firstDayOfWeek }).map((_, i) => <div key={`e-${i}`} />)}
          {Array.from({ length: daysInMonth }).map((_, i) => {
            const day = i + 1
            const dateStr = currentMonth.date(day).format('YYYY-MM-DD')
            const dayEvents = eventsByDate[dateStr] || []
            const isToday = dateStr === today
            const isSelected = dateStr === selectedDate
            return (
              <button key={day} onClick={() => setSelectedDate(isSelected ? null : dateStr)}
                className={`relative h-10 rounded-lg text-sm font-medium transition-colors ${
                  isSelected ? 'bg-primary text-white' : isToday ? 'bg-primary/10 text-primary font-bold' : 'text-slate-700 active:bg-slate-50'
                }`}>
                {day}
                {dayEvents.length > 0 && (
                  <div className="absolute bottom-0.5 left-1/2 -translate-x-1/2 flex gap-0.5">
                    {dayEvents.slice(0, 3).map((e, j) => (
                      <div key={j} className="w-1 h-1 rounded-full" style={{ background: typeLabels[e.type]?.color || '#94a3b8' }} />
                    ))}
                  </div>
                )}
              </button>
            )
          })}
        </div>
      </div>

      {/* Type legend */}
      <div className="flex gap-3 mb-4 flex-wrap">
        {Object.entries(typeLabels).map(([key, tl]) => {
          const cnt = events.filter(e => e.type === key).length
          if (cnt === 0) return null
          return (
            <div key={key} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full" style={{ background: tl.color }} />
              <span className="text-[10px] text-slate-500">{tl.label} {cnt}</span>
            </div>
          )
        })}
      </div>

      {/* Selected date events */}
      {selectedDate && (
        <div>
          <div className="text-sm font-bold text-slate-500 mb-2">{dayjs(selectedDate).format('M月D日')} 的日程</div>
          {selectedEvents.length === 0 ? (
            <div className="text-center py-6 text-slate-400 text-sm">当日无日程</div>
          ) : (
            <div className="space-y-2">
              {selectedEvents.map(e => {
                const tl = typeLabels[e.type] || { label: e.type, icon: 'event', color: '#94a3b8' }
                return (
                  <div key={e.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: tl.color + '20' }}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16, color: tl.color }}>{tl.icon}</span>
                    </div>
                    <div className="flex-1">
                      <div className="text-sm font-bold text-slate-800">{e.title}</div>
                      <div className="text-[10px] text-slate-400">{tl.label}</div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {!selectedDate && events.length === 0 && (
        <div className="text-center py-8 text-slate-400 text-sm">本月无日程安排</div>
      )}
    </div>
  )
}
