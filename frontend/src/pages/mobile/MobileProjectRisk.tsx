import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { aiApi } from '@/api/ai'
import { projectApi } from '@/api/project'
import { taskApi } from '@/api/task'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { OpportunityProject } from '@/api/types'

interface RiskItem {
  title: string
  description: string
  severity: 'H' | 'M' | 'L'
  type?: string
  evidence_link?: string
}

interface ActionItem {
  text: string
  priority?: number
}

const severityBadge: Record<string, { bg: string; text: string; label: string }> = {
  H: { bg: 'bg-red-100', text: 'text-red-700', label: 'Critical' },
  M: { bg: 'bg-orange-100', text: 'text-orange-700', label: 'Warning' },
  L: { bg: 'bg-emerald-100', text: 'text-emerald-700', label: 'Low' },
}

const riskIcon: Record<string, string> = {
  H: 'warning',
  M: 'schedule',
  L: 'info',
}

export default function MobileProjectRisk() {
  usePageTitle('AI 风险分析')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [project, setProject] = useState<OpportunityProject | null>(null)
  const [risks, setRisks] = useState<RiskItem[]>([])
  const [actions, setActions] = useState<ActionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [analyzing, setAnalyzing] = useState(false)

  useEffect(() => {
    if (!id) return
    projectApi.get(id).then((res) => {
      if (res.data) setProject(res.data)
    }).catch(() => {})

    loadRiskData()
  }, [id])

  const loadRiskData = async () => {
    if (!id) return
    setLoading(true)
    try {
      const res = await aiApi.listTasks({ biz_type: 'project', biz_id: id })
      const tasks = res.data || []
      const riskTask = tasks.find((t: any) => t.task_type === 'quote_risk' || t.task_type === 'next_action' || t.status === 'done')
      if (riskTask?.result?.result_json) {
        const rj = riskTask.result.result_json as any
        setRisks(rj.risks || rj.risk_items || [])
        setActions(rj.actions || rj.next_actions || rj.suggestions || [])
      }
    } catch { /* empty */ }
    finally { setLoading(false) }
  }

  const handleAnalyze = async () => {
    if (!id) return
    setAnalyzing(true)
    try {
      const res = await aiApi.analyze({ biz_type: 'project', biz_id: id, analysis_type: 'risk' })
      if (res.data?.result) {
        const r = res.data.result as any
        setRisks(r.risks || r.risk_items || [])
        setActions(r.actions || r.next_actions || r.suggestions || [])
      }
    } catch { message.error('分析失败') }
    finally { setAnalyzing(false) }
  }

  const [creatingIdx, setCreatingIdx] = useState<number | null>(null)

  const handleCreateTask = async (actionText: string, idx: number) => {
    if (!id) return
    setCreatingIdx(idx)
    try {
      await taskApi.create({
        title: actionText,
        biz_type: 'project',
        biz_id: id,
        biz_name: project?.name,
        priority: 'high',
      })
      message.success('任务已创建')
    } catch {
      message.error('创建任务失败')
    } finally {
      setCreatingIdx(null)
    }
  }

  const highCount = risks.filter(r => r.severity === 'H').length
  const medCount = risks.filter(r => r.severity === 'M').length
  const lowCount = risks.filter(r => r.severity === 'L').length

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="material-symbols-outlined animate-spin text-primary" style={{ fontSize: 32 }}>progress_activity</span>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => navigate(-1)} className="flex items-center text-slate-900 bg-transparent border-0 cursor-pointer p-0">
          <span className="material-symbols-outlined">arrow_back</span>
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center truncate px-2">
          {project?.name || 'AI 风险分析'}
        </h2>
        <button
          onClick={handleAnalyze}
          disabled={analyzing}
          className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0 disabled:opacity-50"
        >
          <span className={`material-symbols-outlined ${analyzing ? 'animate-spin' : ''}`} style={{ fontSize: 22 }}>
            {analyzing ? 'progress_activity' : 'refresh'}
          </span>
        </button>
      </div>

      {/* Risk Dashboard */}
      <div className="mb-5">
        <h3 className="text-base font-bold text-slate-900 mb-3">风险仪表盘</h3>
        <div className="grid grid-cols-3 gap-3">
          <div className="bg-red-50 border border-red-100 rounded-xl p-4 flex flex-col items-center">
            <span className="text-red-600 text-2xl font-bold">{String(highCount).padStart(2, '0')}</span>
            <span className="text-red-500 text-[10px] font-bold uppercase tracking-wider">高风险</span>
          </div>
          <div className="bg-orange-50 border border-orange-100 rounded-xl p-4 flex flex-col items-center">
            <span className="text-orange-600 text-2xl font-bold">{String(medCount).padStart(2, '0')}</span>
            <span className="text-orange-500 text-[10px] font-bold uppercase tracking-wider">中风险</span>
          </div>
          <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4 flex flex-col items-center">
            <span className="text-emerald-600 text-2xl font-bold">{String(lowCount).padStart(2, '0')}</span>
            <span className="text-emerald-500 text-[10px] font-bold uppercase tracking-wider">低风险</span>
          </div>
        </div>
      </div>

      {/* Risk Cards */}
      {risks.length > 0 ? (
        <div className="space-y-3 mb-6">
          {risks.map((risk, i) => {
            const badge = severityBadge[risk.severity] || severityBadge.M
            const icon = riskIcon[risk.severity] || 'info'
            return (
              <div key={i} className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
                <div className="flex justify-between items-start mb-2">
                  <div className="flex items-center gap-2">
                    <span className={`material-symbols-outlined ${
                      risk.severity === 'H' ? 'text-red-500' :
                      risk.severity === 'M' ? 'text-orange-500' : 'text-emerald-500'
                    }`} style={{ fontSize: 18 }}>{icon}</span>
                    <h4 className="font-bold text-slate-900 text-sm">{risk.title}</h4>
                  </div>
                  <span className={`${badge.bg} ${badge.text} text-[10px] px-2 py-0.5 rounded-full font-bold uppercase`}>
                    {badge.label}
                  </span>
                </div>
                <p className="text-sm text-slate-600 leading-relaxed">{risk.description}</p>
                {risk.evidence_link && (
                  <a className="flex items-center text-primary text-xs font-bold gap-1 mt-2 cursor-pointer"
                    onClick={(e) => { e.preventDefault(); navigate(risk.evidence_link!) }}>
                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>link</span>
                    查看证据
                  </a>
                )}
              </div>
            )
          })}
        </div>
      ) : (
        <div className="text-center py-8 text-slate-400 text-sm mb-6">
          暂无风险数据，点击右上角刷新按钮进行 AI 分析
        </div>
      )}

      {/* AI Next Actions */}
      {actions.length > 0 && (
        <div className="bg-primary/5 border border-primary/20 rounded-2xl p-5 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>auto_awesome</span>
            <h3 className="text-slate-900 font-bold text-sm">AI 建议下一步行动</h3>
          </div>
          <div className="space-y-3">
            {actions.map((action, i) => (
              <div key={i}>
                {i > 0 && <div className="w-full h-px bg-primary/10 mb-3" />}
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-slate-700">{i + 1}. {typeof action === 'string' ? action : action.text}</p>
                  <button
                    disabled={creatingIdx === i}
                    onClick={() => handleCreateTask(typeof action === 'string' ? action : action.text, i)}
                    className="bg-primary text-white text-xs font-bold px-3 py-2 rounded-lg shrink-0 border-0 cursor-pointer active:scale-95 transition-transform disabled:opacity-50"
                  >
                    {creatingIdx === i ? '创建中...' : '创建任务'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
