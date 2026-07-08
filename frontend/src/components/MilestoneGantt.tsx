import { useMemo } from 'react'
import { Tag, Tooltip } from 'antd'
import type { DeliveryMilestone } from '@/api/types'
import dayjs from 'dayjs'

interface Props {
  milestones: DeliveryMilestone[]
}

const STATUS_COLORS: Record<string, string> = {
  not_start: '#94a3b8', doing: '#3b82f6', done: '#10b981',
  delayed: '#ef4444', pending: '#94a3b8', in_progress: '#3b82f6', completed: '#10b981',
}

const STATUS_LABELS: Record<string, string> = {
  not_start: '未开始', doing: '进行中', done: '已完成',
  delayed: '已延迟', pending: '待开始', in_progress: '进行中', completed: '已完成',
}

export default function MilestoneGantt({ milestones }: Props) {
  const { items, minDate, maxDate, totalDays } = useMemo(() => {
    const today = dayjs()
    const parsedItems = milestones
      .filter((m) => m.plan_date)
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || (a.plan_date || '').localeCompare(b.plan_date || ''))
      .map((m) => {
        const planStart = dayjs(m.plan_date)
        const actualEnd = m.actual_date ? dayjs(m.actual_date) : null
        const isOverdue = actualEnd ? actualEnd.isAfter(planStart) : today.isAfter(planStart) && m.status !== 'done' && m.status !== 'completed'
        return { ...m, planStart, actualEnd, isOverdue }
      })

    if (parsedItems.length === 0) return { items: [], minDate: today, maxDate: today, totalDays: 1 }

    const allDates = parsedItems.flatMap((m) => {
      const dates = [m.planStart]
      if (m.actualEnd) dates.push(m.actualEnd)
      return dates
    })
    const min = allDates.reduce((a, b) => (a.isBefore(b) ? a : b)).subtract(3, 'day')
    const max = allDates.reduce((a, b) => (a.isAfter(b) ? a : b)).add(7, 'day')
    const days = max.diff(min, 'day') || 1

    return { items: parsedItems, minDate: min, maxDate: max, totalDays: days }
  }, [milestones])

  if (items.length === 0) {
    return <div className="text-center py-6 text-slate-400 text-sm">暂无带日期的里程碑数据</div>
  }

  const todayOffset = dayjs().diff(minDate, 'day')
  const todayPct = Math.max(0, Math.min(100, (todayOffset / totalDays) * 100))

  // Generate month ticks
  const monthTicks: { label: string; pct: number }[] = []
  let tick = minDate.startOf('month').add(1, 'month')
  while (tick.isBefore(maxDate)) {
    const pct = (tick.diff(minDate, 'day') / totalDays) * 100
    if (pct > 0 && pct < 100) {
      monthTicks.push({ label: tick.format('M月'), pct })
    }
    tick = tick.add(1, 'month')
  }

  return (
    <div className="space-y-0">
      {/* Timeline header */}
      <div className="relative h-6 mb-1 ml-[140px]">
        {monthTicks.map((t, i) => (
          <div key={i} className="absolute text-[12px] text-slate-400 font-bold" style={{ left: `${t.pct}%`, transform: 'translateX(-50%)' }}>
            {t.label}
          </div>
        ))}
      </div>

      {/* Rows */}
      {items.map((m) => {
        const planPct = (m.planStart.diff(minDate, 'day') / totalDays) * 100
        const actualPct = m.actualEnd ? (m.actualEnd.diff(minDate, 'day') / totalDays) * 100 : null
        const barWidth = Math.max(1, 2) // single-day milestone point

        return (
          <div key={m.id} className="flex items-center h-9 group hover:bg-slate-50 rounded">
            {/* Label */}
            <div className="w-[140px] flex-shrink-0 pr-3 text-right">
              <Tooltip title={`${m.milestone_code} · ${STATUS_LABELS[m.status] || m.status}`}>
                <span className="text-sm font-semibold text-slate-700 truncate block">{m.name || m.milestone_code}</span>
              </Tooltip>
            </div>

            {/* Bar area */}
            <div className="flex-1 relative h-full">
              {/* Grid lines */}
              {monthTicks.map((t, i) => (
                <div key={i} className="absolute top-0 bottom-0 border-l border-slate-100" style={{ left: `${t.pct}%` }} />
              ))}

              {/* Today line */}
              <div className="absolute top-0 bottom-0 border-l-2 border-blue-400 border-dashed z-10" style={{ left: `${todayPct}%` }} />

              {/* Plan marker (diamond) */}
              <Tooltip title={`计划: ${m.plan_date}`}>
                <div
                  className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rotate-45 border-2 z-20"
                  style={{
                    left: `${planPct}%`,
                    transform: `translateX(-50%) translateY(-50%) rotate(45deg)`,
                    borderColor: STATUS_COLORS[m.status] || '#94a3b8',
                    backgroundColor: m.status === 'done' || m.status === 'completed' ? STATUS_COLORS[m.status] : 'white',
                  }}
                />
              </Tooltip>

              {/* Actual marker (circle) + connecting line */}
              {actualPct != null && (
                <>
                  {/* Connecting bar from plan to actual */}
                  <div
                    className="absolute top-1/2 -translate-y-1/2 h-1.5 rounded-full z-10"
                    style={{
                      left: `${Math.min(planPct, actualPct)}%`,
                      width: `${Math.abs(actualPct - planPct)}%`,
                      backgroundColor: m.isOverdue ? '#fca5a5' : '#86efac',
                    }}
                  />
                  <Tooltip title={`实际: ${m.actual_date}${m.isOverdue ? ' (延期)' : ''}`}>
                    <div
                      className="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full border-2 z-20"
                      style={{
                        left: `${actualPct}%`,
                        transform: 'translateX(-50%) translateY(-50%)',
                        borderColor: m.isOverdue ? '#ef4444' : '#10b981',
                        backgroundColor: m.isOverdue ? '#ef4444' : '#10b981',
                      }}
                    />
                  </Tooltip>
                </>
              )}

              {/* Overdue indicator — no actual but past plan date */}
              {actualPct == null && m.isOverdue && (
                <div
                  className="absolute top-1/2 -translate-y-1/2 h-1.5 rounded-full z-10"
                  style={{
                    left: `${planPct}%`,
                    width: `${todayPct - planPct}%`,
                    backgroundColor: '#fca5a5',
                  }}
                />
              )}
            </div>

            {/* Status tag */}
            <div className="w-[60px] flex-shrink-0 pl-2">
              {m.isOverdue && <Tag color="error" className="text-[12px] m-0">延期</Tag>}
            </div>
          </div>
        )
      })}

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-100 ml-[140px]">
        <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
          <div className="w-3 h-3 rotate-45 border-2 border-slate-400 bg-white" />
          <span>计划日期</span>
        </div>
        <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
          <div className="w-3 h-3 rounded-full bg-emerald-500" />
          <span>实际完成</span>
        </div>
        <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
          <div className="w-3 h-3 rounded-full bg-red-500" />
          <span>延期完成</span>
        </div>
        <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
          <div className="w-4 h-0 border-t-2 border-blue-400 border-dashed" />
          <span>今天</span>
        </div>
      </div>
    </div>
  )
}
