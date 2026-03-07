import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { contractApi } from '@/api/contract'
import { usePageTitle } from '@/hooks/usePageTitle'

interface ContractBrief {
  id: string; contract_no: string; status: string
  amount_total?: number; signed_date?: string; end_date?: string
  project_name?: string; created_by_name?: string
  start_date?: string; title?: string
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: '草稿', color: 'text-slate-600', bg: 'bg-slate-100' },
  pending: { label: '待审批', color: 'text-amber-700', bg: 'bg-amber-50' },
  signed: { label: '已签署', color: 'text-emerald-700', bg: 'bg-emerald-50' },
  terminated: { label: '已终止', color: 'text-red-600', bg: 'bg-red-50' },
}

export default function MobileContracts() {
  usePageTitle('合同列表')
  const navigate = useNavigate()
  const [contracts, setContracts] = useState<ContractBrief[]>([])
  const [loading, setLoading] = useState(true)
  const [detail, setDetail] = useState<ContractBrief | null>(null)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)

  useEffect(() => {
    contractApi.list({ pageNo: 1, pageSize: 50 })
      .then((r: any) => setContracts(r.data?.items || r.data || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const filtered = filterStatus ? contracts.filter(c => c.status === filterStatus) : contracts
  const statusCounts = contracts.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] || 0) + 1; return acc
  }, {})

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <h1 className="text-lg font-extrabold text-slate-900">合同列表</h1>
        <span className="px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-bold">{contracts.length}</span>
      </div>

      {/* Status filter bar */}
      <div className="flex gap-2 mb-4 overflow-x-auto pb-1">
        <button onClick={() => setFilterStatus(null)}
          className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-colors ${
            !filterStatus ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
          }`}>全部 {contracts.length}</button>
        {Object.entries(statusConfig).map(([key, sc]) => (
          <button key={key} onClick={() => setFilterStatus(filterStatus === key ? null : key)}
            className={`px-3 py-1 rounded-full text-xs font-bold whitespace-nowrap transition-colors ${
              filterStatus === key ? 'bg-primary text-white' : `${sc.bg} ${sc.color}`
            }`}>{sc.label} {statusCounts[key] || 0}</button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-12 text-slate-400">加载中...</div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-12 text-slate-400 text-sm">暂无合同</div>
      ) : (
        <div className="space-y-2">
          {filtered.map((c) => {
            const sc = statusConfig[c.status] || statusConfig.draft
            const daysLeft = c.end_date ? Math.ceil((new Date(c.end_date).getTime() - Date.now()) / 86400000) : null
            return (
              <div key={c.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer active:bg-slate-50"
                onClick={() => setDetail(c)}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-bold text-slate-900">{c.contract_no}</span>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${sc.bg} ${sc.color}`}>{sc.label}</span>
                </div>
                {c.title && <div className="text-xs text-slate-600 mb-1">{c.title}</div>}
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

      {/* Detail Drawer */}
      {detail && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-end justify-center" onClick={() => setDetail(null)}>
          <div className="bg-white w-full max-w-lg rounded-t-2xl p-6 pb-8 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-5">
              <h3 className="text-lg font-extrabold text-slate-900">{detail.contract_no}</h3>
              <button onClick={() => setDetail(null)} className="text-slate-400">
                <span className="material-symbols-outlined" style={{ fontSize: 22 }}>close</span>
              </button>
            </div>

            {/* Status timeline */}
            <div className="flex items-center gap-1 mb-5">
              {['draft', 'pending', 'signed'].map((step, i) => {
                const steps = ['draft', 'pending', 'signed']
                const currentIdx = steps.indexOf(detail.status)
                const isActive = i <= currentIdx
                const sc = statusConfig[step]
                return (
                  <div key={step} className="flex items-center gap-1 flex-1">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold ${
                      isActive ? 'bg-primary text-white' : 'bg-slate-100 text-slate-400'
                    }`}>{i + 1}</div>
                    <span className={`text-[10px] font-medium ${isActive ? 'text-slate-800' : 'text-slate-400'}`}>{sc.label}</span>
                    {i < 2 && <div className={`flex-1 h-0.5 ${isActive && i < currentIdx ? 'bg-primary' : 'bg-slate-100'}`} />}
                  </div>
                )
              })}
            </div>

            {/* Details */}
            <div className="space-y-3">
              {detail.title && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">标题</span>
                  <span className="font-medium text-slate-800">{detail.title}</span>
                </div>
              )}
              {detail.amount_total != null && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">合同金额</span>
                  <span className="font-bold text-slate-900">¥{detail.amount_total.toLocaleString()}</span>
                </div>
              )}
              {detail.project_name && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">关联项目</span>
                  <span className="font-medium text-slate-800">{detail.project_name}</span>
                </div>
              )}
              {detail.signed_date && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">签署日期</span>
                  <span className="text-slate-800">{detail.signed_date}</span>
                </div>
              )}
              {detail.start_date && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">开始日期</span>
                  <span className="text-slate-800">{detail.start_date}</span>
                </div>
              )}
              {detail.end_date && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">结束日期</span>
                  <span className="text-slate-800">{detail.end_date}</span>
                </div>
              )}
              {detail.created_by_name && (
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">创建人</span>
                  <span className="text-slate-800">{detail.created_by_name}</span>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="mt-6 flex gap-3">
              <button onClick={() => { setDetail(null); navigate(`/opportunities`) }}
                className="flex-1 bg-primary/10 text-primary font-bold text-sm py-2.5 rounded-lg active:opacity-80">
                查看商机
              </button>
              <button onClick={() => setDetail(null)}
                className="flex-1 bg-slate-100 text-slate-600 font-bold text-sm py-2.5 rounded-lg active:opacity-80">
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
