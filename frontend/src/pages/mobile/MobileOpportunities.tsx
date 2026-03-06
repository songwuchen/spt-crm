import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Spin } from 'antd'
import { projectApi } from '@/api/project'
import type { OpportunityProject } from '@/api/types'
import { stageLabels, stageColors } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'

const STAGES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']

export default function MobileOpportunities() {
  usePageTitle('商机')
  const [projects, setProjects] = useState<OpportunityProject[]>([])
  const [loading, setLoading] = useState(false)
  const [activeStage, setActiveStage] = useState<string | null>(null)
  const navigate = useNavigate()

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await projectApi.list({ pageNo: 1, pageSize: 100, status: 'active' })
      setProjects(res.data.items)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const filtered = activeStage ? projects.filter((p) => p.stage_code === activeStage) : projects

  // Group by stage for kanban display
  const groupedByStage = STAGES.map((stage) => ({
    stage,
    label: stageLabels[stage],
    items: projects.filter((p) => p.stage_code === stage),
  }))

  return (
    <div>
      <h1 className="text-lg font-extrabold text-slate-900 mb-3">商机看板</h1>

      {/* Stage Pills */}
      <div className="flex gap-2 overflow-x-auto mb-3 pb-1" style={{ scrollbarWidth: 'none' }}>
        <button
          onClick={() => setActiveStage(null)}
          className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-bold border-0 cursor-pointer transition-colors ${
            !activeStage ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
          }`}
        >
          全部 ({projects.length})
        </button>
        {STAGES.map((s) => {
          const count = projects.filter((p) => p.stage_code === s).length
          return (
            <button
              key={s}
              onClick={() => setActiveStage(activeStage === s ? null : s)}
              className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-bold border-0 cursor-pointer transition-colors ${
                activeStage === s ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {stageLabels[s]} ({count})
            </button>
          )
        })}
      </div>

      {/* Card List or Kanban */}
      {loading ? (
        <div className="flex justify-center mt-10"><Spin /></div>
      ) : activeStage !== null ? (
        // Filtered list view
        <div className="space-y-2">
          {filtered.map((p) => (
            <div
              key={p.id}
              onClick={() => navigate(`/m/opportunities/${p.id}`)}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 active:bg-slate-50 cursor-pointer"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-slate-900 truncate flex-1">{p.name}</span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${stageColors[p.stage_code]}`}>
                  {stageLabels[p.stage_code]}
                </span>
              </div>
              <div className="flex items-center gap-3 text-xs text-slate-500">
                {p.amount_expect && <span>¥{Number(p.amount_expect).toLocaleString()}</span>}
                {p.owner_name && <span>{p.owner_name}</span>}
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <div className="text-center text-sm text-slate-400 py-10">暂无商机</div>
          )}
        </div>
      ) : (
        // Kanban horizontal scroll
        <div className="flex gap-3 overflow-x-auto pb-2" style={{ scrollbarWidth: 'none' }}>
          {groupedByStage.map((g) => (
            <div key={g.stage} className="shrink-0 w-60">
              <div className={`px-3 py-1.5 rounded-t-lg text-xs font-bold border ${stageColors[g.stage]}`}>
                {g.label} <span className="ml-1 opacity-60">({g.items.length})</span>
              </div>
              <div className="bg-slate-50 rounded-b-lg border border-t-0 border-slate-200 p-2 space-y-2 min-h-[200px]">
                {g.items.map((p) => (
                  <div
                    key={p.id}
                    onClick={() => navigate(`/m/opportunities/${p.id}`)}
                    className="bg-white rounded-lg border border-slate-100 p-2.5 shadow-sm active:bg-slate-50 cursor-pointer"
                  >
                    <div className="text-xs font-bold text-slate-800 truncate mb-1">{p.name}</div>
                    <div className="flex items-center justify-between text-[10px] text-slate-500">
                      <span>{p.amount_expect ? `¥${Number(p.amount_expect).toLocaleString()}` : '-'}</span>
                      <span>{p.owner_name || '-'}</span>
                    </div>
                  </div>
                ))}
                {g.items.length === 0 && (
                  <div className="text-center text-[10px] text-slate-300 py-6">空</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
