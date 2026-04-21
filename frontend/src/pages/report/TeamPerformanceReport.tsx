import { useState, useEffect } from 'react'
import { Table, Select, Tag, Progress, Button } from 'antd'
import { DownloadOutlined } from '@ant-design/icons'
import { Column } from '@ant-design/charts'
import { dashboardApi } from '@/api/dashboard'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'

interface LeaderEntry {
  user_id: string; user_name: string
  won_count: number; won_amount: number
  active_count: number; pipeline_amount: number
  win_ratio: number
}

export default function TeamPerformanceReport() {
  usePageTitle('团队绩效报表')
  const [leaders, setLeaders] = useState<LeaderEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [year, setYear] = useState(new Date().getFullYear())
  const [quarter, setQuarter] = useState<number | undefined>()

  useEffect(() => {
    setLoading(true)
    let start = `${year}-01-01`
    let end = `${year}-12-31`
    if (quarter) {
      const sm = (quarter - 1) * 3 + 1
      start = `${year}-${String(sm).padStart(2, '0')}-01`
      const em = sm + 2
      const lastDay = new Date(year, em, 0).getDate()
      end = `${year}-${String(em).padStart(2, '0')}-${lastDay}`
    }
    dashboardApi.leaderboard({ start_date: start, end_date: end })
      .then((r: any) => setLeaders(r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [year, quarter])

  const totalWon = leaders.reduce((s, l) => s + l.won_amount, 0)
  const totalPipeline = leaders.reduce((s, l) => s + l.pipeline_amount, 0)
  const totalDeals = leaders.reduce((s, l) => s + l.won_count, 0)
  const avgWinRate = leaders.length > 0 ? leaders.reduce((s, l) => s + l.win_ratio, 0) / leaders.length : 0

  // Chart data: won amount per person
  const chartData = [...leaders].sort((a, b) => b.won_amount - a.won_amount).slice(0, 15).map(l => ({
    name: l.user_name, amount: +(l.won_amount / 10000).toFixed(1),
  }))

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold text-slate-900">团队绩效报表</h1>
        <p className="text-sm text-slate-500 mt-1">成员赢单量、pipeline、赢单率排行</p>
      </div>

      {/* KPI */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        {[
          { label: '团队赢单额', value: `¥${(totalWon / 10000).toFixed(1)}万`, color: 'text-emerald-600' },
          { label: '管线总额', value: `¥${(totalPipeline / 10000).toFixed(1)}万`, color: 'text-primary' },
          { label: '总赢单数', value: totalDeals, color: 'text-amber-600' },
          { label: '平均赢单率', value: `${(avgWinRate * 100).toFixed(0)}%`, color: 'text-indigo-600' },
        ].map(kpi => (
          <div key={kpi.label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <div className="text-sm font-bold text-slate-400 uppercase">{kpi.label}</div>
            <div className={`text-2xl font-black mt-1 ${kpi.color}`}>{kpi.value}</div>
          </div>
        ))}
      </div>

      <div className="flex gap-3 mb-4 flex-wrap">
        <Select value={year} onChange={setYear} style={{ width: 100 }}
          options={[year - 1, year, year + 1].map(y => ({ label: `${y}年`, value: y }))} />
        <Select value={quarter} onChange={setQuarter} allowClear placeholder="全年" style={{ width: 100 }}
          options={[1, 2, 3, 4].map(q => ({ label: `Q${q}`, value: q }))} />
        <Button icon={<DownloadOutlined />} onClick={() => downloadFile(dashboardApi.exportExcelUrl({ report: 'team_performance', year: String(year) }), 'team_performance.xlsx')}>
          导出
        </Button>
      </div>

      {/* Chart */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-6">
        <h3 className="text-sm font-bold text-slate-700 mb-4">赢单金额排行（万元）</h3>
        {chartData.length > 0 ? (
          <Column data={chartData} xField="name" yField="amount" height={280}
            color="#10b981"
            label={{ position: 'top' as const }}
          />
        ) : <div className="text-center py-8 text-slate-400 text-sm">暂无数据</div>}
      </div>

      {/* Leaderboard table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="user_id" dataSource={leaders} loading={loading} size="small"
          pagination={false}
          columns={[
            { title: '排名', key: 'rank', width: 60, render: (_: unknown, __: unknown, i: number) => {
              const colors = ['#f59e0b', '#94a3b8', '#cd7f32']
              return i < 3 ? (
                <span className="inline-flex w-6 h-6 rounded-full items-center justify-center text-white text-sm font-bold" style={{ background: colors[i] }}>{i + 1}</span>
              ) : <span className="text-slate-500 text-sm">{i + 1}</span>
            }},
            { title: '姓名', dataIndex: 'user_name', width: 120 },
            { title: '赢单数', dataIndex: 'won_count', width: 80, sorter: (a: LeaderEntry, b: LeaderEntry) => a.won_count - b.won_count },
            { title: '赢单金额', dataIndex: 'won_amount', width: 120, sorter: (a: LeaderEntry, b: LeaderEntry) => a.won_amount - b.won_amount,
              render: (v: number) => <span className="font-bold">¥{(v / 10000).toFixed(1)}万</span> },
            { title: '活跃商机', dataIndex: 'active_count', width: 80 },
            { title: '管线金额', dataIndex: 'pipeline_amount', width: 120,
              render: (v: number) => `¥${(v / 10000).toFixed(1)}万` },
            { title: '赢单率', dataIndex: 'win_ratio', width: 150,
              sorter: (a: LeaderEntry, b: LeaderEntry) => a.win_ratio - b.win_ratio,
              render: (v: number) => (
                <div className="flex items-center gap-2">
                  <Progress percent={Math.round(v * 100)} size="small" showInfo={false}
                    strokeColor={v >= 0.5 ? '#10b981' : v >= 0.3 ? '#f59e0b' : '#ef4444'} className="flex-1" />
                  <span className="text-sm font-bold w-10 text-right">{(v * 100).toFixed(0)}%</span>
                </div>
              ),
            },
          ]}
        />
      </div>
    </div>
  )
}
