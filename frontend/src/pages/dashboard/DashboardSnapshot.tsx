import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message, Spin } from 'antd'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'

interface SnapshotData {
  title: string
  created_by_name: string
  created_at: string
  snapshot_data: {
    stats?: Record<string, number>
    trends?: Record<string, { current: number; previous: number; diff: number; pct: number }>
    myOv?: Record<string, unknown>
    funnel?: { stage: string; label: string; count: number; amount: number }[]
    paymentOv?: Record<string, number>
    leaderboard?: { owner_name: string; won_count: number; won_amount: number }[]
    approvalStats?: { total_flows: number; approval_rate: number; avg_approval_hours: number; sla_compliance_rate: number }
    pendingApprovals?: number
  }
  card_visibility?: Record<string, boolean>
  card_order?: string[]
}

const stageColors = ['bg-blue-500', 'bg-cyan-500', 'bg-teal-500', 'bg-emerald-500', 'bg-green-500', 'bg-lime-500']

export default function DashboardSnapshot() {
  const { token } = useParams<{ token: string }>()
  const navigate = useNavigate()
  const [data, setData] = useState<SnapshotData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  usePageTitle(data?.title || '看板快照')

  useEffect(() => {
    if (!token) return
    setLoading(true)
    dashboardApi.getSnapshot(token)
      .then((res: any) => setData(res.data))
      .catch((err: any) => {
        const msg = err?.response?.data?.message || '加载快照失败'
        setError(msg)
        message.error(msg)
      })
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return <div className="flex justify-center py-20"><Spin size="large" /></div>
  if (error || !data) {
    return (
      <div className="text-center py-20">
        <span className="material-symbols-outlined text-5xl text-slate-300 mb-4 block">link_off</span>
        <h2 className="text-lg font-bold text-slate-600 mb-2">{error || '快照不存在'}</h2>
        <button onClick={() => navigate('/')} className="text-primary text-sm font-bold hover:underline">返回工作台</button>
      </div>
    )
  }

  const { snapshot_data: snap } = data
  const stats = snap.stats || {}
  const funnel = snap.funnel || []
  const paymentOv = snap.paymentOv as any
  const leaderboard = snap.leaderboard || []
  const approvalStats = snap.approvalStats as any
  const funnelMax = Math.max(...funnel.map((f) => f.count), 1)

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="material-symbols-outlined text-primary text-xl">photo_camera</span>
            <h1 className="text-2xl font-extrabold text-slate-900">{data.title}</h1>
          </div>
          <p className="text-sm text-slate-500">
            由 <span className="font-semibold text-slate-700">{data.created_by_name}</span> 创建于{' '}
            {data.created_at ? new Date(data.created_at).toLocaleString('zh-CN') : ''}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2 py-1 bg-amber-50 text-amber-600 rounded text-xs font-bold border border-amber-100">
            只读快照
          </span>
          <button onClick={() => navigate('/')}
            className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold">
            返回工作台
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        {[
          { icon: 'business', label: '客户总数', value: stats.customer_total ?? 0 },
          { icon: 'trending_up', label: '线索总数', value: stats.lead_total ?? 0 },
          { icon: 'rocket_launch', label: '商机总数', value: stats.project_total ?? 0 },
          { icon: 'play_circle', label: '进行中商机', value: stats.active_projects ?? 0 },
          { icon: 'payments', label: '管线总额', value: stats.pipeline_value ? `¥${(Number(stats.pipeline_value) / 10000).toFixed(0)}万` : '¥0' },
          { icon: 'handshake', label: '合同/报价', value: `${stats.contract_total ?? 0}/${stats.quote_total ?? 0}` },
          { icon: 'confirmation_number', label: '售后工单', value: stats.ticket_total ?? 0 },
          { icon: 'receipt_long', label: '发票总数', value: stats.invoice_total ?? 0 },
        ].map((kpi) => (
          <div key={kpi.label} className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-primary text-lg">{kpi.icon}</span>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{kpi.label}</span>
            </div>
            <div className="text-2xl font-black text-slate-900">{kpi.value}</div>
          </div>
        ))}
      </div>

      {/* Funnel + Payment */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-blue-500">filter_alt</span>
            <h3 className="text-sm font-bold text-slate-900">销售漏斗</h3>
          </div>
          {funnel.length > 0 ? (
            <div className="space-y-2">
              {funnel.map((f, i) => (
                <div key={f.stage} className="flex items-center gap-3">
                  <span className="text-xs font-bold text-slate-500 w-8">{f.stage}</span>
                  <div className="flex-1 h-7 bg-slate-100 rounded-full overflow-hidden relative">
                    <div className={`h-full ${stageColors[i % stageColors.length]} rounded-full transition-all`}
                      style={{ width: `${Math.max((f.count / funnelMax) * 100, 4)}%` }} />
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-bold text-slate-600">
                      {f.count} · ¥{(f.amount / 10000).toFixed(0)}万
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center text-slate-400 text-sm py-8">暂无漏斗数据</div>
          )}
        </div>

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-emerald-500">account_balance</span>
            <h3 className="text-sm font-bold text-slate-900">回款概览</h3>
          </div>
          {paymentOv ? (
            <div className="grid grid-cols-2 gap-4">
              <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-100">
                <div className="text-xs text-emerald-600 font-bold mb-1">已回款</div>
                <div className="text-xl font-black text-emerald-700">¥{(paymentOv.total_received / 10000).toFixed(1)}万</div>
              </div>
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-100">
                <div className="text-xs text-blue-600 font-bold mb-1">计划总额</div>
                <div className="text-xl font-black text-blue-700">¥{(paymentOv.total_planned / 10000).toFixed(1)}万</div>
              </div>
              <div className="text-center p-2 rounded-lg bg-slate-50">
                <div className="text-lg font-black text-slate-900">{paymentOv.collection_rate}%</div>
                <div className="text-[10px] text-slate-500">回款率</div>
              </div>
              <div className="text-center p-2 rounded-lg bg-red-50">
                <div className="text-lg font-black text-red-600">{paymentOv.overdue_count}</div>
                <div className="text-[10px] text-slate-500">逾期笔数</div>
              </div>
            </div>
          ) : (
            <div className="text-center text-slate-400 text-sm py-8">暂无回款数据</div>
          )}
        </div>
      </div>

      {/* Approval SLA + Leaderboard */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {approvalStats && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="material-symbols-outlined text-indigo-500">verified</span>
              <h3 className="text-sm font-bold text-slate-900">审批SLA概览</h3>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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
              <div className="text-center p-3 rounded-lg bg-amber-50">
                <div className="text-2xl font-black text-amber-600">{Math.round(approvalStats.sla_compliance_rate * 100)}%</div>
                <div className="text-[10px] text-slate-500 font-bold">SLA达标率</div>
              </div>
            </div>
          </div>
        )}

        {leaderboard.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center gap-2 mb-4">
              <span className="material-symbols-outlined text-amber-500">emoji_events</span>
              <h3 className="text-sm font-bold text-slate-900">业绩排行</h3>
            </div>
            <div className="space-y-2">
              {leaderboard.slice(0, 5).map((l, i) => (
                <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-slate-50">
                  <span className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-black ${
                    i === 0 ? 'bg-amber-400 text-white' : i === 1 ? 'bg-slate-300 text-white' : i === 2 ? 'bg-amber-600 text-white' : 'bg-slate-100 text-slate-500'
                  }`}>{i + 1}</span>
                  <span className="flex-1 text-sm font-bold text-slate-800">{l.owner_name}</span>
                  <span className="text-sm font-bold text-emerald-600">{l.won_count}单</span>
                  <span className="text-xs text-slate-500">¥{(l.won_amount / 10000).toFixed(0)}万</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
