import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { paymentApi } from '@/api/payment'
import { usePageTitle } from '@/hooks/usePageTitle'

interface PaymentPlan {
  id: string; plan_no: string; due_date: string; amount: number
  status: string; project_name?: string; remark?: string
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  pending: { label: '待收', color: 'text-blue-700', bg: 'bg-blue-50' },
  paid: { label: '已收', color: 'text-emerald-700', bg: 'bg-emerald-50' },
  overdue: { label: '逾期', color: 'text-red-600', bg: 'bg-red-50' },
}

export default function MobilePayments() {
  usePageTitle('回款管理')
  const navigate = useNavigate()
  const [plans, setPlans] = useState<PaymentPlan[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)

  useEffect(() => {
    paymentApi.listAllPlans({ pageNo: 1, pageSize: 50 })
      .then((r: any) => setPlans(r.data?.items || r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const filtered = filterStatus ? plans.filter(p => p.status === filterStatus) : plans
  const totalAmount = plans.reduce((s, p) => s + (p.amount || 0), 0)
  const paidAmount = plans.filter(p => p.status === 'paid').reduce((s, p) => s + (p.amount || 0), 0)

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <h1 className="text-lg font-extrabold text-slate-900">回款管理</h1>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 text-center">
          <div className="text-[10px] text-slate-400 font-bold">计划总额</div>
          <div className="text-lg font-black text-slate-900">¥{(totalAmount / 10000).toFixed(1)}万</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 text-center">
          <div className="text-[10px] text-slate-400 font-bold">已回款</div>
          <div className="text-lg font-black text-emerald-600">¥{(paidAmount / 10000).toFixed(1)}万</div>
        </div>
      </div>

      {/* Status filter */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        <button onClick={() => setFilterStatus(null)}
          className={`px-3 py-1 rounded-full text-sm font-bold whitespace-nowrap ${!filterStatus ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'}`}>
          全部 {plans.length}
        </button>
        {Object.entries(statusConfig).map(([key, sc]) => (
          <button key={key} onClick={() => setFilterStatus(filterStatus === key ? null : key)}
            className={`px-3 py-1 rounded-full text-sm font-bold whitespace-nowrap ${filterStatus === key ? 'bg-primary text-white' : `${sc.bg} ${sc.color}`}`}>
            {sc.label} {plans.filter(p => p.status === key).length}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">加载中...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">暂无回款计划</div>
      ) : (
        <div className="space-y-2">
          {filtered.map(p => {
            const sc = statusConfig[p.status] || statusConfig.pending
            const daysLeft = Math.ceil((new Date(p.due_date).getTime() - Date.now()) / 86400000)
            return (
              <div key={p.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-bold text-slate-900">{p.plan_no}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${sc.bg} ${sc.color}`}>{sc.label}</span>
                </div>
                <div className="text-lg font-black text-slate-900">¥{p.amount.toLocaleString()}</div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-[10px] text-slate-400">{p.project_name || '-'}</span>
                  <span className={`text-[10px] font-medium ${p.status !== 'paid' && daysLeft < 0 ? 'text-red-500' : 'text-slate-400'}`}>
                    {p.due_date}{p.status !== 'paid' && daysLeft < 0 ? ` (逾期${Math.abs(daysLeft)}天)` : ''}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
