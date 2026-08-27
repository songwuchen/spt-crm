import { useState, useEffect } from 'react'
import { Button, Space, Modal, Tabs, Checkbox, message, Form, Input, Select, Table } from 'antd'
import { EditOutlined, DeleteOutlined, AuditOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { leadApi } from '@/api/lead'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail, WfTodoItem } from '@/types/lowcode'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { Lead, LeadReactivationRecord } from '@/api/types'
import { sourceLabels } from '@/api/types'
import AttachmentPanel from '@/components/AttachmentPanel'
import ActivityTimeline from '@/components/ActivityTimeline'
import DetailSkeleton from '@/components/DetailSkeleton'
import RecordPrevNextNav from '@/components/RecordPrevNextNav'
import { leadStatusConfig as statusConfig, leadReviewStatusConfig, customerNewnessLabels } from '@/constants/labels'
import { useDataDict } from '@/hooks/useDataDict'
import { useSiblingRecordNav } from '@/hooks/useSiblingRecordNav'
import { useAuthStore } from '@/stores/useAuthStore'
import EntityCustomFields from '@/components/lowcode/EntityCustomFields'
import { formatRegion } from '@/utils/address'
import LeadIntelReviewForm from '@/components/lead/LeadIntelReviewForm'
import LeadOwnerConfirmActions from '@/components/lead/LeadOwnerConfirmActions'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import WfActivateFlowModal from '@/components/lowcode/WfActivateFlowModal'
import { useWfProcessDrawer } from '@/components/lowcode/WfProcessDrawer'
import { isLeadOwnerConfirmNode, isLeadReviseTodo, isLeadIntelTodo, isLeadReactivationFollowTodo, leadReviseEditPath } from '@/utils/leadWorkflow'

import Icon from '@/components/Icon'
const categoryLabels: Record<string, string> = { self_reported: '自报', distributed: '分发' }
const countryLabels: Record<string, string> = { domestic: '国内', overseas: '国外' }

function formatArea(lead: Lead): string | undefined {
  if (lead.country_type === 'overseas') {
    return `国外${lead.country_name ? ' · ' + lead.country_name : ''}`
  }
  return formatRegion(lead) || undefined
}

/** 页头/摘要：省市区 + 详细地址 */
function formatLocation(lead: Lead): string | undefined {
  const area = formatArea(lead)
  const detail = (lead.region || '').trim()
  if (area && detail) return `${area} ${detail}`
  return area || detail || undefined
}

const qualifySteps = [
  { key: 'new', label: '新建', icon: 'add_circle' },
  { key: 'following', label: '跟进', icon: 'chat' },
  { key: 'qualified', label: '转化', icon: 'check_circle' },
]

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
        <Icon name="auto_awesome" className="text-primary text-lg" />
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
  const [searchParams, setSearchParams] = useSearchParams()
  const [reactIntent, setReactIntent] = useState(searchParams.get('react') === '1')
  const keepReact = searchParams.get('react') === '1'
  const siblingNav = useSiblingRecordNav('leads', id, {
    pathForId: (rid) => `/leads/${rid}${keepReact ? '?react=1' : ''}`,
    fetchPage: async (pageNo, snap) => {
      const q = snap.listQuery || {}
      const res = await leadApi.list({
        pageNo,
        pageSize: snap.pageSize,
        keyword: q.keyword as string | undefined,
        status: q.status as string | undefined,
        source: q.source as string | undefined,
        customer_type: q.customer_type as string | undefined,
        category: q.category as string | undefined,
        country_type: q.country_type as string | undefined,
        department_id: q.department_id as string | undefined,
        industry: q.industry as string | undefined,
        company_name: q.company_name as string | undefined,
        start_date: q.start_date as string | undefined,
        end_date: q.end_date as string | undefined,
        date_field: q.date_field as string | undefined,
        reactivation_active: q.reactivation_active as boolean | undefined,
        reactivation_status: q.reactivation_status as string | undefined,
      })
      return {
        ids: (res.data.items || []).map((x) => x.id),
        total: res.data.total,
      }
    },
  })
  const [lead, setLead] = useState<Lead | null>(null)
  const [activeTab, setActiveTab] = useState('detail')
  const [followUpSignal, setFollowUpSignal] = useState(0)
  // 当前用户对该线索的待审批任务（有则可在本页直接情报裁定）
  const [myTask, setMyTask] = useState<WfTodoItem | null>(null)
  const [myReactTask, setMyReactTask] = useState<WfTodoItem | null>(null)
  const [reviewInFlight, setReviewInFlight] = useState(false)
  const [wfInstance, setWfInstance] = useState<WfInstanceDetail | null>(null)
  const [activateOpen, setActivateOpen] = useState(false)
  const [wfCommenting, setWfCommenting] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const reloadAfterWf = () => {
    void fetchLead()
    void fetchMyApproval()
    if (id) void loadWf(id)
    void fetchReactivationRecords()
  }
  const { openWith: openWfDrawer, node: wfDrawerNode } = useWfProcessDrawer(reloadAfterWf)
  const [reactRecords, setReactRecords] = useState<LeadReactivationRecord[]>([])
  const [reactRecordsLoading, setReactRecordsLoading] = useState(false)
  const currentUser = useAuthStore((s) => s.user)
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const canDeleteLead = hasPermission('lead:delete')
  const hasLeadEdit = hasPermission('lead:edit')
  const canActivateFlow = hasPermission('workflow:activate') || hasPermission('workflow:manage')
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

  const fetchReactivationRecords = async () => {
    if (!id) return
    setReactRecordsLoading(true)
    try {
      const res = await leadApi.listReactivationRecords(id)
      setReactRecords(res.data || [])
    } catch {
      setReactRecords([])
    } finally {
      setReactRecordsLoading(false)
    }
  }

  const loadWf = async (bizId: string) => {
    try {
      const [leadWf, reactWf] = await Promise.all([
        workflowApi.byBiz({ biz_type: 'lead', biz_id: bizId }),
        workflowApi.byBiz({ biz_type: 'lead_reactivation', biz_id: bizId }),
      ])
      const inst =
        reactWf.data?.status === 'running' ? reactWf.data
          : leadWf.data?.status === 'running' ? leadWf.data
            : reactWf.data || leadWf.data
      setWfInstance(inst || null)
      setReviewInFlight(inst?.status === 'running')
    } catch {
      setWfInstance(null)
      setReviewInFlight(false)
    }
  }

  // 查询「我的待办审批」：申报信息(lead) 与 180天激活(lead_reactivation) 各自独立流程
  const fetchMyApproval = async () => {
    try {
      const [leadTodo, reactTodo] = await Promise.all([
        workflowApi.todo({ pageNo: 1, pageSize: 20, biz_type: 'lead', biz_id: id }),
        workflowApi.todo({ pageNo: 1, pageSize: 20, biz_type: 'lead_reactivation', biz_id: id }),
      ])
      const leadItems = leadTodo.data?.items || []
      const reactItems = reactTodo.data?.items || []
      setMyTask(leadItems.find((p) => p.status === 'pending') || null)
      setMyReactTask(reactItems.find((p) => p.status === 'pending') || null)
    } catch {
      setMyTask(null)
      setMyReactTask(null)
    }
  }

  useEffect(() => {
    if (id) {
      void fetchLead()
      void fetchMyApproval()
      void loadWf(id)
      void fetchReactivationRecords()
    }
  }, [id])

  useEffect(() => {
    if (searchParams.get('react') === '1') setReactIntent(true)
  }, [searchParams])

  useEffect(() => {
    if (!lead || !reactIntent) return
    setActiveTab('detail')
    const pending = myReactTask || myTask
    if (pending?.process_instance_id) {
      openWfDrawer(pending.process_instance_id, pending.task_id)
    }
    setReactIntent(false)
    if (searchParams.get('react') === '1') {
      const next = new URLSearchParams(searchParams)
      next.delete('react')
      setSearchParams(next, { replace: true })
    }
  }, [lead, reactIntent, myReactTask, myTask, openWfDrawer, searchParams, setSearchParams])

  const handleWfComment = async (content: string) => {
    if (!wfInstance?.id || !id) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfInstance.id, content)
      await loadWf(id)
    } finally {
      setWfCommenting(false)
    }
  }

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
      title: '确认是否转商机',
      content: (
        <div>
          <p className="mb-2">将此线索转为商机？转化后线索状态将变为「已转化」。</p>
          <p className="mb-2 text-slate-500 text-sm">
            需要出方案报价请确认创建商机；如为拟建项目、暂不出方案报价，可取消勾选「创建商机」仅标记转化。
            未匹配到已有客户时，系统将自动创建客户并关联商机。
          </p>
          <Checkbox defaultChecked onChange={(e) => { createOpp = e.target.checked }}>
            同时创建商机（带入需求摘要 / 预算）
          </Checkbox>
        </div>
      ),
      onOk: async () => {
        try {
          const res = await leadApi.qualify(id!, createOpp)
          const src = res.data.customer_link_source
          const suffix = res.data.project_code
            ? src === 'auto_created'
              ? '，已自动创建客户并关联'
              : src === 'matched'
                ? '，已关联已有客户'
                : src === 'ambiguous'
                  ? '，客户重名请在商机中手工选择'
                  : ''
            : ''
          message.success(res.data.project_code
            ? `已转商机 ${res.data.project_code}${suffix}`
            : '线索已标记为已转化')
          fetchLead()
        } catch {
          message.error('转化失败')
        }
      },
    })
  }

  const handleSubmitApproval = () => {
    if (!id) return
    Modal.confirm({
      title: '提交审批',
      content: '确认提交该线索进入信息情报部审批？提交后可在本页右侧「流程动态」查看进度。',
      okText: '提交审批',
      onOk: async () => {
        setSubmitting(true)
        try {
          await leadApi.submitReview(id)
          message.success('已提交审批')
          await fetchLead()
          await loadWf(id)
          await fetchMyApproval()
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          message.error(msg || '提交审核失败')
        } finally {
          setSubmitting(false)
        }
      },
    })
  }

  const handleResubmitRevise = () => {
    if (!id || !myTask?.task_id) return
    Modal.confirm({
      title: '重新提交',
      content: '确认修改无误后重新提交信息情报部审批？',
      okText: '重新提交',
      onOk: async () => {
        setSubmitting(true)
        try {
          await workflowApi.act(myTask.task_id, { action: 'resubmit' })
          message.success('已重新提交')
          setMyTask(null)
          await fetchLead()
          await loadWf(id)
          await fetchMyApproval()
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          message.error(msg || '重新提交失败')
        } finally {
          setSubmitting(false)
        }
      },
    })
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

  const openReactivationDrawer = () => {
    if (myReactTask?.process_instance_id) {
      openWfDrawer(myReactTask.process_instance_id, myReactTask.task_id)
      return
    }
    if (wfInstance?.biz_type === 'lead_reactivation' && wfInstance.id) {
      openWfDrawer(wfInstance.id, undefined)
    }
  }

  if (!lead) return (
    <DetailSkeleton />
  )

  const canOperate = lead.status !== 'qualified' && lead.status !== 'discarded'
  const reviewStatus = lead.review_status || 'approved'
  const reactStatus = lead.reactivation_status || 'none'
  const reactFollowTodo = !!myReactTask && isLeadReactivationFollowTodo({
    bizType: myReactTask.biz_type,
    nodeId: myReactTask.node_id,
    nodeName: myReactTask.node_name,
  })
  const reactIntelTodo = !!myReactTask && isLeadIntelTodo({
    bizType: myReactTask.biz_type,
    nodeName: myReactTask.node_name,
    nodeId: myReactTask.node_id,
    nodeType: myReactTask.node_type,
    taskKind: myReactTask.task_kind,
  })
  const reactTodo =
    reactFollowTodo
    || reactStatus === 'awaiting_reporter'
    || reactStatus === 'awaiting_filler'
  const canSubmitReact = reactFollowTodo && !!currentUser
  // 仅情报审进行中锁定；收录后即使还有业务员确认节点也可改
  const reviewInFlightLock = reviewInFlight && (reviewStatus === 'draft' || reviewStatus === 'pending')
  const canEditLead = hasLeadEdit && !reviewInFlightLock
  const canSubmitApproval = canOperate && reviewStatus === 'draft'
  const reviewApproved = reviewStatus === 'approved'
  const reviewCfg = !reviewApproved ? leadReviewStatusConfig[reviewStatus] : null
  const s = statusConfig[lead.status] || statusConfig.new
  // 驳回终态不可再跟进；收录后仍可在详情动态里「添加记录」
  const allowFollowActivity = canOperate && reviewStatus !== 'rejected'
  const isReviseTask = !!myTask && isLeadReviseTodo({
    taskKind: myTask.task_kind,
    nodeType: myTask.node_type,
    nodeName: myTask.node_name,
  })
  const isIntelTask = !!myTask && isLeadIntelTodo({
    bizType: 'lead',
    nodeName: myTask.node_name,
    nodeType: myTask.node_type,
    taskKind: myTask.task_kind,
  })
  const isOwnerConfirmTask = !!myTask && isLeadOwnerConfirmNode(myTask.node_name)

  const currentStepIdx = lead.status === 'discarded' ? -1 : qualifySteps.findIndex((st) => st.key === lead.status)

  const reviewBannerIcon =
    reviewStatus === 'pending' ? 'hourglass_top'
      : reviewStatus === 'draft' ? 'edit_note'
        : reviewStatus === 'attacked' ? 'priority_high'
          : 'gpp_bad'

  return (
    <div>
      {/* Lead Header */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-5">
            <div className="w-16 h-16 rounded-xl bg-primary/5 border border-primary/10 shadow-sm flex items-center justify-center">
              <Icon name="trending_up" className="text-2xl text-primary" />
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
                    <Icon name={reviewBannerIcon} className="text-sm" />
                    {reviewCfg.label}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-sm text-slate-500">
                {lead.company_name && (
                  <span className="flex items-center gap-1">
                    <Icon name="business" className="text-sm" /> {lead.company_name}
                  </span>
                )}
                {lead.industry && (
                  <span className="flex items-center gap-1">
                    <Icon name="factory" className="text-sm" />
                    {industryDict.options.find(o => o.value === lead.industry)?.label || lead.industry}
                  </span>
                )}
                {formatLocation(lead) && (
                  <span className="flex items-center gap-1">
                    <Icon name="location_on" className="text-sm" /> {formatLocation(lead)}
                  </span>
                )}
              </div>
            </div>
          </div>
          <Space>
            {siblingNav.hasNav && (
              <RecordPrevNextNav
                index={siblingNav.index}
                total={siblingNav.total}
                disabled={siblingNav.busy}
                onPrev={siblingNav.goPrev}
                onNext={siblingNav.goNext}
              />
            )}
            {/* 流程激活看 WF 终态，与线索是否已转化无关（已转化单也可重开审批） */}
            {canActivateFlow && wfInstance?.can_activate && wfInstance.id && (
              <Button
                icon={<ThunderboltOutlined />}
                onClick={() => setActivateOpen(true)}
              >
                激活流程
              </Button>
            )}
            {canEditLead && (
              <Button icon={<EditOutlined />} onClick={() => navigate(
                isReviseTask && myTask
                  ? leadReviseEditPath(id!, myTask.task_id)
                  : `/leads/${id}/edit`,
              )}>编辑</Button>
            )}
            {canOperate && (
              <>
                {canSubmitApproval && (
                  <Button type="primary" icon={<AuditOutlined />} loading={submitting} onClick={handleSubmitApproval}>
                    提交审批
                  </Button>
                )}
                {reviewApproved && !isOwnerConfirmTask && (
                  <Button
                    type="primary"
                    onClick={handleQualify}
                  >
                    <Icon name="check_circle" className="text-sm mr-1" />
                    转商机
                  </Button>
                )}
                <Button danger onClick={handleDiscard}>
                  <Icon name="block" className="text-sm mr-1" />
                  废弃
                </Button>
                {canDeleteLead && (
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
                )}
              </>
            )}
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
                      <Icon name={step.icon} className="text-lg" />
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

      {/* 待我处理：修订重提 / 情报四态 / 业务员确认 */}
      {isOwnerConfirmTask && (
        <div className="rounded-xl border border-amber-300 bg-amber-50/60 p-4 mb-6">
          <LeadOwnerConfirmActions
            leadId={id!}
            taskId={myTask!.task_id}
            onDone={() => {
              setMyTask(null)
              void fetchLead()
              if (id) void loadWf(id)
            }}
          />
        </div>
      )}
      {isReviseTask && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 mb-6 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Icon name="edit_note" className="text-amber-600" />
            <div>
              <div className="text-sm font-bold text-amber-800">请修改后重新提交</div>
              <div className="text-sm text-slate-600 mt-1">
                流程已撤回，请像新建时一样完善申报信息，确认无误后再提交审批。评估结论仍由信息情报部在审批时填写。
              </div>
            </div>
          </div>
          <Space>
            {canEditLead && (
              <Button icon={<EditOutlined />} onClick={() => navigate(
                isReviseTask && myTask
                  ? leadReviseEditPath(id!, myTask.task_id)
                  : `/leads/${id}/edit`,
              )}>编辑</Button>
            )}
            <Button type="primary" icon={<AuditOutlined />} loading={submitting} onClick={handleResubmitRevise}>
              重新提交
            </Button>
          </Space>
        </div>
      )}
      {isIntelTask && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 mb-6">
          <div className="flex items-center gap-3 mb-4">
            <Icon name="approval" className="text-primary" />
            <div>
              <div className="text-sm font-bold text-slate-900">该线索待您审批</div>
              <div className="text-sm text-slate-500">{myTask?.node_name || myTask?.title || '信息情报部审批'}</div>
            </div>
          </div>
          <LeadIntelReviewForm
            leadId={id!}
            taskId={myTask!.task_id}
            initialNewness={lead.customer_newness}
            initialOpinion={lead.review_opinion}
            initialReturnReason={lead.reject_reason}
            initialAssessRemark={lead.assess_remark}
            onDone={(decision) => {
              if (decision === 'draft') {
                void fetchLead()
              } else {
                setMyTask(null)
                void fetchLead()
                if (id) void loadWf(id)
              }
            }}
          />
        </div>
      )}

      {/* Review status banner：修订中用上方「请修改后重新提交」，不再叠「待审」条 */}
      {reviewCfg && !isReviseTask && (
        <div className={`rounded-xl border ${reviewCfg.border} ${reviewCfg.bg} p-4 mb-6 flex items-start gap-3`}>
          <Icon name={reviewBannerIcon} className={`${reviewCfg.text}`} />
          <div className="flex-1">
            <div className={`text-sm font-bold ${reviewCfg.text}`}>
              {reviewStatus === 'draft' && (lead.reject_reason ? '线索已回退，待修改后重提' : '线索草稿未提交')}
              {reviewStatus === 'pending' && '线索待信息情报部内勤审核'}
              {reviewStatus === 'rejected' && '线索已驳回'}
              {reviewStatus === 'attacked' && '线索已标记为袭击'}
            </div>
            <div className="text-sm text-slate-600 mt-1">
              {reviewStatus === 'draft' && (
                <>
                  {lead.reject_reason
                    ? `情报已回退，请按意见修改后重新提交。回退原因：${lead.reject_reason}`
                    : '完善申报信息后提交审批，可在右侧查看流程动态。'}
                </>
              )}
              {reviewStatus === 'pending' && '审核收录后方可转商机。'}
              {reviewStatus === 'rejected' && (
                <>
                  项目不可再报备，请勿继续跟进。
                  {lead.reject_reason ? ` 驳回原因：${lead.reject_reason}` : ''}
                </>
              )}
              {reviewStatus === 'attacked' && '袭击状态不可转商机。'}
            </div>
          </div>
          {canSubmitApproval && (
            <Button size="small" type="primary" loading={submitting} onClick={handleSubmitApproval}>提交审批</Button>
          )}
        </div>
      )}

      {/* 收录后引导负责人自行决定是否转化 */}
      {reviewApproved && canOperate && !isOwnerConfirmTask && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 mb-6 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Icon name="verified" className="text-emerald-600" />
            <div>
              <div className="text-sm font-bold text-emerald-700">信息情报部已收录</div>
              <div className="text-sm text-slate-600 mt-1">
                需要出方案报价请确认转化商机；如为拟建项目，目前不需要出方案报价，请不要转化为商机。可在「动态」中继续添加互动记录。
              </div>
            </div>
          </div>
          <Button type="primary" onClick={handleQualify}>确认是否转商机</Button>
        </div>
      )}

      {/* 180 天重激活跟进 */}
      {reactFollowTodo && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 mb-6 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Icon name="schedule" className="text-amber-600" />
            <div>
              <div className="text-sm font-bold text-amber-800">
                180天重激活待办：{myReactTask?.node_name || '填写跟进'}
              </div>
              <div className="text-sm text-slate-600 mt-1">
                在流程待办中填写项目近况 / 跟进进度 / 实地拜访与项目状态。
                仅「进行中」进入内勤与情报审；中标/已签合同等直接结束本轮。
                {lead.reactivation_round ? `（第 ${lead.reactivation_round} 轮）` : ''}
              </div>
            </div>
          </div>
          {canSubmitReact && (
            <Button type="primary" onClick={openReactivationDrawer}>办理待办</Button>
          )}
        </div>
      )}
      {reactIntelTodo && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-4 mb-6 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Icon name="approval" className="text-primary" />
            <div>
              <div className="text-sm font-bold text-slate-900">180天激活待您情报审批</div>
              <div className="text-sm text-slate-500">{myReactTask?.node_name || '180天项目激活审批'}</div>
            </div>
          </div>
          <Button type="primary" onClick={openReactivationDrawer}>办理审批</Button>
        </div>
      )}
      {reactTodo && !reactFollowTodo && !reactIntelTodo && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 mb-6 flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <Icon name="schedule" className="text-amber-600" />
            <div>
              <div className="text-sm font-bold text-amber-800">
                {reactStatus === 'awaiting_reporter' ? '线索已满周期，请申报人更新近况' : '请填表人核对并提交情报审批'}
              </div>
              <div className="text-sm text-slate-600 mt-1">
                填写项目近况 / 跟进进度 / 实地拜访与项目状态。仅「进行中」进入内勤与情报审；
                中标/已签合同等直接结束本轮；暂缓/取消/落标不再自动重激活。
                {lead.reactivation_round ? `（第 ${lead.reactivation_round} 轮）` : ''}
              </div>
            </div>
          </div>
          {canSubmitReact && (
            <Button type="primary" onClick={openReactivationDrawer}>办理待办</Button>
          )}
        </div>
      )}
      {reactStatus === 'pending_review' && (
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 mb-6 flex items-start gap-3">
          <Icon name="hourglass_top" className="text-sky-600" />
          <div>
            <div className="text-sm font-bold text-sky-800">重激活已提交情报审批</div>
            <div className="text-sm text-slate-600 mt-1">收录或袭击后将重新开始 180 天计时。</div>
          </div>
        </div>
      )}
      {reactStatus === 'closed' && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 mb-6 flex items-start gap-3">
          <Icon name="block" className="text-slate-500" />
          <div>
            <div className="text-sm font-bold text-slate-700">重激活本轮已结束</div>
            <div className="text-sm text-slate-600 mt-1">
              项目状态：{lead.report_project_status || '-'}（暂缓/取消/落标不再自动重激活）
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        <div className="lg:col-span-9">
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
                      <div>
                        <div className="relative mb-3 flex items-center overflow-hidden rounded-sm bg-teal-600 px-3 py-2 text-white">
                          <span className="text-[13px] font-semibold">线索信息</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">项目号</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.lead_code || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">公司名称</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.company_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">申报人</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.reporter_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">部门</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.department_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">申报时间</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.reported_at ? new Date(lead.reported_at).toLocaleString('zh-CN') : '-'}
                            </div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">联系人</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.contact_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">联系电话</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.contact_phone || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">联系邮箱</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.contact_email || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">渠道来源</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.source ? (sourceLabels[lead.source] || lead.source) : '-'}
                            </div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">业务日期</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.biz_date || '-'}</div>
                          </div>
                          <div className="sm:col-span-2 xl:col-span-3 p-4 bg-primary/5 rounded-xl border border-primary/20">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-primary/70 mb-1">线索内容</div>
                            <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">
                              {lead.demand_summary || lead.title || '-'}
                            </div>
                          </div>
                          {(lead.converted_project_id || lead.converted_customer_id) && (
                            <div className="sm:col-span-2 xl:col-span-3 p-4 bg-slate-50 rounded-xl border border-slate-100">
                              <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">转化结果</div>
                              {lead.converted_project_id ? (
                                <a
                                  onClick={() => navigate(`/projects/${lead.converted_project_id}`)}
                                  className="text-primary font-bold text-sm hover:underline cursor-pointer"
                                >
                                  查看商机 {lead.converted_project_code || ''}
                                </a>
                              ) : lead.converted_customer_id ? (
                                <a
                                  onClick={() => navigate(`/customers/${lead.converted_customer_id}`)}
                                  className="text-primary font-bold text-sm hover:underline cursor-pointer"
                                >
                                  查看历史转化客户
                                </a>
                              ) : null}
                            </div>
                          )}
                        </div>
                        <div className="mt-4">
                          <EntityCustomFields entityType="lead" value={lead.custom_fields_json || {}} readOnly />
                        </div>
                        <div className="mt-4">
                          <div className="relative mb-3 flex items-center overflow-hidden rounded-sm bg-teal-600 px-3 py-2 text-white">
                            <span className="text-[13px] font-semibold">附件</span>
                          </div>
                          <AttachmentPanel bizType="lead" bizId={id!} />
                        </div>
                      </div>

                      <div>
                        <div className="relative mb-3 flex items-center overflow-hidden rounded-sm bg-teal-600 px-3 py-2 text-white">
                          <span className="text-[13px] font-semibold">申报信息（创建时填写）</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">来源</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.category ? categoryLabels[lead.category] : '-'}
                            </div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">客户类型</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.customer_type
                                ? (customerTypeDict.options.find(o => o.value === lead.customer_type)?.label || lead.customer_type)
                                : '-'}
                            </div>
                          </div>
                          <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">项目名称</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.title || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">公司名称</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.company_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">行业</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.industry
                                ? (industryDict.options.find(o => o.value === lead.industry)?.label || lead.industry)
                                : '-'}
                            </div>
                          </div>
                          <div className="sm:col-span-2 p-4 bg-primary/5 rounded-xl border border-primary/20">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-primary/70 mb-1">线索内容（备注1）</div>
                            <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">
                              {lead.demand_summary || '-'}
                            </div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">是否内部冲突</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.has_internal_conflict || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">中标情况</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.bid_result || '-'}</div>
                          </div>
                          {lead.has_internal_conflict === '是' && (
                            <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                              <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">请示部门经理的结果</div>
                              <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">{lead.conflict_note || '-'}</div>
                            </div>
                          )}
                          {lead.bid_fail_reason && (
                            <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                              <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">原因</div>
                              <div className="text-sm font-semibold text-slate-700">{lead.bid_fail_reason}</div>
                            </div>
                          )}
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">国别 / 地址</div>
                            <div className="text-sm font-semibold text-slate-700">{formatArea(lead) || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">详细地址</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.region || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">委托状态</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.entrust_status || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">委托开具日期</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.entrust_issued_at ? new Date(lead.entrust_issued_at).toLocaleString('zh-CN') : '-'}
                            </div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">委托期限</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.entrust_term || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">填表人</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.created_by_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">部门</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.department_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">申报人</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.reporter_name || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">申报时间</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.reported_at ? new Date(lead.reported_at).toLocaleString('zh-CN') : '-'}
                            </div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">项目动态</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.project_activity || '-'}</div>
                          </div>
                        </div>
                      </div>

                      <div>
                        <div className="relative mb-3 flex items-center overflow-hidden rounded-sm bg-teal-600 px-3 py-2 text-white">
                          <span className="text-[13px] font-semibold">业务反馈项目详情（跟进时填写）</span>
                        </div>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">项目近况</div>
                            <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">{lead.project_recent || '-'}</div>
                          </div>
                          <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">跟进进度</div>
                            <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">{lead.follow_progress || '-'}</div>
                          </div>
                          <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">实地拜访情况</div>
                            <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">{lead.site_visit || '-'}</div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">项目状态</div>
                            <div className="text-sm font-semibold text-slate-700">{lead.report_project_status || '-'}</div>
                          </div>
                        </div>
                      </div>

                      <div>
                        <div className="relative mb-3 flex items-center overflow-hidden rounded-sm bg-teal-600 px-3 py-2 text-white">
                          <span className="text-[13px] font-semibold">180天项目激活内容查看</span>
                        </div>
                        <Table
                          size="small"
                          rowKey="id"
                          loading={reactRecordsLoading}
                          pagination={false}
                          scroll={{ x: 960 }}
                          locale={{ emptyText: '暂无激活记录' }}
                          dataSource={reactRecords}
                          onRow={(rec) => ({
                            onClick: () => navigate(`/lead-reactivations/${rec.id}`),
                            className: 'cursor-pointer hover:bg-slate-50',
                          })}
                          columns={[
                            {
                              title: '原项目编号',
                              dataIndex: 'original_lead_code',
                              width: 120,
                              render: (v: string | null) => v || '-',
                            },
                            {
                              title: '轮次',
                              dataIndex: 'round_no',
                              width: 64,
                              render: (v: number) => (v != null ? `第${v}轮` : '-'),
                            },
                            {
                              title: '项目状态',
                              dataIndex: 'report_project_status',
                              width: 88,
                              render: (v: string | null) => v || '-',
                            },
                            {
                              title: '项目近况',
                              dataIndex: 'project_recent',
                              width: 160,
                              ellipsis: true,
                              render: (v: string | null) => v || '-',
                            },
                            {
                              title: '跟进进度',
                              dataIndex: 'follow_progress',
                              width: 160,
                              ellipsis: true,
                              render: (v: string | null) => v || '-',
                            },
                            {
                              title: '实地拜访情况',
                              dataIndex: 'site_visit',
                              width: 160,
                              ellipsis: true,
                              render: (v: string | null) => v || '-',
                            },
                            {
                              title: '提交人',
                              dataIndex: 'submitted_by_name',
                              width: 88,
                              render: (v: string | null) => v || '-',
                            },
                            {
                              title: '提交时间',
                              dataIndex: 'submitted_at',
                              width: 160,
                              render: (v: string | null) =>
                                v ? new Date(v).toLocaleString('zh-CN') : '-',
                            },
                          ]}
                        />
                      </div>

                      {/* 评估结论：仅情报已裁定后展示；草稿/待审/撤回修订时与新建一致不展示 */}
                      {(reviewApproved || reviewStatus === 'rejected' || reviewStatus === 'attacked') && (
                      <div>
                        <div className="relative mb-3 flex items-center overflow-hidden rounded-sm bg-teal-600 px-3 py-2 text-white">
                          <span className="text-[13px] font-semibold">评估信息（审批时填写）</span>
                        </div>
                        <p className="mb-3 text-xs text-slate-400">
                          由信息情报部在审批待办中填写：新/老客户、最终状态、驳回原因、备注2
                        </p>
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">客户类型（新/老）</div>
                            <div className="text-sm font-semibold text-slate-700">
                              {lead.customer_newness
                                ? (customerNewnessLabels[lead.customer_newness] || lead.customer_newness)
                                : '-'}
                            </div>
                          </div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">项目最终状态</div>
                            <div className="text-sm font-semibold">
                              {(() => {
                                const finalLabels: Record<string, { label: string; cls: string }> = {
                                  draft: { label: '草稿', cls: 'text-slate-500' },
                                  approved: { label: '收录', cls: 'text-emerald-600' },
                                  rejected: { label: '已驳回', cls: 'text-red-600' },
                                  pending: { label: '待审', cls: 'text-amber-600' },
                                  attacked: { label: '袭击', cls: 'text-orange-600' },
                                }
                                const f = finalLabels[reviewStatus] || { label: reviewStatus, cls: 'text-slate-700' }
                                return <span className={f.cls}>{f.label}</span>
                              })()}
                            </div>
                            {reviewStatus === 'rejected' && lead.reject_reason && (
                              <div className="mt-2 text-xs text-red-500 leading-relaxed">驳回原因：{lead.reject_reason}</div>
                            )}
                          </div>
                          <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                            <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">备注2</div>
                            <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">{lead.assess_remark || '-'}</div>
                          </div>
                          {lead.review_opinion && (
                            <div className="sm:col-span-2 p-4 bg-slate-50 rounded-xl border border-slate-100">
                              <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-1">操作意见</div>
                              <div className="text-sm font-semibold text-slate-700 whitespace-pre-wrap">{lead.review_opinion}</div>
                            </div>
                          )}
                        </div>
                      </div>
                      )}

                      {lead.remark && (
                        <div>
                          <div className="text-[12px] font-bold uppercase tracking-wider text-slate-400 mb-2">其他备注</div>
                          <div className="p-4 bg-slate-50 rounded-xl border border-slate-100 text-sm text-slate-600 leading-relaxed whitespace-pre-wrap">
                            {lead.remark}
                          </div>
                        </div>
                      )}

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
                        defaultContactName={lead.contact_name} onCreated={handleFollowUpCreated}
                        allowCreate={allowFollowActivity} />
                    </div>
                  ),
                },
              ]}
            />
          </div>
        </div>

        {/* Right: AI 评分 + 流程动态 + 智能洞察 */}
        <div className="lg:col-span-3 space-y-6">
          <ScoreGauge score={lead.score ?? 0} />
          <div
            className="rounded-xl border border-slate-200 shadow-sm overflow-hidden bg-white"
            style={{ height: 'min(520px, calc(100vh - 280px))', minHeight: 360 }}
          >
            <WfFlowDynamics
              steps={wfInstance?.flow_steps || []}
              comments={wfInstance?.comments || []}
              onSubmitComment={wfInstance ? handleWfComment : undefined}
              commenting={wfCommenting}
              dataLog={id ? { resourceType: 'lead', resourceId: id } : undefined}
            />
          </div>
          <div className="bg-blue-50/50 rounded-xl border border-blue-100 shadow-sm p-5">
            <div className="flex items-center gap-2 mb-5">
              <Icon name="auto_awesome" className="text-primary" />
              <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-900">AI 智能洞察</h3>
            </div>

            <div className="space-y-4">
              {/* Score Analysis */}
              <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <Icon name="analytics" className="text-primary text-sm" />
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
                    <Icon name="lightbulb" className="text-amber-500 text-sm" />
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
              {(lead.converted_project_id || lead.status === 'qualified') && (
                <div className="bg-white p-4 rounded-xl border border-emerald-100 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <Icon name="check_circle" className="text-emerald-500 text-sm" />
                    <span className="text-sm font-bold text-slate-800">已转化</span>
                  </div>
                  <p className="text-sm text-slate-500 leading-relaxed mb-3">
                    {lead.converted_project_id
                      ? '该线索已转为商机，请在商机管理中关联对应客户。'
                      : '该线索已标记为已转化。'}
                  </p>
                  {lead.converted_project_id && (
                    <button
                      onClick={() => navigate(`/projects/${lead.converted_project_id}`)}
                      className="w-full py-2 bg-emerald-600 text-white rounded-lg text-sm font-bold hover:bg-emerald-700 transition-colors"
                    >
                      查看商机详情
                    </button>
                  )}
                </div>
              )}

            </div>
          </div>
        </div>
      </div>

      <WfActivateFlowModal
        open={activateOpen}
        instanceId={wfInstance?.id}
        nodes={wfInstance?.activate_nodes}
        onClose={() => setActivateOpen(false)}
        onDone={() => {
          if (id) void loadWf(id)
        }}
      />
      {wfDrawerNode}
    </div>
  )
}
