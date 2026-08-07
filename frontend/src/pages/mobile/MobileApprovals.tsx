// 移动端审批中心：能力对齐 PC /approvals（待办/发起/已办/抄送/代理/历史/统计）。
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { DatePicker, Input, Modal, Select, message } from 'antd'
import dayjs from 'dayjs'
import MobileIcon from '@/components/MobileIcon'
import PersonField from '@/components/lowcode/fields/PersonField'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { approvalApi } from '@/api/approval'
import { workflowApi, type WfAgent } from '@/api/lowcodeWorkflow'
import {
  fetchUnifiedPending, fetchUnifiedMine, fetchUnifiedDone, decideUnified,
  type UnifiedPendingItem, type UnifiedMineItem, type UnifiedDoneItem,
} from '@/api/unifiedApprovals'
import type { ApprovalFlowItem } from '@/api/types'
import { approvalBizTypeLabels, approvalStatusLabels } from '@/constants/labels'
import { WF_STATUS } from '@/utils/lowcodeWorkflowLabels'

type TabKey = 'pending' | 'mine' | 'done' | 'cc' | 'agents' | 'all' | 'stats'

type CcItem = {
  cc_id: string
  process_instance_id: string
  title?: string
  status?: string
  biz_type?: string
  process_name?: string
  initiator_name?: string
  is_read: boolean
  created_at?: string
}

const TABS: { key: TabKey; label: string }[] = [
  { key: 'pending', label: '待我审批' },
  { key: 'mine', label: '我发起的' },
  { key: 'done', label: '已办' },
  { key: 'cc', label: '抄送我的' },
  { key: 'agents', label: '我的代理' },
  { key: 'all', label: '所有审批' },
  { key: 'stats', label: '统计' },
]

const STATUS_CLS: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-600',
  approved: 'bg-emerald-50 text-emerald-600',
  rejected: 'bg-red-50 text-red-600',
  withdrawn: 'bg-slate-100 text-slate-500',
  transferred: 'bg-blue-50 text-blue-600',
  returned: 'bg-orange-50 text-orange-600',
}

function bizLabel(t?: string | null) {
  if (!t) return '审批'
  return approvalBizTypeLabels[t] || t
}

function statusMeta(status: string, engine?: string) {
  if (engine === 'wf' || WF_STATUS[status]) {
    const s = WF_STATUS[status]
    return { text: s?.text || approvalStatusLabels[status] || status, cls: s?.cls || 'bg-slate-100 text-slate-500' }
  }
  return {
    text: approvalStatusLabels[status] || status,
    cls: STATUS_CLS[status] || 'bg-slate-100 text-slate-500',
  }
}

function doneLabel(status: string) {
  if (status === 'approved') return '已通过'
  if (status === 'rejected') return '已驳回'
  if (status === 'returned') return '已退回'
  if (status === 'transferred') return '已转交'
  return status
}

function fmtTime(v?: string) {
  if (!v) return ''
  return new Date(v).toLocaleString('zh-CN')
}

export default function MobileApprovals() {
  usePageTitle('审批中心')
  const navigate = useNavigate()
  const userId = useAuthStore((s) => s.user?.id)

  const [tab, setTab] = useState<TabKey>('pending')
  const [loading, setLoading] = useState(true)
  const [tabLoading, setTabLoading] = useState(false)

  const [pending, setPending] = useState<UnifiedPendingItem[]>([])
  const [mine, setMine] = useState<UnifiedMineItem[]>([])
  const [done, setDone] = useState<UnifiedDoneItem[]>([])
  const [cc, setCc] = useState<CcItem[]>([])
  const [agents, setAgents] = useState<WfAgent[]>([])
  const [allFlows, setAllFlows] = useState<ApprovalFlowItem[]>([])
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)

  const [filterBizType, setFilterBizType] = useState('')
  const [selectMode, setSelectMode] = useState(false)
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [busy, setBusy] = useState(false)

  const [withdrawOpen, setWithdrawOpen] = useState(false)
  const [withdrawId, setWithdrawId] = useState('')
  const [withdrawEngine, setWithdrawEngine] = useState<'legacy' | 'wf'>('legacy')
  const [withdrawReason, setWithdrawReason] = useState('')

  const [agentOpen, setAgentOpen] = useState(false)
  const [agentUserId, setAgentUserId] = useState<unknown>(undefined)
  const [agentRange, setAgentRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
  const [agentNote, setAgentNote] = useState('')

  const openDetail = useCallback((engine: 'legacy' | 'wf', instanceId: string, taskId?: string) => {
    if (!instanceId) {
      message.warning('缺少流程实例，无法打开')
      return
    }
    if (engine === 'wf') {
      navigate(
        taskId
          ? `/m/lowcode/approvals/${instanceId}?task=${encodeURIComponent(taskId)}`
          : `/m/lowcode/approvals/${instanceId}`,
      )
      return
    }
    navigate(`/m/approvals/${instanceId}`)
  }, [navigate])

  const loadPending = useCallback(async () => {
    setLoading(true)
    try {
      const u = await fetchUnifiedPending()
      setPending(u.items || [])
    } catch {
      message.error('加载失败')
    } finally {
      setLoading(false)
    }
  }, [])

  const loadAllFlows = useCallback(async () => {
    setTabLoading(true)
    try {
      const f = await approvalApi.list({ pageNo: 1, pageSize: 50 })
      setAllFlows(f.data?.items || [])
    } finally {
      setTabLoading(false)
    }
  }, [])

  const loadMine = useCallback(async () => {
    setTabLoading(true)
    try { setMine(await fetchUnifiedMine(userId)) }
    finally { setTabLoading(false) }
  }, [userId])

  const loadDone = useCallback(async () => {
    setTabLoading(true)
    try { setDone(await fetchUnifiedDone(userId)) }
    finally { setTabLoading(false) }
  }, [userId])

  const loadCc = useCallback(async () => {
    setTabLoading(true)
    try {
      const r = await workflowApi.cc({ pageNo: 1, pageSize: 100 })
      setCc((r.data?.items || []) as CcItem[])
    } finally { setTabLoading(false) }
  }, [])

  const loadAgents = useCallback(async () => {
    setTabLoading(true)
    try {
      const r = await workflowApi.listAgents()
      setAgents(r.data || [])
    } finally { setTabLoading(false) }
  }, [])

  const loadStats = useCallback(async () => {
    setTabLoading(true)
    try {
      const r = await approvalApi.statistics()
      setStats(r.data)
    } finally { setTabLoading(false) }
  }, [])

  useEffect(() => { void loadPending() }, [loadPending])

  const onTabChange = (key: TabKey) => {
    setTab(key)
    setSelectMode(false)
    setSelectedKeys([])
    if (key === 'mine') void loadMine()
    if (key === 'done') void loadDone()
    if (key === 'cc') void loadCc()
    if (key === 'agents') void loadAgents()
    if (key === 'stats') void loadStats()
    if (key === 'all') void loadAllFlows()
  }

  const filteredPending = useMemo(() => {
    if (!filterBizType) return pending
    return pending.filter((p) => p.bizType === filterBizType)
  }, [pending, filterBizType])

  const pendingBizTypes = useMemo(() => {
    const types = new Set(pending.map((p) => p.bizType).filter(Boolean) as string[])
    return Array.from(types).map((t) => ({ value: t, label: bizLabel(t) }))
  }, [pending])

  const handleUrge = async (instanceId: string) => {
    try {
      const r = await workflowApi.urge(instanceId)
      message.success(`已催办 ${r.data?.notified ?? 0} 人`)
    } catch (e) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.warning(msg || '催办失败')
    }
  }

  const handleWithdraw = async () => {
    setBusy(true)
    try {
      if (withdrawEngine === 'wf') await workflowApi.withdraw(withdrawId)
      else await approvalApi.withdraw(withdrawId, { reason: withdrawReason || undefined })
      message.success('审批已撤回')
      setWithdrawOpen(false)
      await loadPending()
      if (tab === 'mine') await loadMine()
    } catch {
      message.error('撤回失败')
    } finally {
      setBusy(false)
    }
  }

  const handleResubmit = async (instanceId: string, engine: 'legacy' | 'wf') => {
    setBusy(true)
    try {
      if (engine === 'wf') await workflowApi.resubmit(instanceId)
      else await approvalApi.resubmit(instanceId, {})
      message.success('已重新发起审批')
      await loadPending()
      if (tab === 'mine') await loadMine()
    } catch {
      message.error('重新发起失败')
    } finally {
      setBusy(false)
    }
  }

  const saveAgent = async () => {
    if (!agentUserId) { message.error('请选择代理人'); return }
    if (!agentRange?.[0] || !agentRange?.[1]) { message.error('请选择代理时间段'); return }
    setBusy(true)
    try {
      await workflowApi.createAgent({
        agent_id: String(agentUserId),
        start_time: agentRange[0].toISOString(),
        end_time: agentRange[1].toISOString(),
        note: agentNote || undefined,
      })
      message.success('已设置代理')
      setAgentOpen(false)
      setAgentUserId(undefined)
      setAgentRange(null)
      setAgentNote('')
      await loadAgents()
    } catch {
      message.error('设置失败')
    } finally {
      setBusy(false)
    }
  }

  const handleBulk = (action: 'approve' | 'reject') => {
    if (!selectedKeys.length) { message.warning('请选择审批任务'); return }
    const selected = pending.filter((p) => selectedKeys.includes(p.key))
    const legacy = selected.filter((p) => p.engine === 'legacy')
    const wf = selected.filter((p) => p.engine === 'wf')
    if (wf.length && !legacy.length) {
      message.info('流程引擎待办请逐条打开处理（可能需填写节点字段）')
      return
    }
    const label = action === 'approve' ? '通过' : '驳回'
    Modal.confirm({
      title: `批量${label}确认`,
      content: wf.length
        ? `将${label} ${legacy.length} 条经典待办；另有 ${wf.length} 条流程待办需单独处理。`
        : `确定要${label} ${legacy.length} 条审批任务吗？`,
      onOk: async () => {
        setBusy(true)
        try {
          let ok = 0
          let fail = 0
          for (const item of legacy) {
            try {
              await decideUnified(item, action)
              ok += 1
            } catch { fail += 1 }
          }
          message.success(`完成：成功 ${ok}${fail ? `，失败 ${fail}` : ''}`)
          setSelectedKeys([])
          setSelectMode(false)
          await loadPending()
        } finally {
          setBusy(false)
        }
      },
    })
  }

  const empty = (text: string) => (
    <div className="text-center py-16">
      <MobileIcon name="task_alt" className="text-slate-200 mb-2" style={{ fontSize: 48 }} />
      <p className="text-sm text-slate-400 mt-2">{text}</p>
    </div>
  )

  const spinner = (
    <div className="flex items-center justify-center h-48">
      <MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 28 }} />
    </div>
  )

  return (
    <div style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 80px)' }}>
      <div className="flex items-center justify-between mb-3">
        <button type="button" onClick={() => navigate(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0">
          <MobileIcon name="arrow_back_ios" />
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">审批中心</h2>
        <div className="w-10" />
      </div>

      <div className="flex gap-1 overflow-x-auto pb-2 mb-3 -mx-1 px-1 scrollbar-none">
        {TABS.map((t) => {
          const active = tab === t.key
          const count = t.key === 'pending' ? pending.length : 0
          return (
            <button
              key={t.key}
              type="button"
              onClick={() => onTabChange(t.key)}
              className={`shrink-0 px-3 h-8 rounded-full text-sm font-bold border-0 cursor-pointer ${
                active ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
              }`}
            >
              {t.label}
              {count > 0 && t.key === 'pending' ? ` ${count}` : ''}
            </button>
          )
        })}
      </div>

      {tab === 'pending' && (
        <>
          {pending.length > 0 && (
            <div className="flex flex-wrap items-center gap-2 mb-3">
              <Select
                allowClear
                size="small"
                placeholder="业务类型"
                value={filterBizType || undefined}
                onChange={(v) => setFilterBizType(v || '')}
                options={pendingBizTypes}
                style={{ minWidth: 120 }}
              />
              <button
                type="button"
                onClick={() => { setSelectMode((s) => !s); setSelectedKeys([]) }}
                className="text-sm font-bold text-primary bg-transparent border-0 cursor-pointer p-0"
              >
                {selectMode ? '取消多选' : '多选'}
              </button>
              {selectMode && (
                <>
                  <button type="button" disabled={busy || !selectedKeys.length} onClick={() => handleBulk('approve')}
                    className="text-sm font-bold text-emerald-600 bg-transparent border-0 cursor-pointer p-0 disabled:opacity-40">批量通过</button>
                  <button type="button" disabled={busy || !selectedKeys.length} onClick={() => handleBulk('reject')}
                    className="text-sm font-bold text-red-600 bg-transparent border-0 cursor-pointer p-0 disabled:opacity-40">批量驳回</button>
                </>
              )}
            </div>
          )}
          {loading ? spinner : filteredPending.length === 0 ? empty('暂无待审批事项') : (
            <div className="space-y-3">
              {filteredPending.map((item) => {
                const overdue = item.createdAt
                  ? (Date.now() - new Date(item.createdAt).getTime()) / 3600000 > 24
                  : false
                const selected = selectedKeys.includes(item.key)
                return (
                  <div
                    key={item.key}
                    className={`bg-white rounded-xl border shadow-sm p-4 ${selected ? 'border-primary' : 'border-slate-100'}`}
                    onClick={() => {
                      if (selectMode) {
                        setSelectedKeys((prev) => prev.includes(item.key) ? prev.filter((k) => k !== item.key) : [...prev, item.key])
                        return
                      }
                      openDetail(item.engine, item.instanceId || '', item.taskId)
                    }}
                  >
                    <div className="flex items-start gap-3">
                      {selectMode && (
                        <div className={`mt-1 w-5 h-5 rounded border flex items-center justify-center shrink-0 ${selected ? 'bg-primary border-primary text-white' : 'border-slate-300'}`}>
                          {selected && <MobileIcon name="check" style={{ fontSize: 14 }} />}
                        </div>
                      )}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="text-sm font-bold text-slate-900 truncate">{item.title || '审批'}</h4>
                          <span className="text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 bg-amber-50 text-amber-600">待审批</span>
                        </div>
                        <div className="text-sm text-slate-500 mt-1 truncate">
                          {bizLabel(item.bizType)}
                          {item.subtitle ? ` · ${item.subtitle}` : ''}
                          {item.engine === 'wf' ? ' · 流程' : ' · 经典'}
                        </div>
                        {item.createdAt && (
                          <div className={`text-[12px] mt-1.5 ${overdue ? 'text-red-500 font-bold' : 'text-slate-400'}`}>
                            {fmtTime(item.createdAt)}{overdue ? ' · 超时' : ''}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </>
      )}

      {tab === 'mine' && (
        tabLoading ? spinner : mine.length === 0 ? empty('暂无发起的审批') : (
          <div className="space-y-3">
            {mine.map((item) => {
              const st = statusMeta(item.status, item.engine)
              const canWithdraw = (item.engine === 'wf' && item.status === 'running')
                || (item.engine === 'legacy' && item.status === 'pending')
              const canResubmit = (item.engine === 'wf' && (item.status === 'withdrawn' || item.status === 'rejected'))
                || (item.engine === 'legacy' && (item.status === 'rejected' || item.status === 'withdrawn'))
              return (
                <div key={item.key} className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                  <div
                    className="cursor-pointer"
                    onClick={() => openDetail(item.engine, item.instanceId)}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <h4 className="text-sm font-bold text-slate-900 truncate">{item.title}</h4>
                      <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${st.cls}`}>{st.text}</span>
                    </div>
                    <div className="text-sm text-slate-500 mt-1">
                      {bizLabel(item.bizType)}{item.subtitle ? ` · ${item.subtitle}` : ''}
                    </div>
                    {item.createdAt && <div className="text-[12px] text-slate-400 mt-1.5">{fmtTime(item.createdAt)}</div>}
                  </div>
                  <div className="flex gap-3 mt-3 pt-2 border-t border-slate-50">
                    <button type="button" className="text-sm font-bold text-primary bg-transparent border-0 p-0"
                      onClick={() => openDetail(item.engine, item.instanceId)}>查看</button>
                    {item.engine === 'wf' && item.status === 'running' && (
                      <button type="button" className="text-sm font-bold text-amber-600 bg-transparent border-0 p-0"
                        onClick={() => handleUrge(item.instanceId)}>催办</button>
                    )}
                    {canWithdraw && (
                      <button type="button" className="text-sm font-bold text-slate-600 bg-transparent border-0 p-0"
                        onClick={() => {
                          setWithdrawId(item.instanceId)
                          setWithdrawEngine(item.engine)
                          setWithdrawReason('')
                          setWithdrawOpen(true)
                        }}>撤回</button>
                    )}
                    {canResubmit && (
                      <button type="button" disabled={busy} className="text-sm font-bold text-emerald-600 bg-transparent border-0 p-0 disabled:opacity-40"
                        onClick={() => handleResubmit(item.instanceId, item.engine)}>重新发起</button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )
      )}

      {tab === 'done' && (
        tabLoading ? spinner : done.length === 0 ? empty('暂无已办记录') : (
          <div className="space-y-3">
            {done.map((item) => (
              <div
                key={item.key}
                className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer"
                onClick={() => openDetail(item.engine, item.instanceId, item.taskId)}
              >
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-bold text-slate-900 truncate">{item.title}</h4>
                  <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${STATUS_CLS[item.status] || 'bg-slate-100 text-slate-500'}`}>
                    {doneLabel(item.status)}
                  </span>
                </div>
                <div className="text-sm text-slate-500 mt-1">
                  {bizLabel(item.bizType)}{item.subtitle ? ` · ${item.subtitle}` : ''}
                </div>
                {item.actionAt && <div className="text-[12px] text-slate-400 mt-1.5">{fmtTime(item.actionAt)}</div>}
              </div>
            ))}
          </div>
        )
      )}

      {tab === 'cc' && (
        tabLoading ? spinner : cc.length === 0 ? empty('暂无抄送') : (
          <div className="space-y-3">
            {cc.map((item) => {
              const st = statusMeta(item.status || '', 'wf')
              return (
                <div
                  key={item.cc_id}
                  className={`bg-white rounded-xl border shadow-sm p-4 cursor-pointer ${item.is_read ? 'border-slate-100' : 'border-primary/30'}`}
                  onClick={() => openDetail('wf', item.process_instance_id)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900 truncate">
                      {item.title || '审批'}
                      {!item.is_read && <span className="ml-2 text-[12px] text-red-500">未读</span>}
                    </h4>
                    <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${st.cls}`}>{st.text}</span>
                  </div>
                  <div className="text-sm text-slate-500 mt-1">
                    {bizLabel(item.biz_type || item.process_name)}
                    {item.initiator_name ? ` · ${item.initiator_name}` : ''}
                  </div>
                  {item.created_at && <div className="text-[12px] text-slate-400 mt-1.5">{fmtTime(item.created_at)}</div>}
                </div>
              )
            })}
          </div>
        )
      )}

      {tab === 'agents' && (
        <>
          <div className="bg-primary/10 rounded-xl p-3 mb-3 text-sm text-primary/80">
            设置某时间段由他人代你审批；代理人会在「待我审批」看到你的待办。
          </div>
          <button
            type="button"
            onClick={() => setAgentOpen(true)}
            className="w-full h-10 mb-3 rounded-xl bg-primary text-white text-sm font-bold border-0"
          >
            新增代理
          </button>
          {tabLoading ? spinner : agents.length === 0 ? empty('暂未设置代理') : (
            <div className="space-y-3">
              {agents.map((a) => (
                <div key={a.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-4">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900">{a.agent_name || a.agent_id}</h4>
                    <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full ${a.active_now ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'}`}>
                      {a.active_now ? '生效中' : '未生效'}
                    </span>
                  </div>
                  <div className="text-sm text-slate-500 mt-1">
                    {fmtTime(a.start_time)} ~ {fmtTime(a.end_time)}
                  </div>
                  {a.note && <div className="text-[12px] text-slate-400 mt-1">{a.note}</div>}
                  <button
                    type="button"
                    className="mt-3 text-sm font-bold text-red-500 bg-transparent border-0 p-0"
                    onClick={() => {
                      Modal.confirm({
                        title: '撤销该代理？',
                        onOk: async () => {
                          await workflowApi.deleteAgent(a.id)
                          message.success('已撤销')
                          await loadAgents()
                        },
                      })
                    }}
                  >
                    撤销
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {tab === 'all' && (
        tabLoading ? spinner : allFlows.length === 0 ? empty('暂无审批记录') : (
          <div className="space-y-3">
            {allFlows.map((f) => {
              const st = statusMeta(f.status, 'legacy')
              return (
                <div
                  key={f.id}
                  className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer"
                  onClick={() => openDetail('legacy', f.id)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900 truncate">{f.title || '审批申请'}</h4>
                    <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${st.cls}`}>{st.text}</span>
                  </div>
                  <div className="text-sm text-slate-500 mt-1">
                    {bizLabel(f.biz_type)}
                    {f.submitted_by_name ? ` · ${f.submitted_by_name}` : ''}
                    {f.total_nodes ? ` · ${f.current_node}/${f.total_nodes} 节点` : ''}
                  </div>
                  {f.created_at && <div className="text-[12px] text-slate-400 mt-1.5">{fmtTime(f.created_at)}</div>}
                </div>
              )
            })}
          </div>
        )
      )}

      {tab === 'stats' && (
        tabLoading ? spinner : !stats ? empty('暂无统计数据') : (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: '总审批数', value: String(stats.total_flows ?? 0) },
                { label: '通过率', value: `${(((stats.approval_rate as number) || 0) * 100).toFixed(1)}%` },
                { label: '平均时长', value: `${Number(stats.avg_approval_hours || 0).toFixed(1)} 小时` },
                { label: 'SLA 达标率', value: `${(((stats.sla_compliance_rate as number) || 0) * 100).toFixed(1)}%` },
              ].map((c) => (
                <div key={c.label} className="bg-white rounded-xl border border-slate-100 p-3">
                  <div className="text-[12px] text-slate-400 font-bold">{c.label}</div>
                  <div className="text-lg font-black text-slate-900 mt-1">{c.value}</div>
                </div>
              ))}
            </div>
            <div className="bg-white rounded-xl border border-slate-100 p-4">
              <h4 className="text-sm font-bold text-slate-700 mb-2">状态分布</h4>
              {Object.entries((stats.status_breakdown || {}) as Record<string, number>).map(([k, v]) => (
                <div key={k} className="flex justify-between py-1.5 text-sm">
                  <span className="text-slate-600">{approvalStatusLabels[k] || k}</span>
                  <span className="font-bold text-slate-900">{v}</span>
                </div>
              ))}
            </div>
            <div className="bg-white rounded-xl border border-slate-100 p-4">
              <h4 className="text-sm font-bold text-slate-700 mb-2">业务类型分布</h4>
              {Object.entries((stats.by_biz_type || {}) as Record<string, number>).map(([k, v]) => (
                <div key={k} className="flex justify-between py-1.5 text-sm">
                  <span className="text-slate-600">{bizLabel(k)}</span>
                  <span className="font-bold text-slate-900">{v}</span>
                </div>
              ))}
            </div>
            {((stats.top_approvers as Array<{ name: string; count: number }>) || []).length > 0 && (
              <div className="bg-white rounded-xl border border-slate-100 p-4">
                <h4 className="text-sm font-bold text-slate-700 mb-2">审批人排行</h4>
                {(stats.top_approvers as Array<{ name: string; count: number }>).map((a, i) => (
                  <div key={`${a.name}-${i}`} className="flex justify-between py-1.5 text-sm">
                    <span className="text-slate-600">{i + 1}. {a.name}</span>
                    <span className="font-bold text-slate-900">{a.count} 次</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )
      )}

      <Modal
        title="撤回审批"
        open={withdrawOpen}
        onCancel={() => setWithdrawOpen(false)}
        onOk={handleWithdraw}
        confirmLoading={busy}
        okText="确认撤回"
        destroyOnClose
      >
        {withdrawEngine === 'legacy' && (
          <Input.TextArea
            rows={3}
            value={withdrawReason}
            onChange={(e) => setWithdrawReason(e.target.value)}
            placeholder="撤回原因（选填）"
          />
        )}
        {withdrawEngine === 'wf' && <p className="text-sm text-slate-500">确认撤回该流程？</p>}
      </Modal>

      <Modal
        title="新增代理"
        open={agentOpen}
        onCancel={() => setAgentOpen(false)}
        onOk={saveAgent}
        confirmLoading={busy}
        okText="保存"
        destroyOnClose
      >
        <div className="space-y-3">
          <div>
            <div className="text-sm font-bold text-slate-600 mb-1">代理人</div>
            <PersonField value={agentUserId} onChange={setAgentUserId} placeholder="选择代理人" />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-600 mb-1">代理时段</div>
            <DatePicker.RangePicker
              showTime
              className="w-full"
              value={agentRange}
              onChange={(v) => setAgentRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-600 mb-1">备注</div>
            <Input value={agentNote} onChange={(e) => setAgentNote(e.target.value)} placeholder="选填" />
          </div>
        </div>
      </Modal>
    </div>
  )
}
