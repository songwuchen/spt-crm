import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Modal, Input, Select, message } from 'antd'
import { dashboardApi } from '@/api/dashboard'
import { approvalApi } from '@/api/approval'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { ApprovalPendingItem } from '@/api/types'
import { TrendChart, CollectionChart, RevenueChart, WinLossChart, FunnelChartPanel, LeaderboardChart, ContractExpiryPanel } from './DashboardCharts'

interface Stats {
  customer_total: number
  lead_total: number
  monthly_new_customers: number
  pending_leads: number
  project_total: number
  active_projects: number
  quote_total: number
  solution_total: number
  milestone_total: number
  milestone_delayed: number
  invoice_total: number
  payment_received: number
  change_total: number
  ticket_total: number
  ticket_open: number
  pipeline_value: number
  contract_total: number
}

interface AlertItem {
  type: string
  severity: string
  title: string
  content: string
  biz_type: string
  biz_id: string
}

interface TrendItem {
  current: number; previous: number; diff: number; pct: number
}
interface Trends {
  customers: TrendItem; leads: TrendItem; projects: TrendItem; tickets: TrendItem
}

interface MyOverview {
  my_customer_count: number
  my_active_projects: number
  my_pipeline: number
  my_won_month: number
  my_pending_leads: number
  my_open_tickets: number
  expiring_contracts: Array<{
    id: string; contract_no: string; amount_total: number
    project_name: string; signed_date: string | null
  }>
  stalled_projects: Array<{
    id: string; name: string; stage_code: string; days_stalled: number
  }>
}

interface FunnelItem {
  stage: string; label: string; count: number; amount: number
}

interface PaymentOv {
  total_planned: number; total_received: number
  overdue_count: number; overdue_amount: number
  upcoming_30d_amount: number; collection_rate: number
}

interface LeaderItem {
  owner_id: string; owner_name: string
  won_count: number; won_amount: number
  active_count: number; pipeline_amount: number
}

function KpiCard({ icon, label, value, trend, trendType }: {
  icon: string; label: string; value: number | string
  trend?: string; trendType?: 'up' | 'down' | 'stable'
}) {
  const trendColors = {
    up: 'bg-emerald-50 text-emerald-600',
    down: 'bg-red-50 text-red-500',
    stable: 'bg-slate-50 text-slate-400 border border-slate-100',
  }
  return (
    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
      <div className="flex items-center gap-2 mb-3">
        <span className="material-symbols-outlined text-primary text-xl">{icon}</span>
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-3xl font-black text-slate-900">{value}</span>
        {trend && trendType && (
          <span className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-[11px] font-bold ${trendColors[trendType]}`}>
            {trendType === 'up' && <span className="material-symbols-outlined text-sm">trending_up</span>}
            {trendType === 'down' && <span className="material-symbols-outlined text-sm">trending_down</span>}
            {trend}
          </span>
        )}
      </div>
    </div>
  )
}

function TaskRow({ icon, iconColor, label, count, urgent }: {
  icon: string; iconColor: string; label: string; count: number; urgent?: boolean
}) {
  return (
    <div className={`flex items-center gap-3 p-3.5 rounded-lg border ${
      urgent ? 'bg-red-50 border-red-100' : 'bg-slate-50 border-slate-100'
    }`}>
      <span className={`material-symbols-outlined ${iconColor}`}>{icon}</span>
      <span className="flex-1 text-sm font-medium text-slate-700">{label}</span>
      <span className={`text-sm font-bold ${urgent ? 'text-red-600' : 'text-slate-900'}`}>{count}</span>
    </div>
  )
}

const stageColors = ['bg-blue-500', 'bg-cyan-500', 'bg-teal-500', 'bg-emerald-500', 'bg-green-500', 'bg-lime-500']

const REFRESH_INTERVALS = [
  { value: 0, label: '不刷新' },
  { value: 30, label: '30秒' },
  { value: 60, label: '1分钟' },
  { value: 300, label: '5分钟' },
]

interface DashboardCard {
  key: string
  label: string
  defaultVisible: boolean
}

const DASHBOARD_CARDS: DashboardCard[] = [
  { key: 'myOverview', label: '我的概览', defaultVisible: true },
  { key: 'kpiCards', label: 'KPI 指标卡', defaultVisible: true },
  { key: 'approvals', label: '待审批', defaultVisible: true },
  { key: 'alerts', label: '风险预警', defaultVisible: true },
  { key: 'funnelPayment', label: '销售漏斗 + 回款概览', defaultVisible: true },
  { key: 'trendWinLoss', label: '趋势图 + 赢输分析', defaultVisible: true },
  { key: 'collectionRevenue', label: '回款分析 + 营收分析', defaultVisible: true },
  { key: 'approvalSla', label: '审批SLA概览', defaultVisible: true },
  { key: 'contractExpiry', label: '合同到期预警', defaultVisible: true },
  { key: 'tasksActionsLeaderboard', label: '任务 + 快捷操作 + 排行榜', defaultVisible: true },
]

const STORAGE_KEY = 'dashboard_card_visibility'

function loadCardVisibility(): Record<string, boolean> {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved)
  } catch {}
  const defaults: Record<string, boolean> = {}
  DASHBOARD_CARDS.forEach((c) => { defaults[c.key] = c.defaultVisible })
  return defaults
}

function saveCardVisibility(v: Record<string, boolean>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(v))
}

export default function Dashboard() {
  usePageTitle('工作台')
  const [stats, setStats] = useState<Stats>({ customer_total: 0, lead_total: 0, monthly_new_customers: 0, pending_leads: 0, project_total: 0, active_projects: 0, quote_total: 0, solution_total: 0, milestone_total: 0, milestone_delayed: 0, invoice_total: 0, payment_received: 0, change_total: 0, ticket_total: 0, ticket_open: 0, pipeline_value: 0, contract_total: 0 })
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalPendingItem[]>([])
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [trends, setTrends] = useState<Trends | null>(null)
  const [myOv, setMyOv] = useState<MyOverview | null>(null)
  const [funnel, setFunnel] = useState<FunnelItem[]>([])
  const [paymentOv, setPaymentOv] = useState<PaymentOv | null>(null)
  const [leaderboard, setLeaderboard] = useState<LeaderItem[]>([])
  const [approvalStats, setApprovalStats] = useState<{
    total_flows: number; status_breakdown: Record<string, number>
    avg_approval_hours: number; approval_rate: number; sla_compliance_rate: number
    by_biz_type: Record<string, number>; top_approvers: { name: string; count: number }[]
  } | null>(null)
  const [refreshInterval, setRefreshInterval] = useState(0)
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date())
  const [cardVisibility, setCardVisibility] = useState<Record<string, boolean>>(loadCardVisibility)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const isVisible = (key: string) => cardVisibility[key] !== false
  const refreshTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()

  const fetchData = useCallback(() => {
    dashboardApi.stats().then((res: any) => {
      if (res.data) setStats(res.data)
    }).catch(() => { message.error('加载统计数据失败') })
    dashboardApi.alerts().then((res: any) => {
      if (res.data) setAlerts(res.data)
    }).catch(() => {})
    dashboardApi.trends().then((res: any) => {
      if (res.data) setTrends(res.data)
    }).catch(() => {})
    approvalApi.myPending().then((r) => setPendingApprovals(r.data)).catch(() => {})
    dashboardApi.myOverview().then((res: any) => {
      if (res.data) setMyOv(res.data)
    }).catch(() => {})
    dashboardApi.funnel().then((res: any) => {
      if (res.data) setFunnel(res.data)
    }).catch(() => {})
    dashboardApi.paymentOverview().then((res: any) => {
      if (res.data) setPaymentOv(res.data)
    }).catch(() => {})
    dashboardApi.leaderboard().then((res: any) => {
      if (res.data) setLeaderboard(res.data)
    }).catch(() => {})
    approvalApi.statistics().then((r: any) => {
      if (r.data) setApprovalStats(r.data)
    }).catch(() => {})
  }, [])

  useEffect(() => { fetchData(); setLastRefresh(new Date()) }, [fetchData])

  // Auto-refresh
  useEffect(() => {
    if (refreshTimerRef.current) clearInterval(refreshTimerRef.current)
    if (refreshInterval > 0) {
      refreshTimerRef.current = setInterval(() => {
        fetchData()
        setLastRefresh(new Date())
      }, refreshInterval * 1000)
    }
    return () => { if (refreshTimerRef.current) clearInterval(refreshTimerRef.current) }
  }, [refreshInterval, fetchData])

  const handleApprove = async (taskId: string) => {
    try {
      await approvalApi.decide(taskId, { action: 'approved' })
      message.success('已审批通过')
      fetchData()
    } catch {
      message.error('审批操作失败')
    }
  }
  const handleReject = async (taskId: string) => {
    Modal.confirm({
      title: '驳回审批', content: '确定要驳回此审批吗？',
      okType: 'danger', okText: '驳回',
      onOk: async () => {
        await approvalApi.decide(taskId, { action: 'rejected', comment: '驳回' })
        message.success('已驳回')
        fetchData()
      },
    })
  }

  const funnelMax = Math.max(...funnel.map((f) => f.count), 1)

  return (
    <div>
      {/* Page Title */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
            工作台
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            欢迎回来，<span className="font-semibold text-slate-700">{user?.real_name || user?.username}</span>。
            {stats.pending_leads > 0 && (
              <> 有 <span className="text-primary font-bold">{stats.pending_leads}</span> 条待跟进线索。</>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-1 px-3 py-2 rounded-lg border border-slate-200 bg-white text-sm text-slate-600 hover:bg-slate-50 transition-colors"
            title="看板设置">
            <span className="material-symbols-outlined text-base">settings</span>
          </button>
          <Select size="small" value={refreshInterval} onChange={setRefreshInterval}
            options={REFRESH_INTERVALS} style={{ width: 100 }}
            suffixIcon={<span className="material-symbols-outlined text-sm">timer</span>} />
          <span className="text-[10px] text-slate-400 hidden sm:inline">
            {lastRefresh.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })} 更新
          </span>
          <button onClick={() => { fetchData(); setLastRefresh(new Date()) }}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold shadow-lg shadow-primary/20 hover:bg-primary/90 transition-colors">
            <span className="material-symbols-outlined text-lg">refresh</span>
            刷新
          </button>
        </div>
      </div>

      {/* Personal Overview */}
      {isVisible('myOverview') && myOv && (
        <div className="bg-gradient-to-r from-primary/5 to-blue-50 rounded-xl border border-primary/10 p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-primary">person</span>
            <h3 className="text-sm font-bold text-slate-900">我的概览</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <div className="text-center">
              <div className="text-2xl font-black text-slate-900">{myOv.my_customer_count}</div>
              <div className="text-xs text-slate-500 mt-1">我的客户</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-black text-slate-900">{myOv.my_active_projects}</div>
              <div className="text-xs text-slate-500 mt-1">进行中商机</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-black text-primary">{myOv.my_pipeline > 0 ? `¥${(myOv.my_pipeline / 10000).toFixed(1)}万` : '¥0'}</div>
              <div className="text-xs text-slate-500 mt-1">我的管线</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-black text-emerald-600">{myOv.my_won_month}</div>
              <div className="text-xs text-slate-500 mt-1">本月赢单</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-black text-amber-600">{myOv.my_pending_leads}</div>
              <div className="text-xs text-slate-500 mt-1">待跟进线索</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-black text-red-500">{myOv.my_open_tickets}</div>
              <div className="text-xs text-slate-500 mt-1">处理中工单</div>
            </div>
          </div>

          {/* Stalled projects & contracts */}
          {(myOv.stalled_projects.length > 0 || myOv.expiring_contracts.length > 0) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 pt-4 border-t border-primary/10">
              {myOv.stalled_projects.length > 0 && (
                <div>
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">待跟进商机</div>
                  <div className="space-y-1.5">
                    {myOv.stalled_projects.map((p) => (
                      <div key={p.id} onClick={() => navigate(`/opportunities/${p.id}`)}
                        className="flex items-center gap-2 p-2 rounded-lg bg-white/70 border border-amber-100 cursor-pointer hover:shadow-sm transition-shadow">
                        <span className="material-symbols-outlined text-amber-500 text-base">schedule</span>
                        <span className="text-sm font-medium text-slate-800 flex-1 truncate">{p.name}</span>
                        <span className="text-xs font-bold text-amber-600">{p.days_stalled}天未更新</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {myOv.expiring_contracts.length > 0 && (
                <div>
                  <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">我的合同</div>
                  <div className="space-y-1.5">
                    {myOv.expiring_contracts.map((c) => (
                      <div key={c.id} className="flex items-center gap-2 p-2 rounded-lg bg-white/70 border border-slate-100">
                        <span className="material-symbols-outlined text-blue-500 text-base">description</span>
                        <span className="text-sm font-medium text-slate-800 flex-1 truncate">{c.contract_no}</span>
                        <span className="text-xs text-slate-500">¥{c.amount_total?.toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* KPI Cards */}
      {isVisible('kpiCards') && <><div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <KpiCard icon="business" label="客户总数" value={stats.customer_total}
          trend={trends ? (trends.customers.diff >= 0 ? `+${trends.customers.diff}` : `${trends.customers.diff}`) : undefined}
          trendType={trends ? (trends.customers.diff > 0 ? 'up' : trends.customers.diff < 0 ? 'down' : 'stable') : undefined} />
        <KpiCard icon="trending_up" label="线索总数" value={stats.lead_total}
          trend={trends ? (trends.leads.diff >= 0 ? `+${trends.leads.diff}` : `${trends.leads.diff}`) : undefined}
          trendType={trends ? (trends.leads.diff > 0 ? 'up' : trends.leads.diff < 0 ? 'down' : 'stable') : undefined} />
        <KpiCard icon="person_add" label="本月新增客户" value={stats.monthly_new_customers}
          trend={trends ? `环比${trends.customers.pct >= 0 ? '+' : ''}${trends.customers.pct}%` : undefined}
          trendType={trends ? (trends.customers.pct > 0 ? 'up' : trends.customers.pct < 0 ? 'down' : 'stable') : undefined} />
        <KpiCard icon="schedule" label="待跟进线索" value={stats.pending_leads}
          trend={stats.pending_leads > 5 ? '需关注' : '正常'} trendType={stats.pending_leads > 5 ? 'down' : 'stable'} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard icon="rocket_launch" label="商机总数" value={stats.project_total} />
        <KpiCard icon="play_circle" label="进行中商机" value={stats.active_projects}
          trend={stats.active_projects > 0 ? '活跃' : ''} trendType="up" />
        <KpiCard icon="payments" label="管线总额" value={stats.pipeline_value > 0 ? `¥${(stats.pipeline_value / 10000).toFixed(0)}万` : '¥0'} />
        <KpiCard icon="handshake" label="合同/报价" value={`${stats.contract_total}/${stats.quote_total}`} />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <KpiCard icon="flag" label="交付里程碑" value={stats.milestone_total}
          trend={stats.milestone_delayed > 0 ? `${stats.milestone_delayed} 延期` : ''} trendType={stats.milestone_delayed > 0 ? 'down' : 'stable'} />
        <KpiCard icon="receipt_long" label="发票总数" value={stats.invoice_total} />
        <KpiCard icon="swap_horiz" label="变更单" value={stats.change_total} />
        <KpiCard icon="confirmation_number" label="售后工单" value={stats.ticket_total}
          trend={stats.ticket_open > 0 ? `${stats.ticket_open} 待处理` : '全部完结'} trendType={stats.ticket_open > 0 ? 'down' : 'stable'} />
      </div></>}

      {/* Pending Approvals */}
      {isVisible('approvals') && pendingApprovals.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-amber-500">pending_actions</span>
            <h3 className="text-sm font-bold text-slate-900">待我审批</h3>
            <span className="px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 text-xs font-bold">{pendingApprovals.length}</span>
          </div>
          <div className="space-y-2">
            {pendingApprovals.map((item) => (
              <div key={item.id} className="flex items-center gap-3 p-3 rounded-lg bg-amber-50 border border-amber-100">
                <span className="material-symbols-outlined text-amber-500">task_alt</span>
                <div className="flex-1">
                  <div className="text-sm font-bold text-slate-800">{item.flow?.title || item.flow?.biz_type}</div>
                  <div className="text-xs text-slate-500">
                    提交人: {item.flow?.submitted_by_name} · 节点 {item.node_order}/{item.flow?.total_nodes}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => handleApprove(item.id)}
                    className="px-3 py-1.5 bg-emerald-500 text-white rounded-lg text-xs font-bold hover:bg-emerald-600 transition-colors">
                    通过
                  </button>
                  <button onClick={() => handleReject(item.id)}
                    className="px-3 py-1.5 bg-white text-red-500 border border-red-200 rounded-lg text-xs font-bold hover:bg-red-50 transition-colors">
                    驳回
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Alerts */}
      {isVisible('alerts') && alerts.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-red-500">notifications_active</span>
            <h3 className="text-sm font-bold text-slate-900">风险预警</h3>
            <span className="px-2 py-0.5 rounded-full bg-red-100 text-red-700 text-xs font-bold">{alerts.length}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
            {alerts.slice(0, 6).map((a, i) => {
              const iconMap: Record<string, { icon: string; color: string }> = {
                stalled: { icon: 'pause_circle', color: 'text-amber-500' },
                milestone_delayed: { icon: 'event_busy', color: 'text-red-500' },
                high_risk: { icon: 'warning', color: 'text-red-600' },
                urgent_ticket: { icon: 'support_agent', color: 'text-orange-500' },
              }
              const t = iconMap[a.type] || iconMap.stalled
              return (
                <div key={i} onClick={() => {
                  if (a.biz_type === 'project') navigate(`/opportunities/${a.biz_id}`)
                  else if (a.biz_type === 'service_ticket') navigate(`/service-tickets/${a.biz_id}`)
                  else if (a.biz_type === 'approval_flow') navigate('/approvals')
                }} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer hover:shadow-sm transition-shadow ${
                  a.severity === 'critical' ? 'bg-red-50 border-red-100' : 'bg-amber-50 border-amber-100'
                }`}>
                  <span className={`material-symbols-outlined ${t.color} mt-0.5`}>{t.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-bold text-slate-800 truncate">{a.title}</div>
                    <div className="text-[11px] text-slate-500 truncate">{a.content}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Sales Funnel + Payment Overview */}
      {isVisible('funnelPayment') && <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Sales Funnel */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-blue-500">filter_alt</span>
            <h3 className="text-sm font-bold text-slate-900">销售漏斗</h3>
          </div>
          {funnel.length > 0 ? (
            <FunnelChartPanel funnel={funnel} />
          ) : (
            <div className="text-center text-slate-400 text-sm py-8">暂无漏斗数据</div>
          )}
        </div>

        {/* Payment Overview */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-emerald-500">account_balance</span>
            <h3 className="text-sm font-bold text-slate-900">回款概览</h3>
          </div>
          {paymentOv ? (
            <div>
              <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                  <div className="text-xs text-emerald-600 font-bold mb-1">已回款</div>
                  <div className="text-xl font-black text-emerald-700">¥{(paymentOv.total_received / 10000).toFixed(1)}万</div>
                </div>
                <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                  <div className="text-xs text-blue-600 font-bold mb-1">计划总额</div>
                  <div className="text-xl font-black text-blue-700">¥{(paymentOv.total_planned / 10000).toFixed(1)}万</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-2 rounded-lg bg-slate-50">
                  <div className="text-lg font-black text-slate-900">{paymentOv.collection_rate}%</div>
                  <div className="text-[10px] text-slate-500">回款率</div>
                </div>
                <div className="text-center p-2 rounded-lg bg-red-50">
                  <div className="text-lg font-black text-red-600">{paymentOv.overdue_count}</div>
                  <div className="text-[10px] text-slate-500">逾期笔数</div>
                </div>
                <div className="text-center p-2 rounded-lg bg-amber-50">
                  <div className="text-lg font-black text-amber-600">¥{(paymentOv.upcoming_30d_amount / 10000).toFixed(1)}万</div>
                  <div className="text-[10px] text-slate-500">30天内到期</div>
                </div>
              </div>
              {/* Collection rate bar */}
              <div className="mt-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-slate-500">回款进度</span>
                  <span className="text-xs font-bold text-emerald-600">{paymentOv.collection_rate}%</span>
                </div>
                <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full transition-all"
                    style={{ width: `${Math.min(paymentOv.collection_rate, 100)}%` }} />
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-400 text-sm py-8">暂无回款数据</div>
          )}
        </div>
      </div>}

      {/* Charts Row: Trend + Win/Loss */}
      {isVisible('trendWinLoss') && <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2">
          <TrendChart />
        </div>
        <WinLossChart />
      </div>}

      {/* Charts Row: Collection + Revenue */}
      {isVisible('collectionRevenue') && <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <CollectionChart />
        <RevenueChart />
      </div>}

      {/* Approval SLA Overview */}
      {isVisible('approvalSla') && approvalStats && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-indigo-500">verified</span>
            <h3 className="text-sm font-bold text-slate-900">审批SLA概览</h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-4">
            <div className="text-center p-3 rounded-lg bg-slate-50">
              <div className="text-2xl font-black text-slate-900">{approvalStats.total_flows}</div>
              <div className="text-[10px] text-slate-500 font-bold">审批总数</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-emerald-50">
              <div className="text-2xl font-black text-emerald-600">{Math.round(approvalStats.approval_rate * 100)}%</div>
              <div className="text-[10px] text-slate-500 font-bold">通过率</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-blue-50">
              <div className="text-2xl font-black text-blue-600">{approvalStats.avg_approval_hours}h</div>
              <div className="text-[10px] text-slate-500 font-bold">平均审批时长</div>
            </div>
            <div className={`text-center p-3 rounded-lg ${approvalStats.sla_compliance_rate >= 0.9 ? 'bg-emerald-50' : approvalStats.sla_compliance_rate >= 0.7 ? 'bg-amber-50' : 'bg-red-50'}`}>
              <div className={`text-2xl font-black ${approvalStats.sla_compliance_rate >= 0.9 ? 'text-emerald-600' : approvalStats.sla_compliance_rate >= 0.7 ? 'text-amber-600' : 'text-red-600'}`}>
                {Math.round(approvalStats.sla_compliance_rate * 100)}%
              </div>
              <div className="text-[10px] text-slate-500 font-bold">SLA达标率</div>
            </div>
            <div className="text-center p-3 rounded-lg bg-amber-50">
              <div className="text-2xl font-black text-amber-600">{approvalStats.status_breakdown.pending || 0}</div>
              <div className="text-[10px] text-slate-500 font-bold">待处理</div>
            </div>
          </div>
          {approvalStats.top_approvers.length > 0 && (
            <div>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">审批人排行</div>
              <div className="flex flex-wrap gap-2">
                {approvalStats.top_approvers.slice(0, 5).map((a, i) => (
                  <span key={i} className="px-2.5 py-1 bg-slate-50 border border-slate-100 rounded-lg text-xs">
                    <span className="font-bold text-slate-700">{a.name}</span>
                    <span className="text-slate-400 ml-1">{a.count}次</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Contract Expiry Warning */}
      {isVisible('contractExpiry') && <div className="mb-6">
        <ContractExpiryPanel />
      </div>}

      {/* Three Column Grid: Tasks + Quick Actions + Leaderboard */}
      {isVisible('tasksActionsLeaderboard') && <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        {/* Today's Tasks */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-primary">calendar_today</span>
              <h3 className="text-sm font-bold text-slate-900">今日任务</h3>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs font-bold">
              {stats.pending_leads + stats.monthly_new_customers} 项
            </span>
          </div>
          <div className="space-y-2">
            <TaskRow icon="chat" iconColor="text-blue-600" label="客户跟进" count={stats.pending_leads} />
            <TaskRow icon="person_add" iconColor="text-emerald-600" label="新客户建档" count={stats.monthly_new_customers} />
            <TaskRow icon="warning" iconColor="text-red-600" label="逾期待办" count={paymentOv?.overdue_count || 0} urgent={!!(paymentOv?.overdue_count)} />
          </div>
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-amber-500">bolt</span>
            <h3 className="text-sm font-bold text-slate-900">快捷操作</h3>
          </div>
          <div className="space-y-2">
            <button
              onClick={() => navigate('/customers/new')}
              className="w-full flex items-center gap-3 p-3.5 rounded-lg border border-slate-100 bg-slate-50 hover:border-primary/40 hover:bg-primary/5 transition-all text-left"
            >
              <span className="material-symbols-outlined text-primary">add_business</span>
              <div>
                <div className="text-sm font-bold text-slate-800">新建客户</div>
                <div className="text-[11px] text-slate-500">录入新的客户信息</div>
              </div>
            </button>
            <button
              onClick={() => navigate('/leads/new')}
              className="w-full flex items-center gap-3 p-3.5 rounded-lg border border-slate-100 bg-slate-50 hover:border-primary/40 hover:bg-primary/5 transition-all text-left"
            >
              <span className="material-symbols-outlined text-emerald-600">add_circle</span>
              <div>
                <div className="text-sm font-bold text-slate-800">新建线索</div>
                <div className="text-[11px] text-slate-500">创建新的销售线索</div>
              </div>
            </button>
            <button
              onClick={() => navigate('/opportunities/new')}
              className="w-full flex items-center gap-3 p-3.5 rounded-lg border border-slate-100 bg-slate-50 hover:border-primary/40 hover:bg-primary/5 transition-all text-left"
            >
              <span className="material-symbols-outlined text-amber-500">rocket_launch</span>
              <div>
                <div className="text-sm font-bold text-slate-800">新建商机</div>
                <div className="text-[11px] text-slate-500">创建新的商机项目</div>
              </div>
            </button>
          </div>
        </div>

        {/* Leaderboard */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-amber-500">emoji_events</span>
            <h3 className="text-sm font-bold text-slate-900">业绩排行</h3>
          </div>
          {leaderboard.length > 0 ? (
            <LeaderboardChart leaderboard={leaderboard} />
          ) : (
            <div className="text-center text-slate-400 text-sm py-8">暂无排行数据</div>
          )}
        </div>
      </div>}

      {/* Dashboard Settings Modal */}
      <Modal title="看板设置" open={settingsOpen} onCancel={() => setSettingsOpen(false)}
        footer={null} width={480}>
        <p className="text-sm text-slate-500 mb-4">选择要在工作台上显示的模块</p>
        <div className="space-y-2">
          {DASHBOARD_CARDS.map((card) => (
            <label key={card.key}
              className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-all ${
                cardVisibility[card.key] !== false
                  ? 'border-primary/30 bg-primary/5'
                  : 'border-slate-100 hover:border-slate-200'
              }`}>
              <input type="checkbox" className="accent-primary w-4 h-4"
                checked={cardVisibility[card.key] !== false}
                onChange={(e) => {
                  const next = { ...cardVisibility, [card.key]: e.target.checked }
                  setCardVisibility(next)
                  saveCardVisibility(next)
                }} />
              <span className="text-sm font-medium text-slate-700">{card.label}</span>
            </label>
          ))}
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <Button size="small" onClick={() => {
            const defaults: Record<string, boolean> = {}
            DASHBOARD_CARDS.forEach((c) => { defaults[c.key] = c.defaultVisible })
            setCardVisibility(defaults)
            saveCardVisibility(defaults)
          }}>恢复默认</Button>
        </div>
      </Modal>
    </div>
  )
}
