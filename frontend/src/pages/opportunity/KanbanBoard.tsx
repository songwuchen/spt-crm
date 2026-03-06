import { useState, useEffect, useRef, DragEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { message, Spin, Modal } from 'antd'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import type { OpportunityProject, Customer } from '@/api/types'
import { stageLabels, riskLabels } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'

const STAGES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']
const STAGE_COLORS: Record<string, { bg: string; border: string; text: string; headerBg: string }> = {
  S1: { bg: '#f8fafc', border: '#e2e8f0', text: '#475569', headerBg: '#f1f5f9' },
  S2: { bg: '#eff6ff', border: '#bfdbfe', text: '#1e40af', headerBg: '#dbeafe' },
  S3: { bg: '#eef2ff', border: '#c7d2fe', text: '#3730a3', headerBg: '#e0e7ff' },
  S4: { bg: '#fffbeb', border: '#fde68a', text: '#92400e', headerBg: '#fef3c7' },
  S5: { bg: '#ecfdf5', border: '#a7f3d0', text: '#065f46', headerBg: '#d1fae5' },
  S6: { bg: '#f0fdf4', border: '#86efac', text: '#166534', headerBg: '#bbf7d0' },
}

const statusDot: Record<string, string> = {
  active: '#3b82f6', won: '#10b981', lost: '#ef4444', suspended: '#94a3b8',
}

interface KanbanBoardProps {
  onSwitchView?: () => void
}

export default function KanbanBoard({ onSwitchView }: KanbanBoardProps) {
  usePageTitle('商机看板')
  const navigate = useNavigate()
  const switchToTable = onSwitchView || (() => navigate('/opportunities'))
  const [cards, setCards] = useState<OpportunityProject[]>([])
  const [loading, setLoading] = useState(true)
  const [customerMap, setCustomerMap] = useState<Record<string, string>>({})
  const [dragOverStage, setDragOverStage] = useState<string | null>(null)
  const dragCardRef = useRef<OpportunityProject | null>(null)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await projectApi.list({ pageNo: 1, pageSize: 100, status: 'active' })
      setCards(res.data.items)
      const ids = [...new Set(res.data.items.map((p) => p.customer_id).filter(Boolean))] as string[]
      if (ids.length > 0) {
        const custRes = await customerApi.list({ pageNo: 1, pageSize: 100 })
        const map: Record<string, string> = {}
        custRes.data.items.forEach((c: Customer) => { map[c.id] = c.name })
        setCustomerMap(map)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const grouped = STAGES.reduce<Record<string, OpportunityProject[]>>((acc, s) => {
    acc[s] = cards.filter((c) => c.stage_code === s)
    return acc
  }, {})

  const stageTotal = (stage: string) => {
    const items = grouped[stage] || []
    const sum = items.reduce((a, b) => a + (b.amount_expect || 0), 0)
    return { count: items.length, sum }
  }

  const handleDragStart = (e: DragEvent, card: OpportunityProject) => {
    dragCardRef.current = card
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', card.id)
  }

  const handleDragOver = (e: DragEvent, stage: string) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverStage(stage)
  }

  const handleDragLeave = () => { setDragOverStage(null) }

  const handleDrop = async (e: DragEvent, toStage: string) => {
    e.preventDefault()
    setDragOverStage(null)
    const card = dragCardRef.current
    if (!card || card.stage_code === toStage) return

    const fromIdx = STAGES.indexOf(card.stage_code)
    const toIdx = STAGES.indexOf(toStage)

    Modal.confirm({
      title: `阶段变更确认`,
      content: `将「${card.name}」从 ${card.stage_code} ${stageLabels[card.stage_code]} 移至 ${toStage} ${stageLabels[toStage]}？`,
      okText: '确认',
      cancelText: '取消',
      onOk: async () => {
        try {
          if (toIdx > fromIdx) {
            await projectApi.advance(card.id, { to_stage: toStage, note: '看板拖拽推进' })
          } else {
            await projectApi.rollback(card.id, { to_stage: toStage, note: '看板拖拽回退' })
          }
          message.success(`已移至 ${toStage} ${stageLabels[toStage]}`)
          fetchData()
        } catch (err: any) {
          if (err?.gateData) {
            const failedRules = err.gateData.failed_rules || []
            Modal.warning({
              title: 'Gate 规则校验未通过',
              content: (
                <div>
                  {failedRules.map((r: any, i: number) => (
                    <div key={i} className="mb-1">• {r.name || r.code}: {r.message || ''}</div>
                  ))}
                </div>
              ),
            })
          }
        }
      },
    })
  }

  if (loading) {
    return <DetailSkeleton />
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">商机看板</h1>
          <p className="text-sm text-slate-500 mt-0.5">拖拽卡片推进阶段</p>
        </div>
        <button onClick={switchToTable}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>table_rows</span>
            表格视图
          </button>
      </div>

      {/* Board */}
      <div className="flex gap-3 overflow-x-auto pb-4" style={{ minHeight: 'calc(100vh - 200px)' }}>
        {STAGES.map((stage) => {
          const color = STAGE_COLORS[stage]
          const { count, sum } = stageTotal(stage)
          const isDragOver = dragOverStage === stage
          return (
            <div
              key={stage}
              className="flex-shrink-0 flex flex-col rounded-xl border transition-all duration-200"
              style={{
                width: 280,
                background: isDragOver ? color.headerBg : color.bg,
                borderColor: isDragOver ? color.text : color.border,
                borderWidth: isDragOver ? 2 : 1,
              }}
              onDragOver={(e) => handleDragOver(e, stage)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, stage)}
            >
              {/* Column header */}
              <div className="px-3 py-3 rounded-t-xl" style={{ background: color.headerBg }}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-black uppercase tracking-wider" style={{ color: color.text }}>{stage}</span>
                    <span className="text-[11px] font-semibold" style={{ color: color.text }}>{stageLabels[stage]}</span>
                  </div>
                  <span className="inline-flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold text-white"
                    style={{ background: color.text }}>{count}</span>
                </div>
                <div className="text-[11px] font-medium" style={{ color: color.text, opacity: 0.7 }}>
                  {sum > 0 ? `¥${(sum / 10000).toFixed(1)}万` : '-'}
                </div>
              </div>

              {/* Cards */}
              <div className="flex-1 px-2 py-2 space-y-2 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 300px)' }}>
                {(grouped[stage] || []).map((card) => (
                  <div
                    key={card.id}
                    draggable
                    onDragStart={(e) => handleDragStart(e, card)}
                    onClick={() => navigate(`/opportunities/${card.id}`)}
                    className="bg-white rounded-lg border border-slate-200 p-3 cursor-grab hover:shadow-md hover:border-slate-300 transition-all duration-150 active:cursor-grabbing"
                  >
                    <div className="flex items-start justify-between mb-1.5">
                      <h3 className="text-[13px] font-bold text-slate-800 leading-tight line-clamp-2 flex-1">{card.name}</h3>
                      <span className="w-2 h-2 rounded-full flex-shrink-0 mt-1 ml-2" style={{ background: statusDot[card.status] || '#94a3b8' }} />
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono mb-2">{card.project_code}</div>
                    {card.customer_id && customerMap[card.customer_id] && (
                      <div className="text-[11px] text-slate-500 mb-1.5 flex items-center gap-1">
                        <span className="material-symbols-outlined" style={{ fontSize: 13 }}>business</span>
                        {customerMap[card.customer_id]}
                      </div>
                    )}
                    <div className="flex items-center justify-between">
                      <div className="text-[12px] font-bold text-slate-700">
                        {card.amount_expect != null ? `¥${Number(card.amount_expect).toLocaleString()}` : '-'}
                      </div>
                      <div className="flex items-center gap-2">
                        {card.probability != null && (
                          <span className="text-[10px] font-bold text-blue-500">{card.probability}%</span>
                        )}
                        {card.risk_level && (
                          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                            card.risk_level === 'H' ? 'bg-red-50 text-red-500' :
                            card.risk_level === 'M' ? 'bg-amber-50 text-amber-500' :
                            'bg-emerald-50 text-emerald-500'
                          }`}>{riskLabels[card.risk_level]}</span>
                        )}
                      </div>
                    </div>
                    {card.owner_name && (
                      <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] text-slate-400 flex items-center gap-1">
                        <span className="material-symbols-outlined" style={{ fontSize: 13 }}>person</span>
                        {card.owner_name}
                      </div>
                    )}
                  </div>
                ))}
                {(grouped[stage] || []).length === 0 && (
                  <div className="text-center py-8 text-slate-300 text-xs">暂无商机</div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
