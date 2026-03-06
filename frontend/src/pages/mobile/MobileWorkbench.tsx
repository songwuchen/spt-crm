import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { dashboardApi } from '@/api/dashboard'
import { approvalApi } from '@/api/approval'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'

interface Stats {
  customer_total: number; lead_total: number; monthly_new_customers: number; pending_leads: number
  project_total: number; active_projects: number; pipeline_value: number; ticket_open: number
  contract_total: number; quote_total: number; ticket_total: number
}

interface MyOverview {
  my_customer_count: number; my_active_projects: number; my_pipeline: number
  my_won_month: number; my_pending_leads: number; my_open_tickets: number
  stalled_projects: Array<{ id: string; name: string; stage_code: string; days_stalled: number }>
}

function StatCard({ icon, label, value, color, onClick }: {
  icon: string; label: string; value: string | number; color: string; onClick?: () => void
}) {
  return (
    <div onClick={onClick} className={`bg-white rounded-xl border border-slate-100 shadow-sm p-3 ${onClick ? 'cursor-pointer active:bg-slate-50' : ''}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={`material-symbols-outlined ${color}`} style={{ fontSize: 18 }}>{icon}</span>
        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</span>
      </div>
      <div className="text-xl font-black text-slate-900">{value}</div>
    </div>
  )
}

export default function MobileWorkbench() {
  usePageTitle('工作台')
  const [stats, setStats] = useState<Stats>({
    customer_total: 0, lead_total: 0, monthly_new_customers: 0, pending_leads: 0,
    project_total: 0, active_projects: 0, pipeline_value: 0, ticket_open: 0,
    contract_total: 0, quote_total: 0, ticket_total: 0,
  })
  const [myOv, setMyOv] = useState<MyOverview | null>(null)
  const [pendingCount, setPendingCount] = useState(0)
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()

  useEffect(() => {
    dashboardApi.stats().then((res: any) => {
      if (res.data) setStats(res.data)
    }).catch(() => message.error('加载失败'))
    dashboardApi.myOverview().then((res: any) => {
      if (res.data) setMyOv(res.data)
    }).catch(() => {})
    approvalApi.myPending().then((r) => {
      setPendingCount(r.data?.length || 0)
    }).catch(() => {})
  }, [])

  return (
    <div>
      {/* Welcome */}
      <div className="mb-4">
        <h1 className="text-xl font-extrabold text-slate-900">
          你好，{user?.real_name || user?.username}
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          {myOv && myOv.my_pending_leads > 0 ? `有 ${myOv.my_pending_leads} 条待跟进线索` : '暂无待办'}
        </p>
      </div>

      {/* Personal KPI Grid */}
      {myOv && (
        <div className="grid grid-cols-3 gap-2 mb-4">
          <div className="bg-gradient-to-br from-primary/10 to-blue-50 rounded-xl p-3 text-center border border-primary/10">
            <div className="text-lg font-black text-slate-900">{myOv.my_customer_count}</div>
            <div className="text-[10px] text-slate-500 font-bold">我的客户</div>
          </div>
          <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl p-3 text-center border border-emerald-100">
            <div className="text-lg font-black text-emerald-600">{myOv.my_active_projects}</div>
            <div className="text-[10px] text-slate-500 font-bold">进行中商机</div>
          </div>
          <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-3 text-center border border-amber-100">
            <div className="text-lg font-black text-amber-600">{myOv.my_won_month}</div>
            <div className="text-[10px] text-slate-500 font-bold">本月赢单</div>
          </div>
        </div>
      )}

      {/* KPI Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <StatCard icon="business" label="客户" value={stats.customer_total} color="text-blue-600" onClick={() => navigate('/m/customers')} />
        <StatCard icon="rocket_launch" label="商机" value={stats.active_projects} color="text-amber-600" onClick={() => navigate('/m/opportunities')} />
        <StatCard icon="payments" label="管线" value={myOv && myOv.my_pipeline > 0 ? `¥${(myOv.my_pipeline / 10000).toFixed(0)}万` : '¥0'} color="text-violet-600" />
        <StatCard icon="task_alt" label="待审批" value={pendingCount} color="text-amber-500" onClick={() => navigate('/m/approvals')} />
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 mb-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">快捷操作</h3>
        <div className="grid grid-cols-4 gap-2">
          {[
            { icon: 'add_business', label: '新客户', path: '/m/customers/new', color: 'text-blue-600 bg-blue-50' },
            { icon: 'contact_phone', label: '写跟进', path: '/m/follow-up/new', color: 'text-purple-600 bg-purple-50' },
            { icon: 'checklist', label: '待办', path: '/m/tasks', color: 'text-emerald-600 bg-emerald-50' },
            { icon: 'task_alt', label: '审批', path: '/m/approvals', color: 'text-amber-600 bg-amber-50' },
          ].map((a) => (
            <button key={a.label} onClick={() => navigate(a.path)}
              className="flex flex-col items-center gap-1.5 py-2 bg-transparent border-0 cursor-pointer">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${a.color}`}>
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{a.icon}</span>
              </div>
              <span className="text-[11px] font-bold text-slate-700">{a.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Stalled Projects */}
      {myOv && myOv.stalled_projects.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 mb-4">
          <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">待跟进商机</h3>
          <div className="space-y-2">
            {myOv.stalled_projects.map((p) => (
              <div key={p.id} onClick={() => navigate(`/m/opportunities`)}
                className="flex items-center gap-3 p-2.5 rounded-lg bg-amber-50 border border-amber-100 cursor-pointer active:bg-amber-100">
                <span className="material-symbols-outlined text-amber-500" style={{ fontSize: 18 }}>schedule</span>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-bold text-slate-800 truncate">{p.name}</div>
                  <div className="text-[10px] text-slate-500">{p.stage_code}</div>
                </div>
                <span className="text-xs font-bold text-amber-600">{p.days_stalled}天</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Summary Cards */}
      <div className="space-y-3">
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center">
            <span className="material-symbols-outlined text-amber-600" style={{ fontSize: 20 }}>schedule</span>
          </div>
          <div className="flex-1">
            <div className="text-sm font-bold text-slate-800">待跟进线索</div>
            <div className="text-xs text-slate-500">{myOv?.my_pending_leads || stats.pending_leads} 条需要处理</div>
          </div>
          <span className="text-2xl font-black text-amber-600">{myOv?.my_pending_leads || stats.pending_leads}</span>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center">
            <span className="material-symbols-outlined text-red-500" style={{ fontSize: 20 }}>support_agent</span>
          </div>
          <div className="flex-1">
            <div className="text-sm font-bold text-slate-800">未关闭工单</div>
            <div className="text-xs text-slate-500">{myOv?.my_open_tickets || stats.ticket_open} 个需要关注</div>
          </div>
          <span className="text-2xl font-black text-red-500">{myOv?.my_open_tickets || stats.ticket_open}</span>
        </div>
      </div>
    </div>
  )
}
