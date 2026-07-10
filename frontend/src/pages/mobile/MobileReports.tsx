import { useState, useEffect } from 'react'
import MobileIcon from '@/components/MobileIcon'
import { useNavigate } from 'react-router-dom'
import { dashboardApi } from '@/api/dashboard'
import { approvalApi } from '@/api/approval'
import { usePageTitle } from '@/hooks/usePageTitle'

interface QuickStat {
  label: string; value: string | number; icon: string; color: string
}

export default function MobileReports() {
  usePageTitle('报表')
  const navigate = useNavigate()
  const [stats, setStats] = useState<QuickStat[]>([])
  const [approvalStats, setApprovalStats] = useState<{
    total_flows: number; approval_rate: number; avg_approval_hours: number; sla_compliance_rate: number
  } | null>(null)

  useEffect(() => {
    dashboardApi.stats().then((r: any) => {
      const d = r.data
      if (!d) return
      setStats([
        { label: '客户总数', value: d.customer_total, icon: 'business', color: 'text-primary' },
        { label: '商机总数', value: d.project_total, icon: 'rocket_launch', color: 'text-emerald-600' },
        { label: '管线总额', value: d.pipeline_value > 0 ? `¥${(d.pipeline_value / 10000).toFixed(0)}万` : '¥0', icon: 'payments', color: 'text-amber-600' },
        { label: '工单总数', value: d.ticket_total, icon: 'confirmation_number', color: 'text-indigo-600' },
      ])
    }).catch(() => {})
    approvalApi.statistics().then((r: any) => {
      if (r.data) setApprovalStats(r.data)
    }).catch(() => {})
  }, [])

  const reportLinks = [
    { label: '产品销售报表', desc: '产品引用分析、活跃度', icon: 'inventory_2', path: '/reports/product' },
    { label: '客户生命周期', desc: '客户等级、行业、地区分布', icon: 'groups', path: '/reports/customer-lifecycle' },
    { label: '团队绩效排行', desc: '赢单额、赢单率、排行榜', icon: 'leaderboard', path: '/reports/team-performance' },
    { label: '销售漏斗分析', desc: '各阶段转化率、金额分布', icon: 'filter_alt', path: '/analytics' },
    { label: '销售目标', desc: '目标设定与达成分析', icon: 'flag', path: '/sales-targets' },
  ]

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100">
        <h1 className="text-lg font-bold text-slate-900">报表中心</h1>
      </div>

      {/* Quick Stats */}
      <div className="px-4 pt-3">
        <div className="grid grid-cols-2 gap-2 mb-4">
          {stats.map((s) => (
            <div key={s.label} className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 flex items-center gap-2">
              <MobileIcon name={s.icon} className={`${s.color}`} style={{ fontSize: 20 }} />
              <div>
                <div className="text-sm font-black text-slate-900">{s.value}</div>
                <div className="text-[12px] text-slate-400 font-bold">{s.label}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Approval SLA */}
      {approvalStats && (
        <div className="px-4 mb-4">
          <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
            <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">审批SLA</div>
            <div className="grid grid-cols-4 gap-2 text-center">
              <div>
                <div className="text-lg font-black text-slate-900">{approvalStats.total_flows}</div>
                <div className="text-[12px] text-slate-400">总数</div>
              </div>
              <div>
                <div className="text-lg font-black text-emerald-600">{Math.round(approvalStats.approval_rate * 100)}%</div>
                <div className="text-[12px] text-slate-400">通过率</div>
              </div>
              <div>
                <div className="text-lg font-black text-blue-600">{approvalStats.avg_approval_hours}h</div>
                <div className="text-[12px] text-slate-400">平均时长</div>
              </div>
              <div>
                <div className={`text-lg font-black ${approvalStats.sla_compliance_rate >= 0.9 ? 'text-emerald-600' : 'text-amber-600'}`}>
                  {Math.round(approvalStats.sla_compliance_rate * 100)}%
                </div>
                <div className="text-[12px] text-slate-400">SLA达标</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Report Links */}
      <div className="px-4 space-y-2 pb-20">
        <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-2">详细报表</div>
        {reportLinks.map((r) => (
          <button key={r.path} onClick={() => navigate(r.path)}
            className="w-full bg-white rounded-xl border border-slate-100 shadow-sm p-4 flex items-center gap-3 text-left active:bg-slate-50">
            <MobileIcon name={r.icon} className="text-primary" style={{ fontSize: 24 }} />
            <div className="flex-1">
              <div className="text-sm font-bold text-slate-800">{r.label}</div>
              <div className="text-sm text-slate-400">{r.desc}</div>
            </div>
            <MobileIcon name="chevron_right" className="text-slate-300" style={{ fontSize: 16 }} />
          </button>
        ))}
      </div>
    </div>
  )
}
