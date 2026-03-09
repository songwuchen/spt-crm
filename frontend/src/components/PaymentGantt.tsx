import { useMemo } from 'react'
import { Tag, Tooltip } from 'antd'
import type { PaymentPlanItem, PaymentRecordItem } from '@/api/types'
import dayjs from 'dayjs'

interface Props {
  plans: PaymentPlanItem[]
  records: PaymentRecordItem[]
}

const STATUS_COLORS: Record<string, string> = {
  pending: '#3b82f6', paid: '#10b981', overdue: '#ef4444',
}
const STATUS_LABELS: Record<string, string> = {
  pending: '待回款', paid: '已回款', overdue: '已逾期',
}

export default function PaymentGantt({ plans, records }: Props) {
  const { items, minDate, totalDays, monthTicks, todayPct, recordMap } = useMemo(() => {
    const today = dayjs()
    const datedPlans = plans
      .filter((p) => p.due_date)
      .sort((a, b) => (a.due_date || '').localeCompare(b.due_date || ''))

    if (datedPlans.length === 0) return { items: [], minDate: today, totalDays: 1, monthTicks: [] as { label: string; pct: number }[], todayPct: 0, recordMap: new Map<string, PaymentRecordItem[]>() }

    const allDates = datedPlans.map((p) => dayjs(p.due_date!))
    const recDates = records.filter((r) => r.received_date).map((r) => dayjs(r.received_date!))
    const allPoints = [...allDates, ...recDates, today]

    const min = allPoints.reduce((a, b) => (a.isBefore(b) ? a : b)).subtract(7, 'day')
    const max = allPoints.reduce((a, b) => (a.isAfter(b) ? a : b)).add(14, 'day')
    const days = max.diff(min, 'day') || 1

    const ticks: { label: string; pct: number }[] = []
    let tick = min.startOf('month').add(1, 'month')
    while (tick.isBefore(max)) {
      const pct = (tick.diff(min, 'day') / days) * 100
      if (pct > 0 && pct < 100) ticks.push({ label: tick.format('M月'), pct })
      tick = tick.add(1, 'month')
    }

    const rMap = new Map<string, PaymentRecordItem[]>()
    records.forEach((r) => {
      if (r.matched_plan_id) {
        const list = rMap.get(r.matched_plan_id) || []
        list.push(r)
        rMap.set(r.matched_plan_id, list)
      }
    })

    const todayOff = Math.max(0, Math.min(100, (today.diff(min, 'day') / days) * 100))

    return { items: datedPlans, minDate: min, totalDays: days, monthTicks: ticks, todayPct: todayOff, recordMap: rMap }
  }, [plans, records])

  if (items.length === 0) {
    return <div className="text-center py-6 text-slate-400 text-sm">暂无带日期的回款计划</div>
  }

  return (
    <div className="space-y-0">
      {/* Timeline header */}
      <div className="relative h-6 mb-1 ml-[160px]">
        {monthTicks.map((t, i) => (
          <div key={i} className="absolute text-[10px] text-slate-400 font-bold" style={{ left: t.pct + '%', transform: 'translateX(-50%)' }}>
            {t.label}
          </div>
        ))}
      </div>

      {/* Rows */}
      {items.map((p) => {
        const duePct = (dayjs(p.due_date!).diff(minDate, 'day') / totalDays) * 100
        const isOverdue = p.status === 'overdue' || (p.due_date && dayjs(p.due_date).isBefore(dayjs()) && p.status !== 'paid')
        const matchedRecords = recordMap.get(p.id) || []

        return (
          <div key={p.id} className="flex items-center h-10 group hover:bg-slate-50 rounded">
            <div className="w-[160px] flex-shrink-0 pr-3 text-right">
              <div className="text-xs font-semibold text-slate-700 truncate">{p.plan_no}</div>
              <div className="text-[10px] text-slate-400">¥{(p.amount || 0).toLocaleString()}</div>
            </div>

            <div className="flex-1 relative h-full">
              {monthTicks.map((t, i) => (
                <div key={i} className="absolute top-0 bottom-0 border-l border-slate-100" style={{ left: t.pct + '%' }} />
              ))}
              <div className="absolute top-0 bottom-0 border-l-2 border-blue-400 border-dashed z-10" style={{ left: todayPct + '%' }} />

              <Tooltip title={'到期: ' + p.due_date + ' · ¥' + (p.amount || 0).toLocaleString() + ' · ' + (STATUS_LABELS[p.status] || p.status)}>
                <div
                  className="absolute top-1/2 w-4 h-4 rotate-45 border-2 z-20"
                  style={{
                    left: duePct + '%',
                    transform: 'translateX(-50%) translateY(-50%) rotate(45deg)',
                    borderColor: STATUS_COLORS[p.status] || '#94a3b8',
                    backgroundColor: p.status === 'paid' ? STATUS_COLORS.paid : isOverdue ? '#fecaca' : 'white',
                  }}
                />
              </Tooltip>

              {matchedRecords.map((r) => {
                if (!r.received_date) return null
                const recPct = (dayjs(r.received_date).diff(minDate, 'day') / totalDays) * 100
                return (
                  <Tooltip key={r.id} title={'到账: ' + r.received_date + ' · ¥' + (r.amount || 0).toLocaleString()}>
                    <div
                      className="absolute top-1/2 w-3 h-3 rounded-full border-2 z-20"
                      style={{
                        left: recPct + '%',
                        transform: 'translateX(-50%) translateY(-50%)',
                        borderColor: '#10b981',
                        backgroundColor: '#10b981',
                      }}
                    />
                  </Tooltip>
                )
              })}

              {isOverdue && p.status !== 'paid' && (
                <div
                  className="absolute top-1/2 -translate-y-1/2 h-1.5 rounded-full z-10"
                  style={{
                    left: duePct + '%',
                    width: Math.max(0, todayPct - duePct) + '%',
                    backgroundColor: '#fca5a5',
                  }}
                />
              )}
            </div>

            <div className="w-[60px] flex-shrink-0 pl-2">
              <Tag color={p.status === 'paid' ? 'success' : isOverdue ? 'error' : 'default'} className="text-[10px] m-0">
                {STATUS_LABELS[p.status] || p.status}
              </Tag>
            </div>
          </div>
        )
      })}

      <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-100 ml-[160px]">
        <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
          <div className="w-3 h-3 rotate-45 border-2 border-blue-500 bg-white" />
          <span>到期日</span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
          <div className="w-3 h-3 rounded-full bg-emerald-500" />
          <span>实际到账</span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
          <div className="w-6 h-1.5 rounded-full bg-red-300" />
          <span>逾期</span>
        </div>
        <div className="flex items-center gap-1.5 text-[10px] text-slate-500">
          <div className="w-4 h-0 border-t-2 border-blue-400 border-dashed" />
          <span>今天</span>
        </div>
      </div>
    </div>
  )
}
