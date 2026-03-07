import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { contractApi } from '@/api/contract'
import { usePageTitle } from '@/hooks/usePageTitle'

interface ContractBrief {
  id: string; contract_no: string; status: string
  amount_total?: number; signed_date?: string; end_date?: string
  project_name?: string; created_by_name?: string
}

const statusConfig: Record<string, { label: string; color: string }> = {
  draft: { label: '草稿', color: 'bg-slate-100 text-slate-600' },
  signed: { label: '已签署', color: 'bg-emerald-50 text-emerald-700' },
  terminated: { label: '已终止', color: 'bg-red-50 text-red-600' },
}

export default function MobileContracts() {
  usePageTitle('合同列表')
  const navigate = useNavigate()
  const [contracts, setContracts] = useState<ContractBrief[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    contractApi.list({ pageNo: 1, pageSize: 50 })
      .then((r: any) => setContracts(r.data?.items || r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <h1 className="text-lg font-extrabold text-slate-900">合同列表</h1>
        <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-bold">{contracts.length}</span>
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">加载中...</div>
      ) : contracts.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">暂无合同</div>
      ) : (
        <div className="space-y-2">
          {contracts.map((c) => {
            const sc = statusConfig[c.status] || statusConfig.draft
            const daysLeft = c.end_date ? Math.ceil((new Date(c.end_date).getTime() - Date.now()) / 86400000) : null
            return (
              <div key={c.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-slate-900">{c.contract_no}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${sc.color}`}>{sc.label}</span>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    {c.amount_total != null && (
                      <div className="text-lg font-black text-slate-900">¥{(c.amount_total / 10000).toFixed(1)}万</div>
                    )}
                    <div className="text-[10px] text-slate-400 mt-0.5">
                      {c.signed_date && <span>签署: {c.signed_date}</span>}
                      {c.created_by_name && <span className="ml-2">{c.created_by_name}</span>}
                    </div>
                  </div>
                  {daysLeft !== null && c.status === 'signed' && (
                    <div className={`text-right ${daysLeft < 0 ? 'text-red-600' : daysLeft <= 30 ? 'text-amber-600' : 'text-slate-500'}`}>
                      <div className="text-xs font-bold">
                        {daysLeft < 0 ? `已过期${Math.abs(daysLeft)}天` : `${daysLeft}天后到期`}
                      </div>
                      <div className="text-[10px]">{c.end_date}</div>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
