import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { message } from 'antd'
import { customerApi } from '@/api/customer'
import { projectApi } from '@/api/project'
import { activityApi } from '@/api/activity'
import { aiApi } from '@/api/ai'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { Customer, OpportunityProject } from '@/api/types'

const interactionTypes = [
  { key: 'call', icon: 'call', label: '电话' },
  { key: 'visit', icon: 'distance', label: '拜访' },
  { key: 'meeting', icon: 'groups', label: '会议' },
]

const resultOptions = [
  { key: 'progress', label: '进展', desc: '积极进展或达成里程碑', icon: 'trending_up', color: 'text-green-500' },
  { key: 'stagnant', label: '停滞', desc: '状态无显著变化', icon: 'pause_circle', color: 'text-amber-500' },
  { key: 'risk', label: '风险', desc: '潜在问题或负面反馈', icon: 'warning', color: 'text-red-500' },
]

export default function MobileFollowUp() {
  usePageTitle('新建跟进')
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const presetBizType = searchParams.get('biz_type') || ''
  const presetBizId = searchParams.get('biz_id') || ''

  const [customers, setCustomers] = useState<Customer[]>([])
  const [projects, setProjects] = useState<OpportunityProject[]>([])
  const [bizType, setBizType] = useState(presetBizType || 'customer')
  const [bizId, setBizId] = useState(presetBizId)
  const [activityType, setActivityType] = useState('call')
  const [result, setResult] = useState('progress')
  const [content, setContent] = useState('')
  const [contactName, setContactName] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [aiSummary, setAiSummary] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)

  useEffect(() => {
    customerApi.list({ pageNo: 1, pageSize: 100 }).then((res) => {
      if (res.data?.items) setCustomers(res.data.items)
    }).catch(() => {})
    projectApi.list({ pageNo: 1, pageSize: 100 }).then((res) => {
      if (res.data?.items) setProjects(res.data.items)
    }).catch(() => {})
  }, [])

  const handleSubmit = async () => {
    if (!bizId) { message.warning('请选择客户或项目'); return }
    if (!content.trim()) { message.warning('请填写跟进详情'); return }
    setSubmitting(true)
    try {
      const res = await activityApi.create({
        biz_type: bizType,
        biz_id: bizId,
        activity_type: activityType,
        subject: `${interactionTypes.find(t => t.key === activityType)?.label || ''}跟进`,
        content: content.trim(),
        contact_name: contactName || undefined,
        result_json: { result, ai_summary: aiSummary || undefined },
      })
      if (res.code === 0) {
        message.success('跟进记录已保存')
        navigate(-1)
      }
    } catch { message.error('保存失败') }
    finally { setSubmitting(false) }
  }

  const handleAiSummary = async () => {
    if (!content.trim()) { message.warning('请先填写跟进详情'); return }
    setAiLoading(true)
    try {
      const res = await aiApi.analyze({
        biz_type: bizType,
        biz_id: bizId || 'none',
        analysis_type: 'meeting_summary',
      })
      if (res.data?.result) {
        const r = res.data.result as Record<string, unknown>
        const pick = (...keys: string[]) => keys.map((k) => r[k]).find((v) => typeof v === 'string' && v) as string | undefined
        const text =
          pick('summary', 'text', 'overall_assessment', 'overall_comment', 'content') ||
          Object.values(r).filter((v) => typeof v === 'string' && v).join('；') ||
          '已生成摘要，请在 AI 任务中心查看详情'
        setAiSummary(text)
      }
    } catch { message.error('AI 摘要生成失败') }
    finally { setAiLoading(false) }
  }

  const selectItems = bizType === 'customer'
    ? customers.map(c => ({ value: c.id, label: c.name }))
    : projects.map(p => ({ value: p.id, label: p.name }))

  return (
    <div className="flex flex-col min-h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => navigate(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0">
          <span className="material-symbols-outlined">chevron_left</span>
          <span className="text-sm font-medium">返回</span>
        </button>
        <h1 className="text-lg font-bold text-slate-900">新建跟进</h1>
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className="text-sm font-bold text-primary bg-transparent border-0 cursor-pointer p-0 disabled:opacity-50"
        >
          保存
        </button>
      </div>

      {/* Form */}
      <div className="space-y-5 flex-1">
        {/* Biz Type Toggle + Selector */}
        <section className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 ml-1">关联对象</label>
          <div className="flex gap-2 mb-2">
            {[
              { key: 'customer', label: '客户' },
              { key: 'project', label: '商机' },
            ].map(t => (
              <button
                key={t.key}
                onClick={() => { setBizType(t.key); setBizId('') }}
                className={`flex-1 h-9 rounded-lg text-sm font-bold border-0 cursor-pointer transition-colors ${
                  bizType === t.key ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="relative">
            <select
              value={bizId}
              onChange={(e) => setBizId(e.target.value)}
              className="w-full appearance-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 focus:border-primary focus:ring-1 focus:ring-primary"
            >
              <option value="">请选择{bizType === 'customer' ? '客户' : '商机'}</option>
              {selectItems.map(item => (
                <option key={item.value} value={item.value}>{item.label}</option>
              ))}
            </select>
            <span className="material-symbols-outlined pointer-events-none absolute right-4 top-1/2 -translate-y-1/2 text-slate-400" style={{ fontSize: 18 }}>expand_more</span>
          </div>
        </section>

        {/* Interaction Type */}
        <section className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 ml-1">互动类型</label>
          <div className="flex gap-2">
            {interactionTypes.map(t => (
              <button
                key={t.key}
                onClick={() => setActivityType(t.key)}
                className={`flex flex-1 flex-col items-center justify-center gap-1 rounded-xl px-3 py-3.5 border-0 cursor-pointer transition-colors ${
                  activityType === t.key
                    ? 'bg-primary text-white'
                    : 'bg-white border border-slate-200 text-slate-600 shadow-sm'
                }`}
                style={activityType !== t.key ? { border: '1px solid #e2e8f0' } : {}}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{t.icon}</span>
                <span className="text-sm font-medium">{t.label}</span>
              </button>
            ))}
          </div>
        </section>

        {/* Contact Name */}
        <section className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 ml-1">联系人</label>
          <input
            type="text"
            value={contactName}
            onChange={(e) => setContactName(e.target.value)}
            placeholder="联系人姓名（选填）"
            className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 focus:border-primary focus:ring-1 focus:ring-primary outline-none"
          />
        </section>

        {/* Result Selector */}
        <section className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 ml-1">当前结果</label>
          <div className="flex flex-col gap-2">
            {resultOptions.map(opt => (
              <label
                key={opt.key}
                className={`flex items-center gap-3 rounded-xl border p-3 cursor-pointer transition-colors ${
                  result === opt.key ? 'border-primary bg-primary/5' : 'border-slate-200 bg-white'
                }`}
                onClick={() => setResult(opt.key)}
              >
                <input
                  type="radio"
                  name="result"
                  checked={result === opt.key}
                  onChange={() => setResult(opt.key)}
                  className="h-4 w-4 text-primary border-slate-300 focus:ring-primary"
                />
                <div className="flex-1">
                  <p className="text-sm font-medium text-slate-900">{opt.label}</p>
                  <p className="text-sm text-slate-500">{opt.desc}</p>
                </div>
                <span className={`material-symbols-outlined ${opt.color}`}>{opt.icon}</span>
              </label>
            ))}
          </div>
        </section>

        {/* Visit Details */}
        <section className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 ml-1">跟进详情</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="输入跟进详情、讨论要点等..."
            rows={4}
            className="w-full rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-900 focus:border-primary focus:ring-primary outline-none resize-none"
          />
        </section>

        {/* Attachments */}
        <section className="space-y-2">
          <label className="text-sm font-semibold text-slate-700 ml-1">附件</label>
          <div className="flex gap-3">
            <div className="flex h-20 w-20 flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400 cursor-pointer">
              <span className="material-symbols-outlined">add_a_photo</span>
              <span className="text-[12px]">拍照</span>
            </div>
            <div className="flex h-20 w-20 flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400 cursor-pointer">
              <span className="material-symbols-outlined">mic</span>
              <span className="text-[12px]">录音</span>
            </div>
          </div>
        </section>

        {/* AI Summary */}
        <section>
          <button
            onClick={handleAiSummary}
            disabled={aiLoading}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary/10 py-3.5 text-primary transition-colors active:bg-primary/20 border-0 cursor-pointer font-bold text-sm disabled:opacity-50"
          >
            {aiLoading ? (
              <span className="material-symbols-outlined animate-spin" style={{ fontSize: 18 }}>progress_activity</span>
            ) : (
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>auto_awesome</span>
            )}
            <span>AI 生成摘要</span>
          </button>
        </section>

        {/* AI Summary Result */}
        {aiSummary && (
          <div className="rounded-xl border border-primary/20 bg-primary/5 p-4 space-y-2">
            <div className="flex items-center gap-2 text-primary font-bold text-sm">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>description</span>
              AI 生成摘要
            </div>
            <p className="text-sm leading-relaxed text-slate-700">{aiSummary}</p>
          </div>
        )}
      </div>
    </div>
  )
}
