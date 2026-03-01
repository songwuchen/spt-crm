import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button, Modal, Input, message } from 'antd'
import { dashboardApi } from '@/api/dashboard'
import { approvalApi } from '@/api/approval'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { ApprovalPendingItem } from '@/api/types'

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

export default function Dashboard() {
  usePageTitle('工作台')
  const [stats, setStats] = useState<Stats>({ customer_total: 0, lead_total: 0, monthly_new_customers: 0, pending_leads: 0, project_total: 0, active_projects: 0, quote_total: 0, solution_total: 0, milestone_total: 0, milestone_delayed: 0, invoice_total: 0, payment_received: 0, change_total: 0, ticket_total: 0, ticket_open: 0, pipeline_value: 0, contract_total: 0 })
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalPendingItem[]>([])
  const [alerts, setAlerts] = useState<AlertItem[]>([])
  const [trends, setTrends] = useState<Trends | null>(null)
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()

  const fetchData = () => {
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
  }

  useEffect(() => { fetchData() }, [])

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
        <button
          onClick={() => window.location.reload()}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold shadow-lg shadow-primary/20 hover:bg-primary/90 transition-colors"
        >
          <span className="material-symbols-outlined text-lg">refresh</span>
          刷新数据
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
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
      </div>

      {/* Pending Approvals */}
      {pendingApprovals.length > 0 && (
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
      {alerts.length > 0 && (
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

      {/* Three Column Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
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
            <TaskRow icon="warning" iconColor="text-red-600" label="逾期待办" count={0} urgent />
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

        {/* AI Copilot Suggestions */}
        <div className="bg-blue-50/50 rounded-xl border border-blue-100 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-primary">auto_awesome</span>
            <h3 className="text-sm font-bold text-slate-900">AI 智能建议</h3>
          </div>
          <div className="space-y-3">
            <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
              <div className="text-[10px] font-bold text-primary uppercase tracking-wider mb-1">建议跟进</div>
              <div className="text-sm font-bold text-slate-800 mb-1">高分线索待转化</div>
              <div className="text-xs text-slate-500">
                {stats.pending_leads > 0
                  ? `有 ${stats.pending_leads} 条线索评分较高，建议优先跟进转化。`
                  : '暂无高分线索需要跟进。'}
              </div>
              <button
                onClick={() => navigate('/leads')}
                className="w-full mt-3 py-2 bg-white border border-primary text-primary rounded-lg text-xs font-bold hover:bg-primary hover:text-white transition-colors"
              >
                查看线索列表
              </button>
            </div>
            <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
              <div className="text-[10px] font-bold text-primary uppercase tracking-wider mb-1">数据洞察</div>
              <div className="text-sm font-bold text-slate-800 mb-1">客户健康度分析</div>
              <div className="text-xs text-slate-500">
                当前共 {stats.customer_total} 个客户，本月新增 {stats.monthly_new_customers} 个。
              </div>
              <button
                onClick={() => navigate('/customers')}
                className="w-full mt-3 py-2 bg-white border border-primary text-primary rounded-lg text-xs font-bold hover:bg-primary hover:text-white transition-colors"
              >
                查看客户列表
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
