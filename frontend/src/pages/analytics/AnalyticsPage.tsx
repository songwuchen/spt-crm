import { useState, useEffect, useCallback } from 'react'
import { Spin, DatePicker, Space, Button, message } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import dayjs, { type Dayjs } from 'dayjs'
import { Column, Pie, Funnel, Bar, Line } from '@ant-design/charts'
import { downloadFile } from '@/utils/download'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'

interface FunnelItem {
  stage: string
  label: string
  count: number
  amount: number
}

interface WinLoss {
  won_count: number
  lost_count: number
  won_amount: number
  lost_amount: number
  win_rate: number
}

interface TopCustomer {
  id: string
  name: string
  project_count: number
  total_amount: number
}

interface PaymentOverview {
  total_planned: number
  total_received: number
  overdue_count: number
  overdue_amount: number
  upcoming_30d_amount: number
  collection_rate: number
}

interface MilestoneOverview {
  pending: number
  in_progress: number
  completed: number
  delayed: number
  total: number
  completion_rate: number
}

interface MonthlyRevenue {
  year: number
  month: number
  label: string
  amount: number
}

interface LeaderboardItem {
  owner_id: string
  owner_name: string
  won_count: number
  won_amount: number
  active_count: number
  pipeline_amount: number
}

interface TrendItem {
  label: string
  new: number
  won: number
  lost: number
  won_amount: number
}

interface CollectionItem {
  label: string
  receivable: number
  received: number
  overdue: number
}

export default function AnalyticsPage() {
  usePageTitle('数据分析')
  const navigate = useNavigate()
  const [funnel, setFunnel] = useState<FunnelItem[]>([])
  const [winLoss, setWinLoss] = useState<WinLoss | null>(null)
  const [topCustomers, setTopCustomers] = useState<TopCustomer[]>([])
  const [payment, setPayment] = useState<PaymentOverview | null>(null)
  const [milestones, setMilestones] = useState<MilestoneOverview | null>(null)
  const [monthlyRevenue, setMonthlyRevenue] = useState<MonthlyRevenue[]>([])
  const [leaderboard, setLeaderboard] = useState<LeaderboardItem[]>([])
  const [trendData, setTrendData] = useState<TrendItem[]>([])
  const [collectionData, setCollectionData] = useState<CollectionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [dateRange, setDateRange] = useState<[Dayjs, Dayjs] | null>(null)
  const [periodLabel, setPeriodLabel] = useState('全部')

  const load = useCallback(async () => {
    setLoading(true)
    const params: Record<string, string> = {}
    if (dateRange) {
      params.start_date = dateRange[0].format('YYYY-MM-DD')
      params.end_date = dateRange[1].format('YYYY-MM-DD')
    }
    try {
      const [fRes, wRes, tRes, pRes, mRes, rRes, lRes, trRes, cRes] = await Promise.all([
        dashboardApi.funnel(params),
        dashboardApi.winLoss(params),
        dashboardApi.topCustomers(params),
        dashboardApi.paymentOverview(params),
        dashboardApi.milestoneOverview(params),
        dashboardApi.monthlyRevenue(params),
        dashboardApi.leaderboard(params),
        dashboardApi.trend(params),
        dashboardApi.collection(params),
      ]) as { data: unknown }[]
      setFunnel((fRes.data as FunnelItem[]) || [])
      setWinLoss((wRes.data as WinLoss) || null)
      setTopCustomers((tRes.data as TopCustomer[]) || [])
      setPayment((pRes.data as PaymentOverview) || null)
      setMilestones((mRes.data as MilestoneOverview) || null)
      setMonthlyRevenue((rRes.data as MonthlyRevenue[]) || [])
      setLeaderboard((lRes.data as LeaderboardItem[]) || [])
      setTrendData((trRes.data as TrendItem[]) || [])
      setCollectionData((cRes.data as CollectionItem[]) || [])
    } finally {
      setLoading(false)
    }
  }, [dateRange])

  useEffect(() => { load() }, [load])

  const setQuickRange = (label: string, start: Dayjs, end: Dayjs) => {
    setPeriodLabel(label)
    setDateRange([start, end])
  }

  const handleExportExcel = () => {
    downloadFile('/api/v1/projects/export/excel', `商机报表_${dayjs().format('YYYYMMDD')}.xlsx`)
  }

  if (loading) return <DetailSkeleton />

  // --- Chart data transforms ---
  const funnelData = funnel.map((f) => ({
    stage: `${f.stage} ${f.label}`,
    count: f.count,
  }))

  const winLossPieData = winLoss ? [
    { type: '赢单', value: winLoss.won_count },
    { type: '丢单', value: winLoss.lost_count },
  ] : []

  const monthlyData = monthlyRevenue.map((m) => ({
    month: m.label.slice(5) + '月',
    amount: Math.round(m.amount / 10000),
  }))

  const milestonesPieData = milestones ? [
    { type: '已完成', value: milestones.completed },
    { type: '进行中', value: milestones.in_progress },
    { type: '待开始', value: milestones.pending },
    { type: '延期', value: milestones.delayed },
  ].filter((d) => d.value > 0) : []

  const topCustomerBarData = topCustomers.slice(0, 8).map((c) => ({
    name: c.name.length > 8 ? c.name.slice(0, 8) + '...' : c.name,
    amount: Math.round(c.total_amount / 10000),
    fullName: c.name,
    id: c.id,
  }))

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">销售分析</h1>
          <p className="text-sm text-slate-500 mt-1">销售漏斗、赢单分析、回款跟踪、交付里程碑</p>
        </div>
        <Space>
          <Button icon={<DownloadOutlined />} size="small" onClick={handleExportExcel}>导出报表</Button>
          <Space.Compact>
            {[
              { label: '本月', fn: () => setQuickRange('本月', dayjs().startOf('month'), dayjs()) },
              { label: '本季', fn: () => {
                const qMonth = Math.floor(dayjs().month() / 3) * 3
                setQuickRange('本季', dayjs().month(qMonth).startOf('month'), dayjs())
              } },
              { label: '本年', fn: () => setQuickRange('本年', dayjs().startOf('year'), dayjs()) },
              { label: '全部', fn: () => { setPeriodLabel('全部'); setDateRange(null) } },
            ].map((b) => (
              <Button key={b.label} type={periodLabel === b.label ? 'primary' : 'default'} size="small" onClick={b.fn}>{b.label}</Button>
            ))}
          </Space.Compact>
          <DatePicker.RangePicker size="small" value={dateRange} onChange={(v) => {
            if (v && v[0] && v[1]) { setDateRange([v[0], v[1]]); setPeriodLabel('') }
            else { setDateRange(null); setPeriodLabel('全部') }
          }} />
        </Space>
      </div>

      {/* Payment + Milestone KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {payment && (
          <>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <span className="material-symbols-outlined" style={{ fontSize: 20 }}>payments</span>
                </div>
                <div>
                  <div className="text-xs text-slate-400 font-bold">已回款</div>
                  <div className="text-xl font-black text-slate-900">¥{(payment.total_received / 10000).toFixed(0)}万</div>
                  <div className="text-[10px] text-emerald-600 font-bold">回款率 {payment.collection_rate}%</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-red-50 text-red-600 flex items-center justify-center">
                  <span className="material-symbols-outlined" style={{ fontSize: 20 }}>warning</span>
                </div>
                <div>
                  <div className="text-xs text-slate-400 font-bold">逾期回款</div>
                  <div className="text-xl font-black text-red-600">¥{(payment.overdue_amount / 10000).toFixed(0)}万</div>
                  <div className="text-[10px] text-red-500 font-bold">{payment.overdue_count} 笔逾期</div>
                </div>
              </div>
            </div>
          </>
        )}
        {milestones && (
          <>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <span className="material-symbols-outlined" style={{ fontSize: 20 }}>flag</span>
                </div>
                <div>
                  <div className="text-xs text-slate-400 font-bold">里程碑完成</div>
                  <div className="text-xl font-black text-slate-900">{milestones.completed}/{milestones.total}</div>
                  <div className="text-[10px] text-blue-600 font-bold">完成率 {milestones.completion_rate}%</div>
                </div>
              </div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                  <span className="material-symbols-outlined" style={{ fontSize: 20 }}>schedule</span>
                </div>
                <div>
                  <div className="text-xs text-slate-400 font-bold">延期里程碑</div>
                  <div className="text-xl font-black text-amber-600">{milestones.delayed}</div>
                  <div className="text-[10px] text-slate-400 font-bold">进行中 {milestones.in_progress}</div>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Sales Funnel Chart */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">filter_alt</span>
            销售漏斗
          </h3>
          {funnelData.length > 0 ? (
            <Funnel
              data={funnelData}
              xField="stage"
              yField="count"
              legend={false}
              label={{ text: (d: { stage: string; count: number }) => `${d.stage}: ${d.count}`, position: 'inside', style: { fontSize: 12, fontWeight: 'bold', fill: '#fff' } }}
              style={{ stroke: '#fff', lineWidth: 1 }}
              height={240}
            />
          ) : (
            <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>
          )}
          <div className="mt-3 pt-3 border-t border-slate-100 flex justify-between text-xs text-slate-400">
            <span>总商机: {funnel.reduce((a, b) => a + b.count, 0)}</span>
            <span>总金额: ¥{(funnel.reduce((a, b) => a + b.amount, 0) / 10000).toFixed(0)}万</span>
          </div>
        </div>

        {/* Win/Loss Pie */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-emerald-500">analytics</span>
            赢单/丢单分析
          </h3>
          {winLoss && (winLoss.won_count + winLoss.lost_count > 0) ? (
            <div className="flex items-center gap-6">
              <div style={{ width: 200, height: 200 }}>
                <Pie
                  data={winLossPieData}
                  angleField="value"
                  colorField="type"
                  innerRadius={0.6}
                  height={200}
                  width={200}
                  scale={{ color: { range: ['#10b981', '#ef4444'] } }}
                  legend={false}
                  label={{ text: 'type', position: 'outside', style: { fontSize: 12, fontWeight: 'bold' } }}
                  annotations={[
                    { type: 'text', style: { text: `${winLoss.win_rate}%`, x: '50%', y: '46%', textAlign: 'center', fontSize: 24, fontWeight: 'bold', fill: '#0f172a' } },
                    { type: 'text', style: { text: '赢单率', x: '50%', y: '58%', textAlign: 'center', fontSize: 11, fill: '#94a3b8' } },
                  ]}
                />
              </div>
              <div className="flex-1 space-y-4">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-3 h-3 rounded-full bg-emerald-500" />
                    <span className="text-sm font-bold text-slate-800">赢单</span>
                  </div>
                  <div className="text-2xl font-black text-emerald-600">{winLoss.won_count}</div>
                  <div className="text-xs text-slate-400">¥{(winLoss.won_amount / 10000).toFixed(0)}万</div>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-3 h-3 rounded-full bg-red-500" />
                    <span className="text-sm font-bold text-slate-800">丢单</span>
                  </div>
                  <div className="text-2xl font-black text-red-500">{winLoss.lost_count}</div>
                  <div className="text-xs text-slate-400">¥{(winLoss.lost_amount / 10000).toFixed(0)}万</div>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>
          )}
        </div>
      </div>

      {/* Monthly Revenue Column + Milestone Pie */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-primary">trending_up</span>
            月度回款趋势 (万元)
          </h3>
          {monthlyData.length > 0 ? (
            <Column
              data={monthlyData}
              xField="month"
              yField="amount"
              height={220}
              colorField="month"
              scale={{ color: { range: ['#6366f1'] } }}
              legend={false}
              label={{ text: (d: { amount: number }) => d.amount > 0 ? `${d.amount}` : '', position: 'inside', style: { fontSize: 11, fontWeight: 'bold', fill: '#fff' } }}
              style={{ radiusTopLeft: 4, radiusTopRight: 4 }}
              axis={{ y: { title: '万元' }, x: { title: false } }}
            />
          ) : (
            <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>
          )}
        </div>

        {/* Milestone Pie */}
        {milestones && milestones.total > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-indigo-500">pie_chart</span>
              交付里程碑分布
            </h3>
            <div className="flex items-center gap-4">
              <div style={{ width: 200, height: 200 }}>
                <Pie
                  data={milestonesPieData}
                  angleField="value"
                  colorField="type"
                  innerRadius={0.55}
                  height={200}
                  width={200}
                  scale={{ color: { range: ['#10b981', '#3b82f6', '#cbd5e1', '#ef4444'] } }}
                  legend={false}
                  label={{ text: (d: { type: string; value: number }) => `${d.type} ${d.value}`, position: 'outside', style: { fontSize: 11 } }}
                  annotations={[
                    { type: 'text', style: { text: `${milestones.completion_rate}%`, x: '50%', y: '46%', textAlign: 'center', fontSize: 22, fontWeight: 'bold', fill: '#0f172a' } },
                    { type: 'text', style: { text: '完成率', x: '50%', y: '58%', textAlign: 'center', fontSize: 11, fill: '#94a3b8' } },
                  ]}
                />
              </div>
              <div className="flex-1 space-y-3">
                {[
                  { label: '已完成', value: milestones.completed, color: '#10b981' },
                  { label: '进行中', value: milestones.in_progress, color: '#3b82f6' },
                  { label: '待开始', value: milestones.pending, color: '#cbd5e1' },
                  { label: '延期', value: milestones.delayed, color: '#ef4444' },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-3">
                    <span className="w-3 h-3 rounded-full flex-shrink-0" style={{ background: item.color }} />
                    <span className="text-sm text-slate-700 w-16">{item.label}</span>
                    <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ background: item.color, width: `${milestones.total > 0 ? (item.value / milestones.total) * 100 : 0}%` }} />
                    </div>
                    <span className="text-sm font-bold text-slate-800 w-8 text-right">{item.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Payment + Top Customers */}
      {payment && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-500">account_balance</span>
              回款概览
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">计划总额</span>
                <span className="text-lg font-black text-slate-900">¥{(payment.total_planned / 10000).toFixed(1)}万</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">已回款</span>
                <span className="text-lg font-black text-emerald-600">¥{(payment.total_received / 10000).toFixed(1)}万</span>
              </div>
              <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(payment.collection_rate, 100)}%` }} />
              </div>
              <div className="flex items-center justify-between border-t border-slate-100 pt-3">
                <span className="text-sm text-slate-500">逾期金额</span>
                <span className="text-lg font-black text-red-600">¥{(payment.overdue_amount / 10000).toFixed(1)}万</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-500">30天内到期</span>
                <span className="text-lg font-black text-amber-600">¥{(payment.upcoming_30d_amount / 10000).toFixed(1)}万</span>
              </div>
            </div>
          </div>

          {/* Top Customers Bar Chart */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-amber-500">leaderboard</span>
              客户排行 (管线金额 Top 8, 万元)
            </h3>
            {topCustomerBarData.length === 0 ? (
              <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>
            ) : (
              <Bar
                data={topCustomerBarData}
                xField="name"
                yField="amount"
                height={220}
                colorField="name"
                legend={false}
                label={{ text: (d: { amount: number }) => `¥${d.amount}万`, position: 'right', style: { fontSize: 11, fontWeight: 'bold' } }}
                axis={{ y: { title: false }, x: { title: false } }}
                style={{ radiusTopRight: 4, radiusBottomRight: 4 }}
                onReady={({ chart }) => {
                  chart.on('element:click', (evt: { data?: { data?: { id?: string } } }) => {
                    const id = evt?.data?.data?.id
                    if (id) navigate(`/customers/${id}`)
                  })
                }}
              />
            )}
          </div>
        </div>
      )}

      {/* Trend Analysis + Collection */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Opportunity Trend */}
        {trendData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-indigo-500">show_chart</span>
              商机趋势 (新增/赢单/丢单)
            </h3>
            <Line
              data={trendData.flatMap((d) => [
                { month: d.label.slice(5) + '月', type: '新增', value: d.new },
                { month: d.label.slice(5) + '月', type: '赢单', value: d.won },
                { month: d.label.slice(5) + '月', type: '丢单', value: d.lost },
              ])}
              xField="month"
              yField="value"
              colorField="type"
              height={220}
              scale={{ color: { range: ['#6366f1', '#10b981', '#ef4444'] } }}
              point={{ shapeField: 'circle', sizeField: 3 }}
              legend={{ position: 'top' }}
              axis={{ y: { title: '数量' } }}
            />
          </div>
        )}

        {/* Collection Analysis */}
        {collectionData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-500">account_balance_wallet</span>
              回款分析 (应收/已收/逾期, 万元)
            </h3>
            <Column
              data={collectionData.flatMap((d) => [
                { month: d.label.slice(5) + '月', type: '应收', value: Math.round(d.receivable / 10000) },
                { month: d.label.slice(5) + '月', type: '已收', value: Math.round(d.received / 10000) },
                { month: d.label.slice(5) + '月', type: '逾期', value: Math.round(d.overdue / 10000) },
              ])}
              xField="month"
              yField="value"
              colorField="type"
              height={220}
              group={true}
              scale={{ color: { range: ['#6366f1', '#10b981', '#ef4444'] } }}
              legend={{ position: 'top' }}
              axis={{ y: { title: '万元' } }}
              style={{ radiusTopLeft: 3, radiusTopRight: 3 }}
            />
          </div>
        )}
      </div>

      {/* Sales Leaderboard */}
      {leaderboard.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
          <h3 className="text-sm font-bold text-slate-900 mb-4 flex items-center gap-2">
            <span className="material-symbols-outlined text-amber-500">emoji_events</span>
            销售排行榜 (赢单金额)
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="text-left py-2 px-2 text-xs font-bold text-slate-400 w-10">排名</th>
                  <th className="text-left py-2 px-2 text-xs font-bold text-slate-400">销售</th>
                  <th className="text-right py-2 px-2 text-xs font-bold text-slate-400">赢单数</th>
                  <th className="text-right py-2 px-2 text-xs font-bold text-slate-400">赢单金额</th>
                  <th className="text-right py-2 px-2 text-xs font-bold text-slate-400">跟进中</th>
                  <th className="text-right py-2 px-2 text-xs font-bold text-slate-400">管线金额</th>
                  <th className="py-2 px-2 text-xs font-bold text-slate-400 w-40">赢单占比</th>
                </tr>
              </thead>
              <tbody>
                {leaderboard.map((item, i) => {
                  const maxWon = leaderboard[0].won_amount || 1
                  const pct = Math.max(5, (item.won_amount / maxWon) * 100)
                  return (
                    <tr key={item.owner_id} className="border-b border-slate-50 hover:bg-slate-50/50">
                      <td className="py-2.5 px-2">
                        <span className={`inline-flex w-6 h-6 rounded-full items-center justify-center text-[10px] font-black text-white ${
                          i === 0 ? 'bg-amber-500' : i === 1 ? 'bg-slate-400' : i === 2 ? 'bg-amber-700' : 'bg-slate-300'
                        }`}>{i + 1}</span>
                      </td>
                      <td className="py-2.5 px-2 font-bold text-slate-800">{item.owner_name}</td>
                      <td className="py-2.5 px-2 text-right font-bold text-emerald-600">{item.won_count}</td>
                      <td className="py-2.5 px-2 text-right font-bold text-slate-900">¥{(item.won_amount / 10000).toFixed(0)}万</td>
                      <td className="py-2.5 px-2 text-right text-slate-500">{item.active_count}</td>
                      <td className="py-2.5 px-2 text-right text-slate-500">¥{(item.pipeline_amount / 10000).toFixed(0)}万</td>
                      <td className="py-2.5 px-2">
                        <div className="h-4 bg-slate-100 rounded-full overflow-hidden">
                          <div className="h-full bg-amber-400 rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
