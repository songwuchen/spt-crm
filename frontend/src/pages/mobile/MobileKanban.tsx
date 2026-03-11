import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { projectApi } from '@/api/project'
import { stageLabels } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

const STAGES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']
const stageColors: Record<string, string> = {
  S1: 'border-slate-300 bg-slate-50',
  S2: 'border-blue-300 bg-blue-50',
  S3: 'border-indigo-300 bg-indigo-50',
  S4: 'border-amber-300 bg-amber-50',
  S5: 'border-emerald-300 bg-emerald-50',
  S6: 'border-green-300 bg-green-50',
}

interface Card {
  id: string; name: string; stage_code: string; amount_expect?: number
  customer_name?: string; owner_name?: string; probability?: number
}

export default function MobileKanban() {
  usePageTitle('商机看板')
  const navigate = useNavigate()
  const [cards, setCards] = useState<Card[]>([])
  const [loading, setLoading] = useState(true)
  const [activeStage, setActiveStage] = useState('S1')

  useEffect(() => {
    projectApi.list({ pageNo: 1, pageSize: 100, status: 'active' })
      .then((r: any) => setCards(r.data?.items || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const grouped = STAGES.reduce<Record<string, Card[]>>((acc, s) => {
    acc[s] = cards.filter((c) => c.stage_code === s)
    return acc
  }, {} as Record<string, Card[]>)

  const stageCounts = STAGES.map(s => ({ stage: s, count: grouped[s]?.length || 0 }))

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100">
        <h1 className="text-lg font-bold text-slate-900">商机看板</h1>
      </div>

      {/* Stage Tabs */}
      <div className="bg-white px-2 py-2 border-b border-slate-100 flex gap-1 overflow-x-auto">
        {stageCounts.map(({ stage, count }) => (
          <button key={stage} onClick={() => setActiveStage(stage)}
            className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-bold transition-colors ${
              activeStage === stage ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
            }`}>
            {stage} ({count})
          </button>
        ))}
      </div>

      {/* Cards */}
      <div className="p-4 space-y-2 pb-20">
        {loading && <div className="text-center py-8 text-slate-400 text-sm">加载中...</div>}
        {!loading && (grouped[activeStage] || []).length === 0 && (
          <div className="text-center py-8 text-slate-400 text-sm">
            {activeStage} {stageLabels[activeStage]} 暂无商机
          </div>
        )}
        {(grouped[activeStage] || []).map((c) => (
          <div key={c.id} role="button" tabIndex={0} onClick={() => navigate(`/m/opportunities/${c.id}`)}
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); navigate(`/m/opportunities/${c.id}`) } }}
            className={`rounded-xl border-l-4 bg-white shadow-sm p-3 active:bg-slate-50 ${stageColors[c.stage_code] || 'border-slate-300'}`}>
            <div className="flex items-start justify-between mb-1">
              <span className="text-sm font-bold text-slate-800 flex-1 truncate">{c.name}</span>
              {c.amount_expect != null && (
                <span className="text-sm font-black text-slate-900 shrink-0 ml-2">
                  ¥{(Number(c.amount_expect) / 10000).toFixed(0)}万
                </span>
              )}
            </div>
            <div className="flex items-center gap-3 text-[10px] text-slate-400">
              {c.customer_name && <span>{c.customer_name}</span>}
              {c.owner_name && <span>{c.owner_name}</span>}
              {c.probability != null && <span>赢率 {c.probability}%</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
