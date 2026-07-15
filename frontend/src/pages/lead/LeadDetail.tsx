import { useState, useEffect } from 'react'
import { Button, Space, Modal, Spin, Tabs, Checkbox, message, Input } from 'antd'
import { EditOutlined, DeleteOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import { leadApi } from '@/api/lead'
import { approvalApi } from '@/api/approval'
import type { ApprovalPendingItem } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { Lead } from '@/api/types'
import { sourceLabels } from '@/api/types'
import AttachmentPanel from '@/components/AttachmentPanel'
import ActivityTimeline from '@/components/ActivityTimeline'
import DetailSkeleton from '@/components/DetailSkeleton'
import { leadStatusConfig as statusConfig, leadReviewStatusConfig } from '@/constants/labels'
import { useDataDict } from '@/hooks/useDataDict'
import EntityCustomFields from '@/components/lowcode/EntityCustomFields'

const categoryLabels: Record<string, string> = { self_reported: '自报', distributed: '分发' }
const countryLabels: Record<string, string> = { domestic: '国内', overseas: '国外' }

function formatLocation(lead: Lead): string | undefined {
  if (lead.country_type === 'overseas') {
    return `国外${lead.country_name ? ' · ' + lead.country_name : ''}`
  }
  const parts = [lead.province, lead.city, lead.district].filter(Boolean)
  if (parts.length > 0) return parts.join(' · ')
  return lead.region || undefined
}

const qualifySteps = [
  { key: 'new', label: '新建', icon: 'add_circle' },
  { key: 'following', label: '跟进', icon: 'chat' },
  { key: 'qualified', label: '转化', icon: 'check_circle' },
]

function InfoField({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="py-3 border-b border-slate-50 last:border-0">
      <div className="text-[12px] text-slate-400 uppercase font-bold tracking-wider mb-1">{label}</div>
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
        <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-400">AI 线索评分</h3>
      </div>
      <div className="flex items-center gap-4 mb-3">
        <span className={`text-4xl font-black tabular-nums ${cfg.text}`}>{score}</span>
        <span className={`inline-flex px-2.5 py-0.5 rounded text-[12px] font-bold uppercase border ${cfg.labelBg}`}>
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
  const [activeTab, setActiveTab] = useState('detail')
  const [followUpSignal, setFollowUpSignal] = useState(0)
  // 当前用户对该线索的待审批任务（有则可在本页直接审批）
  const [myTask, setMyTask] = useState<ApprovalPendingItem | null>(null)
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectComment, setRejectComment] = useState('')
  const [deciding, setDeciding] = useState(false)
  const customerTypeDict = useDataDict('customer_type')
  const industryDict = useDataDict('industry')

  const fetchLead = async () => {
    try {
      const res = await leadApi.get(id!)
      setLead(res.data)
    } catch {
      message.error('获取线索详情失败')
    }
  }

  // 查询「我的待办审批」里是否有这条线索的、且轮到我处理的任务
  const fetchMyApproval = async () => {
    try {
      const res = await approvalApi.myPending()
      const t = (res.data || []).find(
        (p) => p.flow?.biz_type === 'lead' && p.flow?.biz_id === id && p.status === 'pending',
      )
      setMyTask(t || null)
    } catch { setMyTask(null) }
  }

  const handleDecide = async (action: 'approved' | 'rejected', comment?: string) => {
    if (!myTask) return
    setDeciding(true)
    try {
      await approvalApi.decide(myTask.id, { action, comment })
      message.success(action === 'approved' ? '已通过' : '已驳回')
      setMyTask(null)
      fetchLead()
    } catch {
      message.error('操作失败')
    } finally {
      setDeciding(false)
    }
  }

  useEffect(() => { if (id) { fetchLead(); fetchMyApproval() } }, [id])

  // 「开始跟进」：跳到动态页并打开跟进记录编辑（自动带入线索信息）
  const handleStartFollowUp = () => {
    setActiveTab('activities')
    setFollowUpSignal((s) => s + 1)
  }

  // 首次跟进记录保存后，将「新建」线索推进到「跟进中」
  const handleFollowUpCreated = async () => {
    if (lead?.status === 'new' && id) {
      try {
        await leadApi.batchStatus([id], 'following')
        fetchLead()
      } catch { /* 记录已保存，状态推进失败不阻塞流程 */ }
    }
  }

  const handleQualify = () => {
    let createOpp = true
    Modal.confirm({
      title: '确认转化',
      content: (
        <div>
          <p className="mb-2">将此线索转化为客户？转化后线索状态将变为"已转化"。</p>
          <Checkbox defaultChecked onChange={(e) => { createOpp = e.target.checked }}>
            同时创建商机（带入需求摘要 / 预算）
          </Checkbox>
        </div>
      ),
      onOk: async () => {
        try {
          const res = await leadApi.qualify(id!, createOpp)
          message.success(res.data.project_code
            ? `已转化为客户「${res.data.customer_name}」并创建商机 ${res.data.project_code}`
            : `已转化为客户: ${res.data.customer_name}`)
          fetchLead()
        } catch {
          message.error('转化失败')
        }
      },
    })
  }

  const handleResubmit = async () => {
    try {
      await leadApi.submitReview(id!)
      message.success('已重新提交审核')
      fetchLead()
    } catch {
      message.error('提交审核失败')
    }
  }

  const handleDiscard = () => {
    Modal.confirm({
      title: '确认废弃',
      content: '确定要废弃此线索？',
      okType: 'danger',
      onOk: async () => {
        try {
          await leadApi.discard(id!)
          message.success('线索已废弃')
          fetchLead()
        } catch {
          message.error('操作失败')
        }
      },
    })
  }

  if (!lead) return (
    <DetailSkeleton />
  )

  const canOperate = lead.status !== 'qualified' && lead.status !== 'discarded'
  const reviewStatus = lead.review_status || 'approved'
  const reviewApproved = reviewStatus === 'approved'
  const reviewCfg = !reviewApproved ? leadReviewStatusConfig[reviewStatus] : null
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
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[12px] font-bold uppercase border ${s.bg} ${s.text} ${s.border}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
                  {s.label}
                </span>
                {reviewCfg && (
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[12px] font-bold uppercase border ${reviewCfg.bg} ${reviewCfg.text} ${reviewCfg.border}`}>
                    <span className="material-symbols-outlined text-sm">{reviewStatus === 'pending' ? 'hourglass_top' : 'gpp_bad'}</span>
                    {reviewCfg.label}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-sm text-slate-500">
                {lead.company_name && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">business</span> {lead.company_name}
                  </span>
                )}
                {lead.industry && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">factory</span>
                    {industryDict.options.find(o => o.value === lead.industry)?.label || lead.industry}
                  </span>
                )}
                {formatLocation(lead) && (
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-sm">location_on</span> {formatLocation(lead)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <Space>
            {canOperate && (
              <>
                <Button icon={<EditOutlined />} onClick={() => navigate(`/leads/${id}/edit`)}>编辑</Button>
                {reviewStatus === 'rejected' && (
                  <Button type="primary" onClick={handleResubmit}>
                    <span className="material-symbols-outlined text-sm mr-1">restart_alt</span>
                    重新提交审核
                  </Button>
                )}
                {reviewApproved && (
                  <Button
                    type="primary"
                    onClick={handleQualify}
                  >
                    <span className="material-symbols-outlined text-sm mr-1">check_circle</span>
                    转化为客户
                  </Button>
                )}
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
                  try {
                    await leadApi.delete(id!)
                    message.success('线索已删除')
                    navigate('/leads')
                  } catch {
                    message.error('删除失败')
                  }
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
                      <span className="text-sm font-bold uppercase tracking-wider">{step.label}</span>
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

      {/* 待我审批：当前用户是该线索审批人时，可直接在此通过/驳回 */}
      {myTask && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 mb-6 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-primary">approval</span>
            <div>
              <div className="text-sm font-bold text-slate-900">该线索待您审批</div>
              <div className="text-sm text-slate-500">
                {myTask.flow?.title || '线索审核'}
                {myTask.flow?.submitted_by_name ? ` · 发起人 ${myTask.flow.submitted_by_name}` : ''}
              </div>
            </div>
          </div>
          <Space>
            <Button danger disabled={deciding} onClick={() => { setRejectComment(''); setRejectOpen(true) }}>驳回</Button>
            <Button type="primary" loading={deciding} onClick={() => handleDecide('approved')}>通过</Button>
          </Space>
        </div>
      )}

      {/* Review status banner */}
      {reviewCfg && (
        <div className={`rounded-xl border ${reviewCfg.border} ${reviewCfg.bg} p-4 mb-6 flex items-start gap-3`}>
          <span className={`material-symbols-outlined ${reviewCfg.text}`}>
            {reviewStatus === 'pending' ? 'hourglass_top' : 'gpp_bad'}
          </span>
          <div className="flex-1">
            <div className={`text-sm font-bold ${reviewCfg.text}`}>
              {reviewStatus === 'pending' ? '线索待信息情报部内勤审核' : '线索审核被驳回'}
            </div>
            <div className="text-sm text-slate-600 mt-1">
              {reviewStatus === 'pending'
                ? '审核通过后方可转化为客户。'
                : (lead.reject_reason ? `驳回原因：${lead.reject_reason}` : '请根据反馈修改线索信息后重新提交审核。')}
            </div>
          </div>
          {reviewStatus === 'rejected' && canOperate && (
            <Button size="small" type="primary" onClick={handleResubmit}>重新提交审核</Button>
          )}
        </div>
      )}

      {/* Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Lead Portrait */}
        <div className="lg:col-span-3 space-y-6">
          {/* Score Card */}
          <ScoreGauge score={lead.score ?? 0} />

          {/* Lead Info */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 space-y-0">
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">线索信息</h3>
            <InfoField label="联系人" value={lead.contact_name} />
            <InfoField label="联系电话" value={lead.contact_phone} />
            <InfoField label="联系邮箱" value={lead.contact_email} />
            <InfoField label="来源" value={lead.source ? (sourceLabels[lead.source] || lead.source) : undefined} />
            <InfoField label="客户类型" value={lead.customer_type ? (customerTypeDict.options.find(o => o.value === lead.customer_type)?.label || lead.customer_type) : undefined} />
            <InfoField label="类别" value={lead.category ? categoryLabels[lead.category] : undefined} />
            <InfoField label="国别" value={lead.country_type ? (lead.country_type === 'overseas' && lead.country_name ? `${countryLabels.overseas} · ${lead.country_name}` : countryLabels[lead.country_type]) : undefined} />
            <InfoField label="预算范围" value={lead.budget_range} />
            <InfoField label="负责人" value={lead.owner_name} />
            {lead.converted_customer_id && (
              <InfoField label="转化客户" value={
                <a onClick={() => navigate(`/customers/${lead.converted_customer_id}`)} className="text-primary font-bold text-sm hover:underline">
                  查看客户详情
                </a>
              } />
            )}
          </div>
          <EntityCustomFields entityType="lead" value={(lead as unknown as { custom_fields_json?: Record<string, unknown> }).custom_fields_json || {}} readOnly />
        </div>

        {/* Center: Tabs Content */}
        <div className="lg:col-span-6">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
            <Tabs
              activeKey={activeTab}
              onChange={setActiveTab}
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
                          <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-2">需求摘要</div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-sm text-slate-700 leading-relaxed">
                            {lead.demand_summary}
                          </div>
                        </div>
                      )}

                      {/* Remark */}
                      {lead.remark && (
                        <div>
                          <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-2">备注</div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-sm text-slate-600 leading-relaxed">
                            {lead.remark}
                          </div>
                        </div>
                      )}

                      {/* Meta Info */}
                      <div className="grid grid-cols-2 gap-4">
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                          <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">创建时间</div>
                          <div className="text-sm font-semibold text-slate-700">
                            {lead.created_at ? new Date(lead.created_at).toLocaleString('zh-CN') : '-'}
                          </div>
                        </div>
                        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                          <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">更新时间</div>
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
                      <ActivityTimeline bizType="lead" bizId={id!} openCreateSignal={followUpSignal}
                        defaultContactName={lead.contact_name} onCreated={handleFollowUpCreated} />
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
        <div className="lg:col-span-3">
          <div className="bg-blue-50/50 rounded-xl border border-blue-100 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-5">
              <span className="material-symbols-outlined text-primary">auto_awesome</span>
              <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-900">AI 智能洞察</h3>
            </div>

            <div className="space-y-4">
              {/* Score Analysis */}
              <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <span className="material-symbols-outlined text-primary text-sm">analytics</span>
                  <span className="text-sm font-bold text-slate-800">评分分析</span>
                </div>
                <p className="text-sm text-slate-500 leading-relaxed">
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
              {canOperate && reviewApproved && (
                <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="material-symbols-outlined text-amber-500 text-sm">lightbulb</span>
                    <span className="text-sm font-bold text-slate-800">建议操作</span>
                  </div>
                  <p className="text-sm text-slate-500 leading-relaxed mb-3">
                    {lead.status === 'new'
                      ? '新线索建议48小时内完成首次联系，可通过电话或邮件确认基本意向。'
                      : '跟进中线索建议定期更新进展，及时记录客户反馈和需求变化。'}
                  </p>
                  <button
                    onClick={lead.status === 'new' ? handleStartFollowUp : handleQualify}
                    className="w-full py-2 bg-white border border-primary text-primary rounded-lg text-sm font-bold hover:bg-primary hover:text-white transition-colors"
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
                    <span className="text-sm font-bold text-slate-800">已转化</span>
                  </div>
                  <p className="text-sm text-slate-500 leading-relaxed mb-3">
                    该线索已成功转化为客户，可前往客户详情页查看完整信息。
                  </p>
                  <button
                    onClick={() => navigate(`/customers/${lead.converted_customer_id}`)}
                    className="w-full py-2 bg-emerald-600 text-white rounded-lg text-sm font-bold hover:bg-emerald-700 transition-colors"
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
                    <span className="text-sm font-bold text-slate-800">预算洞察</span>
                  </div>
                  <p className="text-sm text-slate-500 leading-relaxed">
                    客户预算范围 <span className="font-bold text-slate-700">{lead.budget_range}</span>，
                    建议匹配相应价位的产品方案。
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 驳回原因弹窗 */}
      <Modal
        title="驳回审批"
        open={rejectOpen}
        onOk={() => { setRejectOpen(false); handleDecide('rejected', rejectComment) }}
        onCancel={() => setRejectOpen(false)}
        okText="确认驳回"
        okType="danger"
        cancelText="取消"
        confirmLoading={deciding}
      >
        <Input.TextArea rows={3} value={rejectComment} onChange={(e) => setRejectComment(e.target.value)}
          placeholder="请输入驳回原因（选填）" />
      </Modal>
    </div>
  )
}
