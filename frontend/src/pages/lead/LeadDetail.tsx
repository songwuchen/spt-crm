import { useState, useEffect } from 'react'
import { Button, Space, Modal, Spin, Tabs, message } from 'antd'
import { EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import { leadApi } from '@/api/lead'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { Lead } from '@/api/types'
import { sourceLabels } from '@/api/types'
import AttachmentPanel from '@/components/AttachmentPanel'
import ActivityTimeline from '@/components/ActivityTimeline'
import DetailSkeleton from '@/components/DetailSkeleton'
import { leadStatusConfig as statusConfig } from '@/constants/labels'

const qualifySteps = [
  { key: 'new', label: '新建', icon: 'add_circle' },
  { key: 'following', label: '跟进', icon: 'chat' },
  { key: 'qualified', label: '转化', icon: 'check_circle' },
]

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="py-3 border-b border-slate-50 last:border-0">
      <div className="text-[10px] text-slate-400 uppercase font-bold tracking-wider mb-1">{label}</div>
      <div className="text-sm font-semibold text-slate-700">{value || <span className="text-slate-300">-</span>}</div>
    </div>
  )
}

function ScoreGauge({ score }: { score: number }) {
  const getColor = (s: number) => {
    if (s >= 80) return { bar: 'bg-emerald-500', text: 'text-emerald-600', label: '优质', labelBg: 'bg-emerald-50 text-emerald-600 border-emerald-100' }
    if (s >= 60) return { bar: 'bg-primary', text: 'text-primary', label: '良好', labelBg: 'bg-blue-50 text-blue-600 border-blue-100' }
    if (s >= 40) return { bar: 'bg-amber-500', text: 'text-amber-600', label: '一般', labelBg: 'bg-amber-50 text-amber-600 border-amber-100' }
    return { bar: 'bg-slate-300', text: 'text-slate-400', label: '较低', labelBg: 'bg-slate-50 text-slate-500 border-slate-200' }
  }
  const cfg = getColor(score)
  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
      <div className="flex items-center gap-2 mb-4">
        <span className="material-symbols-outlined text-primary text-lg">auto_awesome</span>
        <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-400">AI 线索评分</h3>
      </div>
      <div className="flex items-center gap-4 mb-3">
        <span className={`text-4xl font-black tabular-nums ${cfg.text}`}>{score}</span>
        <span className={`inline-flex px-2.5 py-0.5 rounded text-[10px] font-bold uppercase border ${cfg.labelBg}`}>
          {cfg.label}
        </span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${cfg.bar}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

export default function LeadDetail() {
  usePageTitle('线索详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [lead, setLead] = useState<Lead | null>(null)

  const fetchLead = async () => {
    const res = await leadApi.get(id!)
    setLead(res.data)
  }

  useEffect(() => { if (id) fetchLead() }, [id])

  const handleQualify = () => {
    Modal.confirm({
      title: '确认转化',
      content: '将此线索转化为客户？转化后线索状态将变为"已转化"。',
      onOk: async () => {
        const res = await leadApi.qualify(id!)
        message.success(`已转化为客户: ${res.data.customer_name}`)
        fetchLead()
      },
    })
  }

  const handleDiscard = () => {
    Modal.confirm({
      title: '确认废弃',
      content: '确定要废弃此线索？',
      okType: 'danger',
      onOk: async () => {
        await leadApi.discard(id!)
        message.success('线索已废弃')
        fetchLead()
      },
    })
  }

  if (!lead) return (
    <DetailSkeleton />
  )

  const canOperate = lead.status !== 'qualified' && lead.status !== 'discarded'
  const s = statusConfig[lead.status] || statusConfig.new

  const currentStepIdx = lead.status === 'discarded' ? -1 : qualifySteps.findIndex((st) => st.key === lead.status)

  return (
    <div>
      {/* Lead Header */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-xl bg-primary/5 border border-primary/10 shadow-sm flex items-center justify-center">
              <span className="material-symbols-outlined text-2xl text-primary">trending_up</span>
            </div>
            <div>
              <div className="flex items-center gap-3 mb-1">
                <h1 className="text-2xl font-bold text-slate-900">{lead.title}</h1>
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold uppercase border ${s.bg} ${s.text} ${s.border}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
                  {s.label}
                </span>
              </div>
              <div className="flex items-center gap-4 text-sm text-slate-500">
                {lead.company_name && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">business</span> {lead.company_name}
                  </span>
                )}
                {lead.industry && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">factory</span> {lead.industry}
                  </span>
                )}
                {lead.region && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">location_on</span> {lead.region}
                  </span>
                )}
              </div>
            </div>
          </div>
          <Space>
            {canOperate && (
              <>
                <Button icon={<EditOutlined />} onClick={() => navigate(`/leads/${id}/edit`)}>编辑</Button>
                <Button
                  type="primary"
                  onClick={handleQualify}
                >
                  <span className="material-symbols-outlined text-sm mr-1">check_circle</span>
                  转化为客户
                </Button>
                <Button danger onClick={handleDiscard}>
                  <span className="material-symbols-outlined text-sm mr-1">block</span>
                  废弃
                </Button>
              </>
            )}
            <Button danger icon={<DeleteOutlined />} onClick={() => {
              Modal.confirm({
                title: '确认删除', content: `确定要删除线索「${lead.title}」？`,
                okType: 'danger',
                onOk: async () => {
                  await leadApi.delete(id!)
                  message.success('线索已删除')
                  navigate('/leads')
                },
              })
            }}>删除</Button>
          </Space>
        </div>

        {/* Qualification Progress */}
        {lead.status !== 'discarded' && (
          <div className="mt-6 pt-5 border-t border-slate-100">
            <div className="flex items-center gap-0">
              {qualifySteps.map((step, idx) => {
                const isActive = idx <= currentStepIdx
                const isCurrent = idx === currentStepIdx
                return (
                  <div key={step.key} className="flex items-center">
                    <div className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-colors ${
                      isCurrent ? 'bg-primary/10 text-primary' : isActive ? 'text-emerald-600' : 'text-slate-300'
                    }`}>
                      <span className="material-symbols-outlined text-lg">{step.icon}</span>
                      <span className="text-xs font-bold uppercase tracking-wider">{step.label}</span>
                    </div>
                    {idx < qualifySteps.length - 1 && (
                      <div className={`w-12 h-0.5 mx-1 rounded ${isActive && idx < currentStepIdx ? 'bg-emerald-300' : 'bg-slate-200'}`} />
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Content Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left: Lead Portrait */}
        <div className="col-span-3 space-y-6">
          {/* Score Card */}
          <ScoreGauge score={lead.score ?? 0} />

          {/* Lead Info */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-0">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">线索信息</h3>
            <InfoField label="联系人" value={lead.contact_name} />
            <InfoField label="联系电话" value={lead.contact_phone} />
            <InfoField label="联系邮箱" value={lead.contact_email} />
            <InfoField label="来源" value={lead.source ? (sourceLabels[lead.source] || lead.source) : undefined} />
            <InfoField label="预算范围" value={lead.budget_range} />
            <InfoField label="负责人" value={lead.owner_name} />
            {lead.converted_customer_id && (
              <InfoField label="转化客户" value={
                <a onClick={() => navigate(`/customers/${lead.converted_customer_id}`)} className="text-primary font-bold text-xs hover:underline">
                  查看客户详情
                </a>
              } />
            )}
          </div>
        </div>

        {/* Center: Tabs Content */}
        <div className="col-span-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <Tabs
              defaultActiveKey="detail"
              className="px-6 pt-2"
              items={[
                {
                  key: 'detail',
                  label: <span className="font-semibold">详细信息</span>,
                  children: (
                    <div className="pb-6 space-y-6">
                      {/* Demand Summary */}
                      {lead.demand_summary && (
                        <div>
                          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">需求摘要</div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-sm text-slate-700 leading-relaxed">
                            {lead.demand_summary}
                          </div>
                        </div>
                      )}

                      {/* Remark */}
                      {lead.remark && (
                        <div>
                          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">备注</div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-sm text-slate-600 leading-relaxed">
                            {lead.remark}
                          </div>
                        </div>
                      )}

                      {/* Meta Info */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">创建时间</div>
                          <div className="text-sm font-semibold text-slate-700">
                            {lead.created_at ? new Date(lead.created_at).toLocaleString('zh-CN') : '-'}
                          </div>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">更新时间</div>
                          <div className="text-sm font-semibold text-slate-700">
                            {lead.updated_at ? new Date(lead.updated_at).toLocaleString('zh-CN') : '-'}
                          </div>
                        </div>
                      </div>
                    </div>
                  ),
                },
                {
                  key: 'activities',
                  label: <span className="font-semibold">动态</span>,
                  children: (
                    <div className="py-4">
                      <ActivityTimeline bizType="lead" bizId={id!} />
                    </div>
                  ),
                },
                {
                  key: 'attachments',
                  label: <span className="font-semibold">附件</span>,
                  children: (
                    <div className="py-4">
                      <AttachmentPanel bizType="lead" bizId={id!} />
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>

        {/* Right: AI Insights Panel */}
        <div className="col-span-3">
          <div className="bg-blue-50/50 rounded-xl border border-blue-100 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-5">
              <span className="material-symbols-outlined text-primary">auto_awesome</span>
              <h3 className="text-[10px] font-bold uppercase tracking-widest text-slate-900">AI 智能洞察</h3>
            </div>

            <div className="space-y-4">
              {/* Score Analysis */}
              <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-primary text-sm">analytics</span>
                  <span className="text-xs font-bold text-slate-800">评分分析</span>
                </div>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {(lead.score ?? 0) >= 80
                    ? '该线索评分优异，建议尽快安排转化跟进，避免错失高价值客户。'
                    : (lead.score ?? 0) >= 60
                    ? '线索质量良好，建议持续跟进并获取更多需求信息以提高转化率。'
                    : (lead.score ?? 0) >= 40
                    ? '线索质量一般，建议进一步验证客户意向和预算情况。'
                    : '线索评分较低，建议确认联系信息有效性和基本意向。'}
                </p>
              </div>

              {/* Next Action */}
              {canOperate && (
                <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="material-symbols-outlined text-amber-500 text-sm">lightbulb</span>
                    <span className="text-xs font-bold text-slate-800">建议操作</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed mb-3">
                    {lead.status === 'new'
                      ? '新线索建议48小时内完成首次联系，可通过电话或邮件确认基本意向。'
                      : '跟进中线索建议定期更新进展，及时记录客户反馈和需求变化。'}
                  </p>
                  <button
                    onClick={lead.status === 'new' ? () => navigate(`/leads/${id}/edit`) : handleQualify}
                    className="w-full py-2 bg-white border border-primary text-primary rounded-lg text-xs font-bold hover:bg-primary hover:text-white transition-colors"
                  >
                    {lead.status === 'new' ? '开始跟进' : '立即转化'}
                  </button>
                </div>
              )}

              {/* Conversion Card */}
              {lead.converted_customer_id && (
                <div className="bg-white p-4 rounded-xl border border-emerald-100 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="material-symbols-outlined text-emerald-500 text-sm">check_circle</span>
                    <span className="text-xs font-bold text-slate-800">已转化</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed mb-3">
                    该线索已成功转化为客户，可前往客户详情页查看完整信息。
                  </p>
                  <button
                    onClick={() => navigate(`/customers/${lead.converted_customer_id}`)}
                    className="w-full py-2 bg-emerald-600 text-white rounded-lg text-xs font-bold hover:bg-emerald-700 transition-colors"
                  >
                    查看客户详情
                  </button>
                </div>
              )}

              {/* Budget Insight */}
              {lead.budget_range && (
                <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="material-symbols-outlined text-slate-500 text-sm">payments</span>
                    <span className="text-xs font-bold text-slate-800">预算洞察</span>
                  </div>
                  <p className="text-xs text-slate-500 leading-relaxed">
                    客户预算范围 <span className="font-bold text-slate-700">{lead.budget_range}</span>，
                    建议匹配相应价位的产品方案。
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
