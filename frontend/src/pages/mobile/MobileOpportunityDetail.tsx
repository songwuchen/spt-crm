import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { projectApi } from '@/api/project'
import { activityApi } from '@/api/activity'
import { stageLabels, stageColors } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useSwipe } from '@/hooks/useSwipe'

interface ProjectInfo {
  id: string; name: string; project_code: string; stage_code: string; status: string
  amount_expect?: number; probability?: number; risk_level?: string
  owner_name?: string; customer_name?: string; customer_id?: string
  created_at: string; expected_close_date?: string
  requirements_json?: { summary?: string }
  competitors_json?: string[]
}

interface Activity {
  id: string; interaction_type: string; summary: string; result?: string
  created_by_name?: string; created_at: string
}

const riskLabels: Record<string, { label: string; color: string }> = {
  low: { label: '低', color: 'text-emerald-600 bg-emerald-50' },
  medium: { label: '中', color: 'text-amber-600 bg-amber-50' },
  high: { label: '高', color: 'text-red-600 bg-red-50' },
}

const activityIcons: Record<string, string> = {
  call: 'call', visit: 'directions_walk', meeting: 'groups', email: 'email', other: 'note',
}

export default function MobileOpportunityDetail() {
  usePageTitle('商机详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<ProjectInfo | null>(null)
  const [activities, setActivities] = useState<Activity[]>([])
  const [tab, setTab] = useState<'info' | 'activities'>('info')
  // Hooks must run before any early return — calling useSwipe after the
  // `if (!project)` guard changes the hook count between renders (React #310).
  const swipeHandlers = useSwipe({ onSwipeRight: () => navigate(-1) })

  useEffect(() => {
    if (!id) return
    projectApi.get(id).then((r: any) => setProject(r.data)).catch(() => message.error('加载失败'))
    activityApi.list('project', id).then((r: any) => {
      setActivities(r.data || [])
    }).catch(() => {})
  }, [id])

  if (!project) return <div className="text-center py-12 text-slate-400">加载中...</div>

  const sc = stageColors[project.stage_code] || stageColors.S1
  const risk = riskLabels[project.risk_level || ''] || null

  return (
    <div {...swipeHandlers}>
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-extrabold text-slate-900 truncate">{project.name}</h1>
          <span className="text-[10px] font-mono text-slate-400">{project.project_code}</span>
        </div>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${sc}`}>
          {project.stage_code} {stageLabels[project.stage_code]}
        </span>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-gradient-to-br from-primary/10 to-blue-50 rounded-xl p-3 text-center border border-primary/10">
          <div className="text-lg font-black text-slate-900">
            {project.amount_expect != null ? `¥${(Number(project.amount_expect) / 10000).toFixed(0)}万` : '-'}
          </div>
          <div className="text-[10px] text-slate-500 font-bold">预期金额</div>
        </div>
        <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl p-3 text-center border border-emerald-100">
          <div className="text-lg font-black text-emerald-600">{project.probability || 0}%</div>
          <div className="text-[10px] text-slate-500 font-bold">赢率</div>
        </div>
        <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-3 text-center border border-amber-100">
          <div className="text-lg font-black text-amber-600">{risk ? risk.label : '-'}</div>
          <div className="text-[10px] text-slate-500 font-bold">风险</div>
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-1 mb-4 bg-slate-100 rounded-lg p-1">
        {(['info', 'activities'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 rounded-md text-sm font-bold transition-colors ${tab === t ? 'bg-white text-primary shadow-sm' : 'text-slate-500'}`}>
            {t === 'info' ? '基本信息' : '互动记录'}
          </button>
        ))}
      </div>

      {tab === 'info' && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 space-y-3">
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">状态</span>
            <span className="text-sm text-slate-700">
              {project.status === 'active' ? '进行中' : project.status === 'won' ? '赢单' : project.status === 'lost' ? '丢单' : '暂停'}
            </span>
          </div>
          {project.customer_name && (
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">客户</span>
              <span className="text-sm font-bold text-slate-800">{project.customer_name}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">负责人</span>
            <span className="text-sm text-slate-700">{project.owner_name || '-'}</span>
          </div>
          {project.expected_close_date && (
            <div className="flex justify-between">
              <span className="text-sm text-slate-400">预计关单</span>
              <span className="text-sm text-slate-700">{project.expected_close_date}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">创建时间</span>
            <span className="text-sm text-slate-500">{project.created_at ? new Date(project.created_at).toLocaleDateString('zh-CN') : '-'}</span>
          </div>
          {project.competitors_json && project.competitors_json.length > 0 && (
            <div>
              <span className="text-sm text-slate-400 block mb-1">竞争对手</span>
              <div className="flex flex-wrap gap-1">
                {project.competitors_json.map((c, i) => (
                  <span key={i} className="px-2 py-0.5 bg-red-50 text-red-600 rounded text-[10px] font-bold">{c}</span>
                ))}
              </div>
            </div>
          )}
          {project.requirements_json?.summary && (
            <div>
              <span className="text-sm text-slate-400 block mb-1">需求摘要</span>
              <p className="text-sm text-slate-700 whitespace-pre-wrap">{project.requirements_json.summary}</p>
            </div>
          )}
        </div>
      )}

      {tab === 'activities' && (
        <div>
          {activities.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">暂无互动记录</div>
          ) : (
            <div className="space-y-2">
              {activities.map((a) => (
                <div key={a.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="material-symbols-outlined text-slate-400" style={{ fontSize: 16 }}>
                      {activityIcons[a.interaction_type] || 'note'}
                    </span>
                    <span className="text-sm font-bold text-slate-800 flex-1 truncate">{a.summary}</span>
                    {a.result && (
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                        a.result === 'progress' ? 'bg-emerald-50 text-emerald-600' :
                        a.result === 'risk' ? 'bg-red-50 text-red-600' : 'bg-amber-50 text-amber-600'
                      }`}>{a.result === 'progress' ? '进展' : a.result === 'risk' ? '风险' : '停滞'}</span>
                    )}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {a.created_by_name || ''} &middot; {a.created_at ? new Date(a.created_at).toLocaleDateString('zh-CN') : ''}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="fixed bottom-20 left-0 right-0 px-4 pb-2">
        <div className="flex gap-2">
          <button onClick={() => navigate(`/m/opportunities/${id}/risk`)}
            className="flex-1 py-2.5 bg-white border border-slate-200 rounded-lg text-sm font-bold text-slate-600 shadow-sm">
            风险评估
          </button>
          <button onClick={() => navigate('/m/follow-up/new')}
            className="flex-1 py-2.5 bg-primary text-white rounded-lg text-sm font-bold shadow-sm">
            写跟进
          </button>
        </div>
      </div>
    </div>
  )
}
