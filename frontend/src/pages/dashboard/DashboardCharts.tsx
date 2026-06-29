import { useState, useEffect, memo } from 'react'
import { useNavigate } from 'react-router-dom'
import { Select, Button, message } from 'antd'
import { contractApi } from '@/api/contract'
import { Column, Line, Pie, Funnel as FunnelChart } from '@ant-design/charts'
import { dashboardApi } from '@/api/dashboard'

interface TrendItem {
  label: string; new: number; won: number; lost: number; won_amount: number
}
interface CollectionItem {
  label: string; receivable: number; received: number; overdue: number
}
interface RevenueItem {
  label: string; amount: number
}
interface WinLoss {
  won_count: number; lost_count: number; win_rate: number
  won_amount: number; lost_amount: number
}
interface FunnelItem {
  stage: string; label: string; count: number; amount: number
}
interface LeaderItem {
  owner_id: string; owner_name: string
  won_count: number; won_amount: number
  active_count: number; pipeline_amount: number
}

export function TrendChart() {
  const [data, setData] = useState<TrendItem[]>([])
  useEffect(() => {
    dashboardApi.trend({ months: 6 }).then((r: any) => setData(r.data || [])).catch(() => { /* non-critical chart data */ })
  }, [])

  const chartData = data.flatMap((d) => [
    { month: d.label, type: '新建', value: d.new },
    { month: d.label, type: '赢单', value: d.won },
    { month: d.label, type: '丢单', value: d.lost },
  ])

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-blue-500">show_chart</span>
        <h3 className="text-sm font-bold text-slate-900">商机月度趋势</h3>
      </div>
      {data.length > 0 ? (
        <Line
          data={chartData}
          xField="month"
          yField="value"
          colorField="type"
          smooth
          height={240}
          style={{ lineWidth: 2.5 }}
          point={{ shapeField: 'circle', sizeField: 3 }}
          scale={{ color: { range: ['#3b82f6', '#10b981', '#ef4444'] } }}
          axis={{ y: { title: '数量' }, x: { title: false } }}
          legend={{ position: 'top' }}
        />
      ) : (
        <div className="text-center text-slate-400 text-sm py-12">暂无趋势数据</div>
      )}
    </div>
  )
}

export function CollectionChart() {
  const [data, setData] = useState<CollectionItem[]>([])
  useEffect(() => {
    dashboardApi.collection({ months: 6 }).then((r: any) => setData(r.data || [])).catch(() => { /* non-critical chart data */ })
  }, [])

  const chartData = data.flatMap((d) => [
    { month: d.label, type: '应收', value: d.receivable / 10000 },
    { month: d.label, type: '已收', value: d.received / 10000 },
    { month: d.label, type: '逾期', value: d.overdue / 10000 },
  ])

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-emerald-500">bar_chart</span>
        <h3 className="text-sm font-bold text-slate-900">回款月度分析（万元）</h3>
      </div>
      {data.length > 0 ? (
        <Column
          data={chartData}
          xField="month"
          yField="value"
          colorField="type"
          group
          height={240}
          scale={{ color: { range: ['#3b82f6', '#10b981', '#ef4444'] } }}
          axis={{ y: { title: '万元' }, x: { title: false } }}
          legend={{ position: 'top' }}
        />
      ) : (
        <div className="text-center text-slate-400 text-sm py-12">暂无回款数据</div>
      )}
    </div>
  )
}

export function RevenueChart() {
  const [data, setData] = useState<RevenueItem[]>([])
  useEffect(() => {
    dashboardApi.monthlyRevenue({ months: 6 }).then((r: any) => setData(r.data || [])).catch(() => { /* non-critical chart data */ })
  }, [])

  const chartData = data.map((d) => ({ month: d.label, value: d.amount / 10000 }))

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-amber-500">trending_up</span>
        <h3 className="text-sm font-bold text-slate-900">月度回款额（万元）</h3>
      </div>
      {data.length > 0 ? (
        <Column
          data={chartData}
          xField="month"
          yField="value"
          height={240}
          style={{ radiusTopLeft: 4, radiusTopRight: 4, fill: '#3b82f6' }}
          axis={{ y: { title: '万元' }, x: { title: false } }}
          label={{ text: (d: any) => d.value > 0 ? `${d.value.toFixed(1)}` : '', position: 'outside' }}
        />
      ) : (
        <div className="text-center text-slate-400 text-sm py-12">暂无数据</div>
      )}
    </div>
  )
}

export function WinLossChart() {
  const [data, setData] = useState<WinLoss | null>(null)
  useEffect(() => {
    dashboardApi.winLoss().then((r: any) => setData(r.data)).catch(() => { /* non-critical chart data */ })
  }, [])

  if (!data) return null

  const pieData = [
    { type: '赢单', value: data.won_count },
    { type: '丢单', value: data.lost_count },
  ]

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-emerald-500">pie_chart</span>
        <h3 className="text-sm font-bold text-slate-900">赢单/丢单</h3>
        <span className="ml-auto text-sm font-bold text-emerald-600">赢率 {data.win_rate}%</span>
      </div>
      {(data.won_count + data.lost_count) > 0 ? (
        <Pie
          data={pieData}
          angleField="value"
          colorField="type"
          height={220}
          innerRadius={0.6}
          scale={{ color: { range: ['#10b981', '#ef4444'] } }}
          label={{ text: (d: any) => `${d.type}\n${d.value}`, position: 'outside' }}
          legend={{ position: 'bottom' }}
          annotations={[{
            type: 'text',
            style: { text: `${data.win_rate}%`, x: '50%', y: '50%', textAlign: 'center', fontSize: 24, fontWeight: 'bold', fill: '#10b981' },
          }]}
        />
      ) : (
        <div className="text-center text-slate-400 text-sm py-12">暂无数据</div>
      )}
    </div>
  )
}

export const FunnelChartPanel = memo(function FunnelChartPanel({ funnel }: { funnel: FunnelItem[] }) {
  if (funnel.length === 0) return null

  const chartData = funnel.map((f) => ({
    stage: `${f.label} (${f.count})`,
    value: f.count,
    amount: f.amount,
  }))

  return (
    <FunnelChart
      data={chartData}
      xField="stage"
      yField="value"
      height={260}
      label={{ text: (d: any) => `${d.stage}`, position: 'inside' }}
      scale={{ color: { range: ['#3b82f6', '#06b6d4', '#14b8a6', '#10b981', '#22c55e', '#84cc16'] } }}
    />
  )
})

interface ExpiryItem {
  id: string; contract_no: string; project_id?: string; project_name: string; owner_name: string
  amount_total: number; signed_date: string | null; end_date: string | null
  days_left: number; urgency: string
}

export function ContractExpiryPanel() {
  const navigate = useNavigate()
  const [items, setItems] = useState<ExpiryItem[]>([])
  const [days, setDays] = useState(90)
  const [renewingId, setRenewingId] = useState<string | null>(null)

  useEffect(() => {
    dashboardApi.contractExpiry({ days }).then((r: any) => setItems(r.data || [])).catch(() => { /* non-critical chart data */ })
  }, [days])

  const urgencyConfig: Record<string, { label: string; bg: string; text: string }> = {
    expired: { label: '已过期', bg: 'bg-red-100', text: 'text-red-700' },
    critical: { label: '即将到期', bg: 'bg-red-50', text: 'text-red-600' },
    warning: { label: '30天内', bg: 'bg-amber-50', text: 'text-amber-600' },
    normal: { label: '正常', bg: 'bg-blue-50', text: 'text-blue-600' },
  }

  const handleRenew = async (e: React.MouseEvent, contractId: string) => {
    e.stopPropagation()
    setRenewingId(contractId)
    try {
      await contractApi.renew(contractId)
      message.success('已创建续签机会')
      setItems((prev) => prev.filter((i) => i.id !== contractId))
    } catch {
      message.error('创建续签失败')
    } finally {
      setRenewingId(null)
    }
  }

  const expiredCount = items.filter((i) => i.urgency === 'expired' || i.urgency === 'critical').length

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-red-500">event_busy</span>
          <h3 className="text-sm font-bold text-slate-900">合同到期预警</h3>
          {items.length > 0 && (
            <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-sm font-bold">{items.length}</span>
          )}
        </div>
        <Select size="small" value={days} onChange={setDays} style={{ width: 100 }}
          options={[{ value: 30, label: '30天' }, { value: 60, label: '60天' }, { value: 90, label: '90天' }]} />
      </div>
      {/* Summary bar */}
      {items.length > 0 && (
        <div className="flex gap-3 mb-3">
          <div className="flex-1 rounded-lg bg-red-50 border border-red-100 p-2 text-center">
            <div className="text-lg font-black text-red-600">{expiredCount}</div>
            <div className="text-[10px] text-red-500 font-bold">紧急/已过期</div>
          </div>
          <div className="flex-1 rounded-lg bg-amber-50 border border-amber-100 p-2 text-center">
            <div className="text-lg font-black text-amber-600">{items.length - expiredCount}</div>
            <div className="text-[10px] text-amber-500 font-bold">预警中</div>
          </div>
          <div className="flex-1 rounded-lg bg-blue-50 border border-blue-100 p-2 text-center">
            <div className="text-lg font-black text-blue-600">¥{(items.reduce((s, i) => s + (i.amount_total || 0), 0) / 10000).toFixed(0)}万</div>
            <div className="text-[10px] text-blue-500 font-bold">涉及金额</div>
          </div>
        </div>
      )}
      {items.length === 0 ? (
        <div className="text-center text-slate-400 text-sm py-8">暂无即将到期合同</div>
      ) : (
        <div className="space-y-2 max-h-[320px] overflow-y-auto">
          {items.map((item) => {
            const u = urgencyConfig[item.urgency] || urgencyConfig.normal
            return (
              <div key={item.id}
                onClick={() => navigate(`/opportunities/${item.project_id || ''}`)}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer hover:shadow-sm transition-shadow ${u.bg} border-slate-100`}>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-slate-800 truncate">{item.contract_no}</div>
                  <div className="text-[11px] text-slate-500 truncate">{item.project_name} · {item.owner_name || '-'}</div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-sm font-bold text-slate-700">¥{(item.amount_total / 10000).toFixed(1)}万</div>
                  <div className={`text-[10px] font-bold ${u.text}`}>
                    {item.days_left < 0 ? `已过期${Math.abs(item.days_left)}天` : `${item.days_left}天后到期`}
                  </div>
                </div>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${u.bg} ${u.text}`}>{u.label}</span>
                <Button size="small" type="primary"
                  loading={renewingId === item.id}
                  onClick={(e) => handleRenew(e, item.id)}
                  className="shrink-0 text-[11px]">
                  续签
                </Button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export const LeaderboardChart = memo(function LeaderboardChart({ leaderboard }: { leaderboard: LeaderItem[] }) {
  if (leaderboard.length === 0) return null

  // 名称过长时截断，避免 X 轴标签互相重叠（issue #73）
  const short = (s: string) => (s && s.length > 6 ? s.slice(0, 6) + '…' : s || '-')
  const chartData = leaderboard.slice(0, 8).flatMap((item) => [
    { name: short(item.owner_name), type: '赢单金额', value: item.won_amount / 10000 },
    { name: short(item.owner_name), type: '管线金额', value: item.pipeline_amount / 10000 },
  ])

  return (
    <Column
      data={chartData}
      xField="name"
      yField="value"
      colorField="type"
      group
      height={260}
      scale={{ color: { range: ['#10b981', '#3b82f6'] } }}
      axis={{ y: { title: '万元' }, x: { title: false, labelAutoHide: false, labelAutoRotate: true, style: { labelFontSize: 11 } } }}
      legend={{ position: 'top' }}
    />
  )
})
