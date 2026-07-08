import { useMemo } from 'react'
import { Tag, Tooltip } from 'antd'
import type { PaymentPlanItem, PaymentRecordItem } from '@/api/types'
import dayjs from 'dayjs'

interface Props {
  plans: PaymentPlanItem[]
  records: PaymentRecordItem[]
}

export default function PaymentChart({ plans, records }: Props) {
  const chartData = useMemo(() => {
    if (plans.length === 0 && records.length === 0) return null

    const planTotal = plans.reduce((sum, p) => sum + (p.amount || 0), 0)
    const receivedTotal = records.reduce((sum, r) => sum + (r.amount || 0), 0)

    // Group plans by month
    const monthMap = new Map<string, { plan: number; received: number; overdue: boolean }>()

    plans.forEach((p) => {
      const month = p.due_date ? dayjs(p.due_date).format('YYYY-MM') : 'unknown'
      const entry = monthMap.get(month) || { plan: 0, received: 0, overdue: false }
      entry.plan += p.amount || 0
      if (p.status === 'overdue' || (p.due_date && dayjs(p.due_date).isBefore(dayjs()) && p.status !== 'paid')) {
        entry.overdue = true
      }
      monthMap.set(month, entry)
    })

    records.forEach((r) => {
      const month = r.received_date ? dayjs(r.received_date).format('YYYY-MM') : 'unknown'
      const entry = monthMap.get(month) || { plan: 0, received: 0, overdue: false }
      entry.received += r.amount || 0
      monthMap.set(month, entry)
    })

    const months = [...monthMap.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, data]) => ({ month, ...data }))

    const maxValue = Math.max(...months.map((m) => Math.max(m.plan, m.received)), 1)

    return { planTotal, receivedTotal, months, maxValue }
  }, [plans, records])

  if (!chartData) {
    return <div className="text-center py-6 text-slate-400 text-sm">暂无回款数据</div>
  }

  const { planTotal, receivedTotal, months, maxValue } = chartData
  const collectionRate = planTotal > 0 ? receivedTotal / planTotal : 0

  return (
    <div>
      {/* Summary cards */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
          <div className="text-[12px] text-blue-400 font-bold uppercase">计划回款</div>
          <div className="text-lg font-black text-blue-700">¥{planTotal.toLocaleString()}</div>
        </div>
        <div className="bg-emerald-50 border border-emerald-100 rounded-lg p-3">
          <div className="text-[12px] text-emerald-400 font-bold uppercase">实际到账</div>
          <div className="text-lg font-black text-emerald-700">¥{receivedTotal.toLocaleString()}</div>
        </div>
        <div className={`border rounded-lg p-3 ${collectionRate >= 0.8 ? 'bg-emerald-50 border-emerald-100' : collectionRate >= 0.5 ? 'bg-amber-50 border-amber-100' : 'bg-red-50 border-red-100'}`}>
          <div className="text-[12px] text-slate-400 font-bold uppercase">回款率</div>
          <div className={`text-lg font-black ${collectionRate >= 0.8 ? 'text-emerald-700' : collectionRate >= 0.5 ? 'text-amber-700' : 'text-red-700'}`}>
            {(collectionRate * 100).toFixed(1)}%
          </div>
        </div>
      </div>

      {/* Bar chart */}
      {months.length > 0 && (
        <div>
          <div className="text-sm font-bold text-slate-500 uppercase mb-3">月度回款对比</div>
          <div className="space-y-3">
            {months.map((m) => {
              const planPct = (m.plan / maxValue) * 100
              const receivedPct = (m.received / maxValue) * 100
              const monthLabel = m.month === 'unknown' ? '未定' : dayjs(m.month + '-01').format('YY/MM')
              return (
                <div key={m.month} className="flex items-center gap-3">
                  {/* Month label */}
                  <div className="w-[50px] flex-shrink-0 text-right">
                    <span className="text-sm font-bold text-slate-600">{monthLabel}</span>
                  </div>

                  {/* Bars */}
                  <div className="flex-1 space-y-1">
                    {/* Plan bar */}
                    <Tooltip title={`计划: ¥${m.plan.toLocaleString()}`}>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                          <div
                            className="h-full bg-blue-400 rounded transition-all"
                            style={{ width: `${planPct}%` }}
                          />
                        </div>
                        <span className="text-[12px] text-slate-400 w-[70px] text-right">¥{m.plan.toLocaleString()}</span>
                      </div>
                    </Tooltip>

                    {/* Received bar */}
                    <Tooltip title={`实收: ¥${m.received.toLocaleString()}`}>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-4 bg-slate-100 rounded overflow-hidden">
                          <div
                            className={`h-full rounded transition-all ${m.received >= m.plan ? 'bg-emerald-400' : 'bg-amber-400'}`}
                            style={{ width: `${receivedPct}%` }}
                          />
                        </div>
                        <span className="text-[12px] text-slate-400 w-[70px] text-right">¥{m.received.toLocaleString()}</span>
                      </div>
                    </Tooltip>
                  </div>

                  {/* Overdue marker */}
                  <div className="w-[40px] flex-shrink-0">
                    {m.overdue && <Tag color="error" className="text-[12px] m-0">逾期</Tag>}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 mt-3 pt-3 border-t border-slate-100">
            <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
              <div className="w-3 h-3 rounded bg-blue-400" />
              <span>计划回款</span>
            </div>
            <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
              <div className="w-3 h-3 rounded bg-emerald-400" />
              <span>实际到账</span>
            </div>
            <div className="flex items-center gap-1.5 text-[12px] text-slate-500">
              <div className="w-3 h-3 rounded bg-amber-400" />
              <span>到账不足</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
