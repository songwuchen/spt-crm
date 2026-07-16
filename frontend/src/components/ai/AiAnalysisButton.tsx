// 详情页一键 AI 分析按钮 + 结构化结果卡片。业务详情页放一个 <AiAnalysisButton .../> 即可。
import { useState } from 'react'
import { Button, Modal, Tag, Spin, Segmented, Empty, message } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { aiApi } from '@/api/ai'
import DataView from '@/components/DataView'

type BizType = 'project' | 'customer' | 'quote_version' | 'contract_version' | 'contract'

const ANALYSES: Record<BizType, { type: string; label: string }[]> = {
  project: [
    { type: 'risk', label: '风险评估' },
    { type: 'win_probability', label: '赢率预测' },
    { type: 'next_actions', label: '下一步建议' },
    { type: 'sales_script', label: '销售话术' },
  ],
  customer: [
    { type: 'profile', label: '客户画像' },
    { type: 'sales_script', label: '销售话术' },
  ],
  quote_version: [{ type: 'quote_review', label: '报价审核' }],
  contract_version: [{ type: 'contract_review', label: '合同审核' }],
  contract: [{ type: 'receivable', label: '应收账款分析' }],
}

const riskColor = (v?: string) => (v === 'H' ? 'error' : v === 'M' ? 'warning' : v === 'L' ? 'success' : 'default')
const riskLabel = (v?: string) => (v === 'H' ? '高' : v === 'M' ? '中' : v === 'L' ? '低' : v || '-')

interface UsageInfo { model?: string; token_in?: number; token_out?: number; cost_est?: number }

function ResultView({ type, result }: { type: string; result: Record<string, unknown> }) {
  const r = result || {}
  const List = ({ items }: { items?: unknown[] }) =>
    Array.isArray(items) && items.length ? (
      <ul className="list-disc pl-5 space-y-1 text-sm text-slate-700">{items.map((x, i) => <li key={i}>{String(x)}</li>)}</ul>
    ) : <span className="text-slate-400 text-sm">—</span>

  // 风险类：risk / quote_review / contract_review
  if (type === 'risk' || type === 'quote_review' || type === 'contract_review') {
    const rows = (r.risks || r.review_items || r.clauses || []) as Record<string, unknown>[]
    const comment = (r.overall_assessment || r.overall_comment) as string | undefined
    return (
      <div className="space-y-3">
        {r.risk_level != null && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-500">风险等级</span>
            <Tag color={riskColor(r.risk_level as string)}>{riskLabel(r.risk_level as string)}</Tag>
          </div>
        )}
        <div className="space-y-2">
          {Array.isArray(rows) && rows.map((it, i) => {
            const sev = (it.severity || it.risk || it.status) as string | undefined
            const title = (it.category || it.item || it.clause || `项 ${i + 1}`) as string
            const detail = (it.description || it.detail) as string | undefined
            const sevTag = it.status
              ? <Tag color={it.status === 'pass' ? 'success' : it.status === 'warning' ? 'warning' : 'error'}>{String(it.status)}</Tag>
              : <Tag color={riskColor(sev)}>{riskLabel(sev)}</Tag>
            return (
              <div key={i} className="border border-slate-100 rounded-lg p-3 bg-slate-50/60">
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-sm text-slate-800">{title}</span>
                  {sevTag}
                </div>
                {detail && <p className="text-sm text-slate-600">{detail}</p>}
                {typeof it.mitigation === 'string' && <p className="text-xs text-emerald-600 mt-1">应对：{it.mitigation}</p>}
              </div>
            )
          })}
        </div>
        {comment && <div className="text-sm text-slate-700 bg-indigo-50/60 rounded-lg p-3">{comment}</div>}
      </div>
    )
  }

  // 赢率
  if (type === 'win_probability') {
    const p = Number(r.win_probability ?? 0)
    const f = (r.factors || {}) as Record<string, unknown>
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <div className="text-4xl font-black text-primary">{p}%</div>
          <div className="text-sm text-slate-500">预测赢率</div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><div className="text-xs font-bold text-emerald-600 mb-1">有利因素</div><List items={f.positive as unknown[]} /></div>
          <div><div className="text-xs font-bold text-rose-500 mb-1">不利因素</div><List items={f.negative as unknown[]} /></div>
        </div>
        {typeof r.recommendation === 'string' && <div className="text-sm text-slate-700 bg-indigo-50/60 rounded-lg p-3">{r.recommendation}</div>}
      </div>
    )
  }

  // 客户画像
  if (type === 'profile') {
    const Field = ({ label, val }: { label: string; val?: unknown }) =>
      val ? <div><div className="text-xs font-bold text-slate-400 mb-0.5">{label}</div>
        {Array.isArray(val) ? <List items={val} /> : <p className="text-sm text-slate-700">{String(val)}</p>}</div> : null
    return (
      <div className="space-y-3">
        <Field label="行业定位" val={r.industry_position} />
        <Field label="决策模式" val={r.decision_pattern} />
        <Field label="痛点" val={r.pain_points} />
        <Field label="机会" val={r.opportunities} />
        <Field label="切入建议" val={r.recommended_approach} />
      </div>
    )
  }

  // 下一步建议
  if (type === 'next_actions') {
    const acts = (r.next_actions || []) as Record<string, unknown>[]
    return (
      <div className="space-y-2">
        {Array.isArray(acts) && acts.map((a, i) => (
          <div key={i} className="flex items-start gap-2 border border-slate-100 rounded-lg p-3">
            <Tag color={riskColor(a.priority as string)}>{riskLabel(a.priority as string)}</Tag>
            <div className="flex-1">
              <div className="text-sm font-semibold text-slate-800">{String(a.action || '')}</div>
              <div className="text-xs text-slate-400 mt-0.5">
                {a.deadline ? `期限：${a.deadline}` : ''}{a.owner ? ` · 负责人：${a.owner}` : ''}
              </div>
            </div>
          </div>
        ))}
        {typeof r.stage_suggestion === 'string' && <div className="text-sm text-slate-700 bg-indigo-50/60 rounded-lg p-3">{r.stage_suggestion}</div>}
      </div>
    )
  }

  // 应收账款分析
  if (type === 'receivable') {
    const acts = (r.collection_actions || []) as Record<string, unknown>[]
    return (
      <div className="space-y-3">
        {r.risk_level != null && (
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-500">回款风险</span>
            <Tag color={riskColor(r.risk_level as string)}>{riskLabel(r.risk_level as string)}</Tag>
          </div>
        )}
        {typeof r.overdue_summary === 'string' && (
          <div><div className="text-xs font-bold text-slate-400 mb-0.5">逾期状况</div>
            <p className="text-sm text-slate-700">{r.overdue_summary}</p></div>
        )}
        {Array.isArray(acts) && acts.length > 0 && (
          <div>
            <div className="text-xs font-bold text-slate-400 mb-1">催收动作</div>
            <div className="space-y-2">
              {acts.map((a, i) => (
                <div key={i} className="flex items-start gap-2 border border-slate-100 rounded-lg p-3">
                  <Tag color={riskColor(a.priority as string)}>{riskLabel(a.priority as string)}</Tag>
                  <div className="flex-1">
                    <div className="text-sm font-semibold text-slate-800">{String(a.action || '')}</div>
                    {a.deadline ? <div className="text-xs text-slate-400 mt-0.5">期限：{String(a.deadline)}</div> : null}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
        {typeof r.cash_flow_comment === 'string' && (
          <div className="text-sm text-amber-700 bg-amber-50/70 rounded-lg p-3">💰 {r.cash_flow_comment}</div>
        )}
        {typeof r.overall_comment === 'string' && (
          <div className="text-sm text-slate-700 bg-indigo-50/60 rounded-lg p-3">{r.overall_comment}</div>
        )}
      </div>
    )
  }

  // 销售话术推荐
  if (type === 'sales_script') {
    const obj = (r.objection_handling || []) as Record<string, unknown>[]
    return (
      <div className="space-y-3">
        {typeof r.opening === 'string' && (
          <div><div className="text-xs font-bold text-slate-400 mb-0.5">开场白</div>
            <div className="text-sm text-slate-700 bg-slate-50 rounded-lg p-3 border-l-2 border-indigo-300">{r.opening}</div></div>
        )}
        <div><div className="text-xs font-bold text-slate-400 mb-0.5">核心价值主张</div><List items={r.value_props as unknown[]} /></div>
        <div><div className="text-xs font-bold text-slate-400 mb-0.5">挖掘需求提问</div><List items={r.discovery_questions as unknown[]} /></div>
        {Array.isArray(obj) && obj.length > 0 && (
          <div>
            <div className="text-xs font-bold text-slate-400 mb-1">异议应对</div>
            <div className="space-y-2">
              {obj.map((o, i) => (
                <div key={i} className="border border-slate-100 rounded-lg p-3">
                  <div className="text-sm font-semibold text-rose-500">❓ {String(o.objection || '')}</div>
                  <div className="text-sm text-slate-700 mt-1">💬 {String(o.response || '')}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        {typeof r.closing === 'string' && (
          <div><div className="text-xs font-bold text-slate-400 mb-0.5">促成话术</div>
            <div className="text-sm text-slate-700 bg-emerald-50/70 rounded-lg p-3 border-l-2 border-emerald-300">{r.closing}</div></div>
        )}
        {Array.isArray(r.tips) && (r.tips as unknown[]).length > 0 && (
          <div><div className="text-xs font-bold text-slate-400 mb-0.5">实战提示</div><List items={r.tips as unknown[]} /></div>
        )}
      </div>
    )
  }

  // 兜底
  return <DataView value={r} />
}

export default function AiAnalysisButton({
  bizType, bizId, size = 'middle', type = 'default',
}: {
  bizType: BizType
  bizId: string
  size?: 'small' | 'middle' | 'large'
  type?: 'default' | 'primary' | 'link'
}) {
  const [open, setOpen] = useState(false)
  const options = ANALYSES[bizType] || []
  const [active, setActive] = useState(options[0]?.type)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<Record<string, unknown> | null>(null)
  const [usage, setUsage] = useState<UsageInfo | null>(null)

  const run = async (analysisType: string) => {
    setActive(analysisType)
    setLoading(true)
    setResult(null)
    try {
      const res = await aiApi.analyze({ biz_type: bizType, biz_id: bizId, analysis_type: analysisType }) as
        { data: { result: Record<string, unknown>; usage?: UsageInfo } }
      setResult(res.data.result)
      setUsage(res.data.usage || null)
    } catch (e) {
      const err = e as { response?: { data?: { message?: string } } }
      message.error(err?.response?.data?.message || 'AI 分析失败')
    } finally {
      setLoading(false)
    }
  }

  const openModal = () => { setOpen(true); if (options[0]) run(options[0].type) }

  return (
    <>
      <Button size={size} type={type} icon={<ThunderboltOutlined />} onClick={openModal}>AI 分析</Button>
      <Modal
        title={<span><ThunderboltOutlined className="text-indigo-500 mr-2" />AI 智能分析</span>}
        open={open} onCancel={() => setOpen(false)} footer={null} width={640} destroyOnClose
      >
        {options.length > 1 && (
          <Segmented
            className="mb-4"
            value={active}
            options={options.map((o) => ({ label: o.label, value: o.type }))}
            onChange={(v) => run(v as string)}
          />
        )}
        <div className="min-h-[200px]">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 gap-3">
              <Spin /><span className="text-sm text-slate-400">AI 分析中，请稍候…</span>
            </div>
          ) : result ? (
            <>
              <ResultView type={active!} result={result} />
              {usage && (usage.token_in || usage.token_out) ? (
                <div className="text-xs text-slate-400 mt-4 pt-3 border-t border-slate-100">
                  模型 {usage.model} · Token {usage.token_in}/{usage.token_out}
                  {usage.cost_est ? ` · 约 ¥${usage.cost_est.toFixed(4)}` : ''}
                </div>
              ) : null}
            </>
          ) : (
            <Empty description="暂无结果" />
          )}
        </div>
      </Modal>
    </>
  )
}
