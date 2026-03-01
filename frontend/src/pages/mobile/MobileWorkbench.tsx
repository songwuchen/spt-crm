import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { dashboardApi } from '@/api/dashboard'
import { useAuthStore } from '@/stores/useAuthStore'
import { usePageTitle } from '@/hooks/usePageTitle'

interface Stats {
  customer_total: number; lead_total: number; monthly_new_customers: number; pending_leads: number
  project_total: number; active_projects: number; pipeline_value: number; ticket_open: number
  contract_total: number; quote_total: number; ticket_total: number
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
  const user = useAuthStore((s) => s.user)
  const navigate = useNavigate()

  useEffect(() => {
    dashboardApi.stats().then((res: any) => {
      if (res.data) setStats(res.data)
    }).catch(() => message.error('加载失败'))
  }, [])

  return (
    <div>
      {/* Welcome */}
      <div className="mb-4">
        <h1 className="text-xl font-extrabold text-slate-900">
          你好，{user?.real_name || user?.username}
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">
          {stats.pending_leads > 0 ? `有 ${stats.pending_leads} 条待跟进线索` : '暂无待办'}
        </p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <StatCard icon="business" label="客户" value={stats.customer_total} color="text-blue-600" onClick={() => navigate('/m/customers')} />
        <StatCard icon="trending_up" label="线索" value={stats.lead_total} color="text-emerald-600" />
        <StatCard icon="rocket_launch" label="商机" value={stats.active_projects} color="text-amber-600" onClick={() => navigate('/m/opportunities')} />
        <StatCard icon="payments" label="管线" value={stats.pipeline_value > 0 ? `¥${(stats.pipeline_value / 10000).toFixed(0)}万` : '¥0'} color="text-violet-600" />
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 mb-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">快捷操作</h3>
        <div className="grid grid-cols-4 gap-2">
          {[
            { icon: 'add_business', label: '新客户', path: '/customers/new', color: 'text-blue-600 bg-blue-50' },
            { icon: 'add_circle', label: '新线索', path: '/leads/new', color: 'text-emerald-600 bg-emerald-50' },
            { icon: 'rocket', label: '新商机', path: '/opportunities/new', color: 'text-amber-600 bg-amber-50' },
            { icon: 'qr_code_scanner', label: '扫名片', path: '#', color: 'text-slate-600 bg-slate-50' },
          ].map((a) => (
            <button key={a.label} onClick={() => a.path !== '#' && navigate(a.path)}
              className="flex flex-col items-center gap-1.5 py-2 bg-transparent border-0 cursor-pointer">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${a.color}`}>
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{a.icon}</span>
              </div>
              <span className="text-[11px] font-bold text-slate-700">{a.label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="space-y-3">
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center">
            <span className="material-symbols-outlined text-amber-600" style={{ fontSize: 20 }}>schedule</span>
          </div>
          <div className="flex-1">
            <div className="text-sm font-bold text-slate-800">待跟进线索</div>
            <div className="text-xs text-slate-500">{stats.pending_leads} 条需要处理</div>
          </div>
          <span className="text-2xl font-black text-amber-600">{stats.pending_leads}</span>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center">
            <span className="material-symbols-outlined text-red-500" style={{ fontSize: 20 }}>support_agent</span>
          </div>
          <div className="flex-1">
            <div className="text-sm font-bold text-slate-800">未关闭工单</div>
            <div className="text-xs text-slate-500">{stats.ticket_open} 个需要关注</div>
          </div>
          <span className="text-2xl font-black text-red-500">{stats.ticket_open}</span>
        </div>
      </div>
    </div>
  )
}
