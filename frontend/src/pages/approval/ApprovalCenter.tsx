import { useState, useEffect, useMemo, useCallback } from 'react'
import { Tabs, Tag, Space, Modal, Input, Button, message, Spin, Select, Card, Statistic, Row, Col, DatePicker, Popconfirm } from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import { CheckCircleOutlined, CloseCircleOutlined, SwapOutlined, UndoOutlined, RedoOutlined, BarChartOutlined, FilterOutlined } from '@ant-design/icons'
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { approvalApi } from '@/api/approval'
import {
  fetchUnifiedPending, decideUnified, fetchUnifiedMine, fetchUnifiedDone,
  type UnifiedPendingItem, type UnifiedMineItem, type UnifiedDoneItem,
} from '@/api/unifiedApprovals'
import { workflowApi, type WfAgent } from '@/api/lowcodeWorkflow'
import { useWfProcessDrawer } from '@/components/lowcode/WfProcessDrawer'
import PersonField from '@/components/lowcode/fields/PersonField'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'
import { resolveWorkflowBizPath } from '@/utils/workflowBizPath'
import client from '@/api/client'
import { useAuthStore } from '@/stores/useAuthStore'
import type { ApprovalFlowItem } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import {
  approvalBizTypeLabels as bizTypeLabels,
  approvalStatusColors as statusColors,
  approvalStatusLabels as statusLabels,
  approvalModeLabels,
  approvalModeColors,
  taskStatusLabelsApproval,
  taskStatusColorsApproval,
} from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'
import { useUserSelect } from '@/hooks/useSelectOptions'
import dayjs from 'dayjs'

import Icon from '@/components/Icon'
export default function ApprovalCenter() {
  usePageTitle('审批中心')
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const userInfo = useAuthStore((s) => s.user)
  const [pending, setPending] = useState<UnifiedPendingItem[]>([])
  const [allFlows, setAllFlows] = useState<ApprovalFlowItem[]>([])
  const [mineItems, setMineItems] = useState<UnifiedMineItem[]>([])
  const [doneItems, setDoneItems] = useState<UnifiedDoneItem[]>([])
  const [ccItems, setCcItems] = useState<Array<{
    cc_id: string
    process_instance_id: string
    title?: string
    status?: string
    biz_type?: string
    initiator_name?: string
    is_read: boolean
    created_at?: string
  }>>([])
  const [agents, setAgents] = useState<WfAgent[]>([])
  const [tabLoading, setTabLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('pending')
  const [loading, setLoading] = useState(true)
  // 撤回：兼容两套引擎
  const [withdrawEngine, setWithdrawEngine] = useState<'legacy' | 'wf'>('legacy')
  // 代理设置
  const [agentModal, setAgentModal] = useState(false)
  const [agentUserId, setAgentUserId] = useState<unknown>(undefined)
  const [agentRange, setAgentRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null)
  const [agentNote, setAgentNote] = useState('')
  const [decideModal, setDecideModal] = useState(false)
  const [currentTask, setCurrentTask] = useState<UnifiedPendingItem | null>(null)
  const [decideAction, setDecideAction] = useState<'approve' | 'reject'>('approve')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // Detail modal
  const [detailModal, setDetailModal] = useState(false)
  const [detailFlow, setDetailFlow] = useState<ApprovalFlowItem | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  // Delegate modal
  const [delegateModal, setDelegateModal] = useState(false)
  const [delegateTask, setDelegateTask] = useState<UnifiedPendingItem | null>(null)
  const [delegateUserId, setDelegateUserId] = useState('')
  const [delegateReason, setDelegateReason] = useState('')
  // Withdraw modal
  const [withdrawModal, setWithdrawModal] = useState(false)
  const [withdrawFlowId, setWithdrawFlowId] = useState('')
  const [withdrawReason, setWithdrawReason] = useState('')
  // Bulk actions & filters
  const [selectedRowKeys, setSelectedRowKeys] = useState<string[]>([])
  const [filterBizType, setFilterBizType] = useState<string>('')
  const [filterDateRange, setFilterDateRange] = useState<[any, any] | null>(null)
  const userSelect = useUserSelect()

  // Statistics
  const [stats, setStats] = useState<Record<string, unknown> | null>(null)
  const [statsLoading, setStatsLoading] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      // 合同/线索等已切到新工作流引擎：待办必须聚合两套引擎
      // 「所有审批」tab 再按需拉 list，避免首屏多打一次重请求
      const uRes = await fetchUnifiedPending()
      setPending(uRes.items || [])
    } finally {
      setLoading(false)
    }
  }

  const loadAllFlows = useCallback(async () => {
    setTabLoading(true)
    try {
      const fRes = await approvalApi.list({ pageNo: 1, pageSize: 50 })
      setAllFlows(fRes.data?.items || [])
    } finally {
      setTabLoading(false)
    }
  }, [])

  const loadMine = useCallback(async () => {
    setTabLoading(true)
    try {
      setMineItems(await fetchUnifiedMine(userInfo?.id))
    } finally {
      setTabLoading(false)
    }
  }, [userInfo?.id])

  const loadDone = useCallback(async () => {
    setTabLoading(true)
    try {
      setDoneItems(await fetchUnifiedDone(userInfo?.id))
    } finally {
      setTabLoading(false)
    }
  }, [userInfo?.id])

  const loadCc = useCallback(async () => {
    setTabLoading(true)
    try {
      const r = await workflowApi.cc({ pageNo: 1, pageSize: 100 })
      setCcItems(r.data?.items || [])
    } finally {
      setTabLoading(false)
    }
  }, [])

  const loadAgents = useCallback(async () => {
    setTabLoading(true)
    try {
      const r = await workflowApi.listAgents()
      setAgents(r.data || [])
    } finally {
      setTabLoading(false)
    }
  }, [])

  const onTabChange = (key: string) => {
    setActiveTab(key)
    if (key === 'stats' && !stats) loadStats()
    if (key === 'mine') loadMine()
    if (key === 'done') loadDone()
    if (key === 'cc') loadCc()
    if (key === 'agents') loadAgents()
    if (key === 'all') loadAllFlows()
  }

  const { openWith: openWfDrawer, node: wfDrawerNode } = useWfProcessDrawer(() => {
    fetchData()
    if (activeTab === 'mine') loadMine()
    if (activeTab === 'done') loadDone()
    if (activeTab === 'cc') loadCc()
  })

  useEffect(() => { fetchData() }, [])

  // 深链：?tab=cc → 抄送我的；通知/钉钉 → ?wf= / ?flow=
  useEffect(() => {
    const st = (location.state || {}) as { openInstanceId?: string; openTaskId?: string; openFlowId?: string }
    const tab = searchParams.get('tab')
    const wfId = searchParams.get('wf') || st.openInstanceId || null
    const flowId = searchParams.get('flow') || st.openFlowId || null
    const taskId = searchParams.get('task') || st.openTaskId || null

    if (tab === 'cc' || tab === 'mine' || tab === 'done' || tab === 'pending' || tab === 'agents') {
      const mapped = tab === 'pending' ? 'pending' : tab
      setActiveTab(mapped)
      if (mapped === 'cc') void loadCc()
      if (mapped === 'mine') void loadMine()
      if (mapped === 'done') void loadDone()
      if (mapped === 'agents') void loadAgents()
    }

    if (!wfId && !flowId) {
      // 仅切 tab 的深链：应用后清掉 query，避免刷新/返回时反复抢焦点
      if (searchParams.has('tab')) {
        const next = new URLSearchParams(searchParams)
        next.delete('tab')
        setSearchParams(next, { replace: true })
      }
      return
    }

    if (wfId) openWfDrawer(wfId, taskId)
    else if (flowId) openDetail(flowId)

    if (searchParams.has('wf') || searchParams.has('flow') || searchParams.has('task') || searchParams.has('tab')) {
      const next = new URLSearchParams(searchParams)
      next.delete('wf'); next.delete('flow'); next.delete('task'); next.delete('tab')
      setSearchParams(next, { replace: true })
    }
    if (st.openInstanceId || st.openFlowId) {
      navigate(location.pathname, { replace: true, state: {} })
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state, searchParams])

  const openWfHandle = (item: UnifiedPendingItem) => {
    if (item.engine === 'wf' && item.taskKind === 'revise') {
      const path = resolveWorkflowBizPath({
        bizType: item.bizType,
        bizId: item.bizId,
        formInstanceId: item.formInstanceId,
        formCode: item.formCode,
        taskKind: item.taskKind,
        taskId: item.taskId,
      })
      if (path) {
        navigate(path)
        return
      }
    }
    if (!item.instanceId) {
      message.warning('缺少流程实例，无法打开')
      return
    }
    openWfDrawer(item.instanceId, item.taskId)
  }

  const openOriginalDoc = (opts: {
    bizType?: string | null
    bizId?: string | null
    formInstanceId?: string | null
    formCode?: string | null
    taskKind?: string | null
    taskId?: string | null
  }) => {
    const path = resolveWorkflowBizPath({
      bizType: opts.bizType,
      bizId: opts.bizId,
      formInstanceId: opts.formInstanceId,
      formCode: opts.formCode,
      taskKind: opts.taskKind,
      taskId: opts.taskId,
    })
    if (path) navigate(path)
    else message.info('暂无关联原单据')
  }

  const openDecide = (task: UnifiedPendingItem, action: 'approve' | 'reject') => {
    // 新引擎合同登记等节点可能要求填写采购员/质检员，本页抽屉处理
    if (task.engine === 'wf') {
      openWfHandle(task)
      return
    }
    setCurrentTask(task)
    setDecideAction(action)
    setComment('')
    setDecideModal(true)
  }

  const handleDecide = async () => {
    if (!currentTask) return
    setSubmitting(true)
    try {
      await decideUnified(currentTask, decideAction, comment || undefined)
      message.success(decideAction === 'approve' ? '已通过' : '已驳回')
      setDecideModal(false)
      fetchData()
    } catch {
      message.error('审批操作失败')
    } finally {
      setSubmitting(false)
    }
  }

  const openDetail = async (flowId: string) => {
    setDetailLoading(true)
    setDetailModal(true)
    try {
      const res = await approvalApi.get(flowId)
      setDetailFlow(res.data)
    } finally {
      setDetailLoading(false)
    }
  }

  const navigateToBiz = async (bizType: string, bizId: string) => {
    try {
      if (bizType === 'quote_version') {
        const res = await client.get(`/api/v1/quote_versions/${bizId}`)
        const ver = (res as any).data
        if (ver?.quote_id) {
          const qRes = await client.get(`/api/v1/quotes/${ver.quote_id}`)
          const q = (qRes as any).data
          if (q?.project_id) {
            navigate(`/opportunities/${q.project_id}/quotes/${ver.quote_id}`)
            return
          }
        }
      } else if (bizType === 'contract_version') {
        const res = await client.get(`/api/v1/contract_versions/${bizId}`)
        const ver = (res as any).data
        if (ver?.contract_id) {
          const cRes = await client.get(`/api/v1/contracts/${ver.contract_id}`)
          const c = (cRes as any).data
          if (c?.project_id) {
            navigate(`/opportunities/${c.project_id}/contracts/${ver.contract_id}`)
            return
          }
        }
      } else if (bizType === 'change_request') {
        // biz_id 是变更单 id，不是商机 id —— 先取 project_id 再跳转，否则 404
        const res = await client.get(`/api/v1/change_requests/${bizId}`)
        const cr = (res as any).data
        if (cr?.project_id) {
          navigate(`/opportunities/${cr.project_id}`)
          return
        }
      } else if (bizType === 'solution') {
        // biz_id 是方案 id，不是商机 id —— 先取 project_id 再跳转，否则 404
        const res = await client.get(`/api/v1/solutions/${bizId}`)
        const sol = (res as any).data
        if (sol?.project_id) {
          navigate(`/opportunities/${sol.project_id}/solutions/${bizId}`)
          return
        }
      } else if (bizType === 'lead') {
        // biz_id 即线索 id，直接跳线索详情
        navigate(`/leads/${bizId}`)
        return
      }
    } catch {
      // Fallback
    }
    message.info('无法定位到具体业务页面')
  }

  // Withdraw
  const openWithdraw = (flowId: string, engine: 'legacy' | 'wf' = 'legacy') => {
    setWithdrawFlowId(flowId)
    setWithdrawEngine(engine)
    setWithdrawReason('')
    setWithdrawModal(true)
  }

  const handleWithdraw = async () => {
    setSubmitting(true)
    try {
      if (withdrawEngine === 'wf') {
        await workflowApi.withdraw(withdrawFlowId)
      } else {
        await approvalApi.withdraw(withdrawFlowId, { reason: withdrawReason || undefined })
      }
      message.success('审批已撤回')
      setWithdrawModal(false)
      fetchData()
      loadMine()
    } finally {
      setSubmitting(false)
    }
  }

  const handleUrge = async (instanceId: string) => {
    try {
      const r = await workflowApi.urge(instanceId)
      message.success(`已催办 ${r.data?.notified ?? 0} 人`)
    } catch (e) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.warning(msg || '催办失败')
    }
  }

  const saveAgent = async () => {
    if (!agentUserId) { message.error('请选择代理人'); return }
    if (!agentRange?.[0] || !agentRange?.[1]) { message.error('请选择代理时间段'); return }
    setSubmitting(true)
    try {
      await workflowApi.createAgent({
        agent_id: String(agentUserId),
        start_time: agentRange[0].toISOString(),
        end_time: agentRange[1].toISOString(),
        note: agentNote || undefined,
      })
      message.success('已设置代理')
      setAgentModal(false)
      setAgentUserId(undefined)
      setAgentRange(null)
      setAgentNote('')
      loadAgents()
    } catch {
      message.error('设置失败')
    } finally {
      setSubmitting(false)
    }
  }

  // Delegate
  const openDelegate = (task: UnifiedPendingItem) => {
    if (task.engine === 'wf') {
      openWfHandle(task)
      return
    }
    setDelegateTask(task)
    setDelegateUserId('')
    setDelegateReason('')
    setDelegateModal(true)
  }

  const handleDelegate = async () => {
    if (!delegateTask) return
    if (!delegateUserId) { message.warning('请选择目标审批人'); return }
    setSubmitting(true)
    try {
      await approvalApi.delegate(delegateTask.taskId, { target_user_id: delegateUserId, reason: delegateReason || undefined })
      message.success('审批已转交')
      setDelegateModal(false)
      fetchData()
    } finally {
      setSubmitting(false)
    }
  }

  // Bulk decide
  const handleBulkDecide = (action: 'approved' | 'rejected') => {
    if (selectedRowKeys.length === 0) { message.warning('请选择审批任务'); return }
    const selected = pending.filter((p) => selectedRowKeys.includes(p.key))
    const legacyIds = selected.filter((p) => p.engine === 'legacy').map((p) => p.taskId)
    const wfItems = selected.filter((p) => p.engine === 'wf')
    if (wfItems.length > 0 && legacyIds.length === 0) {
      message.info('流程引擎待办请逐条点「处理」（可能需填写节点字段）')
      return
    }
    const label = action === 'approved' ? '通过' : '驳回'
    Modal.confirm({
      title: `批量${label}确认`,
      content: wfItems.length
        ? `将${label} ${legacyIds.length} 条旧引擎待办；另有 ${wfItems.length} 条流程待办需单独处理。`
        : `确定要${label} ${legacyIds.length} 条审批任务吗？`,
      onOk: async () => {
        setSubmitting(true)
        try {
          if (legacyIds.length) {
            const res = await approvalApi.bulkDecide({ task_ids: legacyIds, action })
            const results = res.data || []
            const successCount = results.filter((r: any) => r.success).length
            const failCount = results.filter((r: any) => !r.success).length
            message.info(`完成: 成功 ${successCount} 条，失败 ${failCount} 条`)
          }
          setSelectedRowKeys([])
          fetchData()
        } finally {
          setSubmitting(false)
        }
      },
    })
  }

  // Resubmit（旧引擎驳回/撤回；新引擎撤回/驳回）
  const handleResubmit = async (flowId: string, engine: 'legacy' | 'wf' = 'legacy') => {
    setSubmitting(true)
    try {
      if (engine === 'wf') {
        await workflowApi.resubmit(flowId)
      } else {
        await approvalApi.resubmit(flowId, {})
      }
      message.success('已重新提交审批')
      fetchData()
    } finally {
      setSubmitting(false)
    }
  }

  const handleEndProcess = (instanceId: string) => {
    Modal.confirm({
      title: '确认手动结束？',
      content: '结束后将取消「修改并重新提交」待办，流程不再出现在待办列表。',
      okText: '结束流程',
      okType: 'danger',
      onOk: async () => {
        setSubmitting(true)
        try {
          await workflowApi.endProcess(instanceId)
          message.success('已手动结束流程')
          fetchData()
        } finally {
          setSubmitting(false)
        }
      },
    })
  }

  // Statistics
  const loadStats = async () => {
    setStatsLoading(true)
    try {
      const res = await approvalApi.statistics()
      setStats(res.data)
    } finally {
      setStatsLoading(false)
    }
  }

  const filteredPending = useMemo(() => {
    let list = pending
    if (filterBizType) {
      list = list.filter((p) => p.bizType === filterBizType)
    }
    if (filterDateRange && filterDateRange[0] && filterDateRange[1]) {
      const start = filterDateRange[0].startOf('day').valueOf()
      const end = filterDateRange[1].endOf('day').valueOf()
      list = list.filter((p) => {
        const t = p.createdAt ? new Date(p.createdAt).getTime() : 0
        return t >= start && t <= end
      })
    }
    return list
  }, [pending, filterBizType, filterDateRange])

  const pendingBizTypes = useMemo(() => {
    const types = new Set(pending.map((p) => p.bizType).filter(Boolean))
    return Array.from(types).map((t) => ({ value: t!, label: bizTypeLabels[t!] || t! }))
  }, [pending])

  const pendingColumns: ColumnsType<UnifiedPendingItem> = [
    {
      title: '审批标题', dataIndex: 'title', width: 360,
      render: (v: string, r) => (
        <a
          className="font-semibold text-primary cursor-pointer"
          onClick={() => {
            if (r.engine === 'wf') openWfHandle(r)
            else if (r.instanceId) openDetail(r.instanceId)
          }}
        >
          {v || '审批申请'}
        </a>
      ),
    },
    {
      title: '类型', dataIndex: 'bizType', width: 120,
      render: (v: string) => <Tag color="blue">{bizTypeLabels[v] || v || '—'}</Tag>,
    },
    {
      title: '引擎', dataIndex: 'engine', width: 90,
      render: (v: string) => v === 'wf' ? <Tag color="purple">流程</Tag> : <Tag>经典</Tag>,
    },
    {
      title: '说明', dataIndex: 'subtitle', width: 180,
      render: (v: string) => <span className="text-sm text-slate-500">{v || '—'}</span>,
    },
    {
      title: '发起时间', dataIndex: 'createdAt', width: 160,
      render: (v: string) => {
        if (!v) return '-'
        const hours = (Date.now() - new Date(v).getTime()) / (1000 * 3600)
        const isOverdue = hours > 24
        return (
          <span className={isOverdue ? 'text-red-500 font-bold' : ''}>
            {new Date(v).toLocaleString('zh-CN')}
            {isOverdue && <Tag color="red" className="ml-1 text-[12px]">超时</Tag>}
          </span>
        )
      },
    },
    {
      title: '操作', key: 'actions', width: 240,
      render: (_, r) => (
        <Space>
          {r.engine === 'wf' ? (
            <>
              <Button type="primary" size="small" onClick={() => openWfHandle(r)}>
                {r.taskKind === 'revise' ? '去修改' : '处理'}
              </Button>
              {(r.taskKind === 'revise' || r.bizId || r.formInstanceId) && (
                <Button size="small" type="link" onClick={() => openOriginalDoc(r)}>
                  原单据
                </Button>
              )}
            </>
          ) : (
            <>
              <Button type="primary" size="small" icon={<CheckCircleOutlined />}
                onClick={() => openDecide(r, 'approve')}>通过</Button>
              <Button danger size="small" icon={<CloseCircleOutlined />}
                onClick={() => openDecide(r, 'reject')}>驳回</Button>
              <Button size="small" icon={<SwapOutlined />}
                onClick={() => openDelegate(r)}>转交</Button>
            </>
          )}
        </Space>
      ),
    },
  ]

  const renderFlowStatus = (status: string, engine?: string) => {
    if (engine === 'wf' || PSTATUS[status]) {
      const t = PSTATUS[status] || { color: 'default', text: statusLabels[status] || status }
      return <Tag color={t.color}>{t.text}</Tag>
    }
    return <Tag color={statusColors[status]}>{statusLabels[status] || status}</Tag>
  }

  const historyColumns: ColumnsType<ApprovalFlowItem> = [
    {
      title: '审批标题', dataIndex: 'title', width: 280,
      render: (v: string, r) => (
        <a className="font-semibold text-primary cursor-pointer" onClick={() => openDetail(r.id)}>{v || '审批申请'}</a>
      ),
    },
    {
      title: '类型', dataIndex: 'biz_type', width: 120,
      render: (v: string) => <Tag color="blue">{bizTypeLabels[v] || v}</Tag>,
    },
    {
      title: '模式', dataIndex: 'approval_mode', width: 100,
      render: (v: string) => v ? <Tag color={approvalModeColors[v] || 'blue'}>{approvalModeLabels[v] || v}</Tag> : null,
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v] || v}</Tag>,
    },
    {
      title: '发起人', dataIndex: 'submitted_by_name', width: 100,
    },
    {
      title: '进度', key: 'progress', width: 100,
      render: (_, r) => <span className="text-sm text-slate-500">{r.current_node}/{r.total_nodes} 节点</span>,
    },
    {
      title: '发起时间', dataIndex: 'created_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '更新时间', dataIndex: 'updated_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
  ]

  const mineColumns: ColumnsType<UnifiedMineItem> = [
    {
      title: '审批标题', dataIndex: 'title', width: 360,
      render: (v, r) => (
        <a
          className="font-semibold text-primary cursor-pointer"
          onClick={() => {
            if (r.engine === 'wf') openWfDrawer(r.instanceId)
            else openDetail(r.instanceId)
          }}
        >
          {v || '审批申请'}
        </a>
      ),
    },
    {
      title: '类型', dataIndex: 'bizType', width: 120,
      render: (v: string) => <Tag color="blue">{bizTypeLabels[v] || v || '—'}</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', width: 110,
      render: (v, r) => renderFlowStatus(v, r.engine),
    },
    {
      title: '进度', dataIndex: 'subtitle', width: 160,
      render: (v: string) => <span className="text-sm text-slate-500">{v || '—'}</span>,
    },
    {
      title: '发起时间', dataIndex: 'createdAt', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作', key: 'actions', width: 220,
      render: (_, r) => (
        <Space>
          <Button
            size="small"
            onClick={() => {
              if (r.engine === 'wf') openWfDrawer(r.instanceId)
              else openDetail(r.instanceId)
            }}
          >
            查看
          </Button>
          {r.engine === 'wf' && r.status === 'running' && (
            <Button size="small" type="link" onClick={() => handleUrge(r.instanceId)}>催办</Button>
          )}
          {((r.engine === 'wf' && r.status === 'running') || (r.engine === 'legacy' && r.status === 'pending')) && (
            <Button size="small" icon={<UndoOutlined />} onClick={() => openWithdraw(r.instanceId, r.engine)}>撤回</Button>
          )}
          {((r.engine === 'wf' && (r.status === 'withdrawn' || r.status === 'rejected'))
            || (r.engine === 'legacy' && (r.status === 'rejected' || r.status === 'withdrawn'))) && (
            <>
              {(r.formInstanceId || r.bizId) && (
                <Button
                  size="small"
                  onClick={() => openOriginalDoc({
                    bizType: r.bizType,
                    bizId: r.bizId,
                    formInstanceId: r.formInstanceId,
                    formCode: r.formCode,
                  })}
                >
                  打开原单据
                </Button>
              )}
              <Button
                size="small"
                type="primary"
                icon={<RedoOutlined />}
                onClick={() => handleResubmit(r.instanceId, r.engine)}
              >
                重新提交
              </Button>
              {r.engine === 'wf' && (
                <Button size="small" danger onClick={() => handleEndProcess(r.instanceId)}>
                  手动结束
                </Button>
              )}
            </>
          )}
        </Space>
      ),
    },
  ]

  const doneColumns: ColumnsType<UnifiedDoneItem> = [
    {
      title: '审批标题', dataIndex: 'title', width: 360,
      render: (v, r) => (
        <a
          className="font-semibold text-primary cursor-pointer"
          onClick={() => {
            if (r.engine === 'wf') openWfDrawer(r.instanceId, r.taskId)
            else openDetail(r.instanceId)
          }}
        >
          {v || '审批申请'}
        </a>
      ),
    },
    {
      title: '类型', dataIndex: 'bizType', width: 120,
      render: (v: string) => <Tag color="blue">{bizTypeLabels[v] || v || '—'}</Tag>,
    },
    {
      title: '我的处理', dataIndex: 'status', width: 110,
      render: (s: string) => (
        <Tag color={s === 'approved' ? 'green' : s === 'rejected' ? 'red' : s === 'returned' ? 'orange' : 'default'}>
          {s === 'approved' ? '已通过' : s === 'rejected' ? '已驳回' : s === 'returned' ? '已退回' : s === 'transferred' ? '已转交' : s}
        </Tag>
      ),
    },
    {
      title: '说明', dataIndex: 'subtitle', width: 180,
      render: (v: string) => <span className="text-sm text-slate-500">{v || '—'}</span>,
    },
    {
      title: '处理时间', dataIndex: 'actionAt', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作', key: 'op', width: 90,
      render: (_, r) => (
        <Button
          size="small"
          onClick={() => {
            if (r.engine === 'wf') openWfDrawer(r.instanceId, r.taskId)
            else openDetail(r.instanceId)
          }}
        >
          查看
        </Button>
      ),
    },
  ]

  if (loading) return <DetailSkeleton />


  return (
    <div>
      <div className="mb-6 shrink-0">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">审批中心</h1>
        <p className="text-sm text-slate-500 mt-1">统一处理合同、线索等业务待办（含可视化流程）</p>
      </div>
      {wfDrawerNode}

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Tabs activeKey={activeTab} className="px-4 pt-2 pb-4"
          onChange={onTabChange}
          items={[
            {
              key: 'pending',
              label: <span>待我审批 {pending.length > 0 && <Tag color="red" className="ml-1">{pending.length}</Tag>}</span>,
              children: (
                <div>
                  {pending.length > 0 && (
                    <div className="mb-3 flex flex-wrap items-center gap-2 shrink-0">
                      <FilterOutlined className="text-slate-400" />
                      <Select size="small" allowClear placeholder="业务类型" value={filterBizType || undefined}
                        onChange={(v) => { setFilterBizType(v || ''); setSelectedRowKeys([]) }}
                        options={pendingBizTypes} style={{ width: 130 }} />
                      <DatePicker.RangePicker size="small" value={filterDateRange as any}
                        onChange={(v) => { setFilterDateRange(v as any); setSelectedRowKeys([]) }} />
                      {(filterBizType || filterDateRange) && (
                        <Button size="small" type="link" onClick={() => { setFilterBizType(''); setFilterDateRange(null); setSelectedRowKeys([]) }}>清除筛选</Button>
                      )}
                      <div className="flex-1" />
                      <Button size="small" type="primary" icon={<CheckCircleOutlined />}
                        disabled={selectedRowKeys.length === 0} loading={submitting}
                        onClick={() => handleBulkDecide('approved')}>批量通过</Button>
                      <Button size="small" danger icon={<CloseCircleOutlined />}
                        disabled={selectedRowKeys.length === 0} loading={submitting}
                        onClick={() => handleBulkDecide('rejected')}>批量驳回</Button>
                      {selectedRowKeys.length > 0 && <span className="text-sm text-slate-400 self-center">已选 {selectedRowKeys.length}/{filteredPending.length} 项</span>}
                    </div>
                  )}
                  <FillHeightTable rowKey="key" columns={pendingColumns} dataSource={filteredPending}
                    rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys as string[]) }}
                    pagination={false} size="small" scroll={{ x: 'max-content' }}
                    locale={{ emptyText: <div className="py-8 text-slate-400">暂无待审批任务</div> }} />
                </div>
              ),
            },
            {
              key: 'mine',
              label: '我发起的',
              children: (
                <FillHeightTable
                  rowKey="key"
                  columns={mineColumns}
                  dataSource={mineItems}
                  loading={tabLoading}
                  pagination={{ pageSize: 15, showSizeChanger: false }}
                  size="small"
                  scroll={{ x: 'max-content' }}
                  locale={{ emptyText: <div className="py-8 text-slate-400">暂无发起的审批</div> }}
                />
              ),
            },
            {
              key: 'done',
              label: '已办',
              children: (
                <FillHeightTable
                  rowKey="key"
                  columns={doneColumns}
                  dataSource={doneItems}
                  loading={tabLoading}
                  pagination={{ pageSize: 15, showSizeChanger: false }}
                  size="small"
                  scroll={{ x: 'max-content' }}
                  locale={{ emptyText: <div className="py-8 text-slate-400">暂无已办记录</div> }}
                />
              ),
            },
            {
              key: 'cc',
              label: '抄送我的',
              children: (
                <FillHeightTable<{
                  cc_id: string
                  process_instance_id: string
                  title?: string
                  status?: string
                  biz_type?: string
                  initiator_name?: string
                  is_read: boolean
                  created_at?: string
                }>
                  rowKey="cc_id"
                  loading={tabLoading}
                  size="small"
                  scroll={{ x: 'max-content' }}
                  pagination={{ pageSize: 15, showSizeChanger: false }}
                  locale={{ emptyText: <div className="py-8 text-slate-400">暂无抄送<br /><span className="text-xs">流程抄送节点触发后会出现在此；通知中心的「审批待处理/已决定」不会进入本列表</span></div> }}
                  dataSource={ccItems}
                  columns={[
                    {
                      title: '标题', dataIndex: 'title', width: 280,
                      render: (v, r) => (
                        <a className="font-semibold text-primary cursor-pointer" onClick={() => openWfDrawer(r.process_instance_id)}>
                          {v || '审批'}{!r.is_read && <Tag color="red" className="ml-1">未读</Tag>}
                        </a>
                      ),
                    },
                    {
                      title: '类型', key: 'type', width: 120,
                      render: (_: unknown, r: { biz_type?: string; process_name?: string | null }) => {
                        const t = r.biz_type || r.process_name || ''
                        return <Tag color="blue">{bizTypeLabels[t] || t || '—'}</Tag>
                      },
                    },
                    {
                      title: '状态', dataIndex: 'status', width: 110,
                      render: (v) => renderFlowStatus(v || '', 'wf'),
                    },
                    {
                      title: '发起人', dataIndex: 'initiator_name', width: 100,
                      render: (v) => v || '—',
                    },
                    {
                      title: '抄送时间', dataIndex: 'created_at', width: 160,
                      render: (v) => v ? new Date(v).toLocaleString('zh-CN') : '-',
                    },
                    {
                      title: '操作', key: 'op', width: 90,
                      render: (_: unknown, r) => (
                        <Button size="small" onClick={() => openWfDrawer(r.process_instance_id)}>查看</Button>
                      ),
                    },
                  ]}
                />
              ),
            },
            {
              key: 'agents',
              label: '我的代理',
              children: (
                <div>
                  <div className="mb-3 flex items-center gap-3 shrink-0">
                    <span className="text-sm text-slate-500">设置某时间段由他人代你审批；代理人会在「待我审批」看到你的待办。</span>
                    <Button type="primary" size="small" onClick={() => setAgentModal(true)}>新增代理</Button>
                  </div>
                  <FillHeightTable
                    rowKey="id"
                    loading={tabLoading}
                    size="small"
                    scroll={{ x: 'max-content' }}
                    pagination={false}
                    dataSource={agents}
                    locale={{ emptyText: <div className="py-8 text-slate-400">暂未设置代理</div> }}
                    columns={[
                      { title: '代理人', dataIndex: 'agent_name', render: (v: string, r: WfAgent) => v || r.agent_id },
                      {
                        title: '开始', dataIndex: 'start_time',
                        render: (v: string) => (v ? new Date(v).toLocaleString('zh-CN') : '—'),
                      },
                      {
                        title: '结束', dataIndex: 'end_time',
                        render: (v: string) => (v ? new Date(v).toLocaleString('zh-CN') : '—'),
                      },
                      {
                        title: '状态', key: 'st', width: 90,
                        render: (_: unknown, r: WfAgent) => (r.active_now ? <Tag color="green">生效中</Tag> : <Tag>未生效</Tag>),
                      },
                      { title: '备注', dataIndex: 'note', render: (v: string) => v || '—' },
                      {
                        title: '操作', key: 'op', width: 80,
                        render: (_: unknown, r: WfAgent) => (
                          <Popconfirm title="撤销该代理?" onConfirm={async () => {
                            await workflowApi.deleteAgent(r.id)
                            message.success('已撤销')
                            loadAgents()
                          }}>
                            <Button size="small" type="link" danger>撤销</Button>
                          </Popconfirm>
                        ),
                      },
                    ]}
                  />
                </div>
              ),
            },
            {
              key: 'all',
              label: '所有审批',
              children: (
                <div>
                  <FillHeightTable rowKey="id" columns={historyColumns} dataSource={allFlows}
                    loading={tabLoading}
                    pagination={{ pageSize: 15, showSizeChanger: false }} size="small" scroll={{ x: 'max-content' }} />
                </div>
              ),
            },
            {
              key: 'stats',
              label: <span><BarChartOutlined className="mr-1" />统计</span>,
              children: statsLoading ? (
                <div className="flex justify-center py-12 overflow-y-auto"><Spin /></div>
              ) : stats ? (
                <div className="py-4 overflow-y-auto">
                  <Row gutter={16} className="mb-6">
                    <Col span={6}><Card><Statistic title="总审批数" value={stats.total_flows as number} /></Card></Col>
                    <Col span={6}><Card><Statistic title="通过率" value={((stats.approval_rate as number) * 100)} suffix="%" precision={1} /></Card></Col>
                    <Col span={6}><Card><Statistic title="平均审批时长" value={stats.avg_approval_hours as number} suffix="小时" precision={1} /></Card></Col>
                    <Col span={6}><Card><Statistic title="SLA 达标率" value={((stats.sla_compliance_rate as number) * 100)} suffix="%" precision={1} /></Card></Col>
                  </Row>
                  <Row gutter={16}>
                    <Col span={12}>
                      <Card title="状态分布" size="small">
                        {Object.entries(stats.status_breakdown as Record<string, number>).map(([k, v]) => (
                          <div key={k} className="flex justify-between py-1">
                            <Tag color={statusColors[k]}>{statusLabels[k] || k}</Tag>
                            <span className="font-bold">{v}</span>
                          </div>
                        ))}
                      </Card>
                    </Col>
                    <Col span={12}>
                      <Card title="业务类型分布" size="small">
                        {Object.entries(stats.by_biz_type as Record<string, number>).map(([k, v]) => (
                          <div key={k} className="flex justify-between py-1">
                            <Tag color="blue">{bizTypeLabels[k] || k}</Tag>
                            <span className="font-bold">{v}</span>
                          </div>
                        ))}
                      </Card>
                    </Col>
                  </Row>
                  {(stats.top_approvers as Array<{ name: string; count: number }>)?.length > 0 && (
                    <Card title="审批人排行" size="small" className="mt-4">
                      {(stats.top_approvers as Array<{ name: string; count: number }>).map((a, i) => (
                        <div key={i} className="flex justify-between py-1">
                          <span>{i + 1}. {a.name}</span>
                          <span className="font-bold">{a.count} 次</span>
                        </div>
                      ))}
                    </Card>
                  )}
                </div>
              ) : <div className="py-8 text-center text-slate-400">暂无统计数据</div>,
            },
          ]}
        />
      </div>

      <Modal
        title="新增代理"
        open={agentModal}
        onOk={saveAgent}
        confirmLoading={submitting}
        onCancel={() => setAgentModal(false)}
        destroyOnClose
      >
        <div className="space-y-3 py-2">
          <div>
            <div className="mb-1 text-sm">代理人</div>
            <PersonField value={agentUserId} onChange={setAgentUserId} placeholder="选择代理人" />
          </div>
          <div>
            <div className="mb-1 text-sm">代理时间段</div>
            <DatePicker.RangePicker
              showTime
              className="w-full"
              value={agentRange as never}
              onChange={(v) => setAgentRange(v as [dayjs.Dayjs, dayjs.Dayjs] | null)}
            />
          </div>
          <div>
            <div className="mb-1 text-sm">备注</div>
            <Input value={agentNote} onChange={(e) => setAgentNote(e.target.value)} placeholder="可选，如：出差期间" />
          </div>
        </div>
      </Modal>

      {/* Decide Modal */}
      <Modal
        title={decideAction === 'approve' ? '审批通过' : '审批驳回'}
        open={decideModal}
        onOk={handleDecide}
        onCancel={() => setDecideModal(false)}
        confirmLoading={submitting}
        okText={decideAction === 'approve' ? '确认通过' : '确认驳回'}
        okButtonProps={{ danger: decideAction === 'reject' }}
      >
        {currentTask && (
          <div className="py-2">
            <div className="mb-3 p-3 bg-slate-50 rounded-lg">
              <div className="text-sm font-bold text-slate-800">{currentTask.title || '审批申请'}</div>
              <div className="text-sm text-slate-500 mt-1">
                类型: {bizTypeLabels[currentTask.bizType || ''] || currentTask.bizType || '—'}
                {currentTask.subtitle ? ` · ${currentTask.subtitle}` : ''}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">审批意见</label>
              <Input.TextArea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={3}
                placeholder={decideAction === 'approve' ? '同意，可选填意见...' : '请填写驳回原因...'}
              />
            </div>
          </div>
        )}
      </Modal>

      {/* Flow Detail Modal */}
      <Modal
        title="审批详情"
        open={detailModal}
        onCancel={() => { setDetailModal(false); setDetailFlow(null) }}
        footer={null}
        width={640}
      >
        {detailLoading ? (
          <div className="flex justify-center py-8"><Spin /></div>
        ) : detailFlow ? (
          <div>
            <div className="mb-4 p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg font-bold text-slate-900">{detailFlow.title || '审批申请'}</span>
                <Space>
                  <Tag color={statusColors[detailFlow.status]}>{statusLabels[detailFlow.status] || detailFlow.status}</Tag>
                  {detailFlow.approval_mode && (
                    <Tag color={approvalModeColors[detailFlow.approval_mode]}>{approvalModeLabels[detailFlow.approval_mode] || detailFlow.approval_mode}</Tag>
                  )}
                </Space>
              </div>
              <div className="text-sm text-slate-500">
                类型: {bizTypeLabels[detailFlow.biz_type] || detailFlow.biz_type} ·
                发起人: {detailFlow.submitted_by_name} ·
                发起时间: {detailFlow.created_at ? new Date(detailFlow.created_at).toLocaleString('zh-CN') : '-'}
                {detailFlow.revision_no && detailFlow.revision_no > 1 && (
                  <Tag color="orange" className="ml-2">第 {detailFlow.revision_no} 次提交</Tag>
                )}
              </div>
              {detailFlow.biz_id && (
                <Button size="small" className="mt-2" onClick={() => { setDetailModal(false); navigateToBiz(detailFlow.biz_type, detailFlow.biz_id) }}>
                  查看关联业务
                </Button>
              )}
            </div>

            {/* Business Detail */}
            {detailFlow.biz_detail && Object.keys(detailFlow.biz_detail).length > 0 && (
              <div className="mb-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
                <h4 className="text-sm font-bold uppercase tracking-wider text-blue-400 mb-2">业务信息</h4>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(detailFlow.biz_detail).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-sm text-slate-500">{k}</span>
                      <span className="text-sm font-semibold text-slate-800">{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Approval Timeline */}
            <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400 mb-3">审批流程</h4>
            <div className="space-y-3">
              {(detailFlow.tasks || []).map((task) => {
                const isApproved = task.status === 'approved'
                const isRejected = task.status === 'rejected'
                const isCancelled = task.status === 'cancelled'
                const isPending = task.status === 'pending'
                return (
                  <div key={task.id} className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      isApproved ? 'bg-emerald-100 text-emerald-600' :
                      isRejected ? 'bg-red-100 text-red-600' :
                      isCancelled ? 'bg-slate-100 text-slate-400' :
                      isPending ? 'bg-amber-100 text-amber-600' :
                      'bg-slate-100 text-slate-400'
                    }`}>
                      <Icon name={isApproved ? 'check' : isRejected ? 'close' : isCancelled ? 'block' : isPending ? 'schedule' : 'hourglass_empty'} style={{ fontSize: 16 }} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-800">
                          节点 {task.node_order}: {task.assignee_name || '审批人'}
                        </span>
                        <Tag color={taskStatusColorsApproval[task.status] || 'default'}>
                          {taskStatusLabelsApproval[task.status] || task.status}
                        </Tag>
                      </div>
                      {task.comment && (
                        <div className="text-sm text-slate-500 mt-1">意见: {task.comment}</div>
                      )}
                      {task.decided_at && (
                        <div className="text-[13px] text-slate-400 mt-0.5">{task.decided_at}</div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Withdraw Modal */}
      <Modal
        title="撤回审批"
        open={withdrawModal}
        onOk={handleWithdraw}
        onCancel={() => setWithdrawModal(false)}
        confirmLoading={submitting}
        okText="确认撤回"
      >
        <div className="py-2">
          <label className="text-sm font-medium text-slate-700 mb-1 block">撤回原因（选填）</label>
          <Input.TextArea
            value={withdrawReason}
            onChange={(e) => setWithdrawReason(e.target.value)}
            rows={3}
            placeholder="请填写撤回原因..."
          />
        </div>
      </Modal>

      {/* Delegate Modal */}
      <Modal
        title="转交审批"
        open={delegateModal}
        onOk={handleDelegate}
        onCancel={() => setDelegateModal(false)}
        confirmLoading={submitting}
        okText="确认转交"
      >
        <div className="py-2 space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">选择目标审批人</label>
            <Select
              className="w-full"
              placeholder="选择用户"
              value={delegateUserId || undefined}
              onChange={setDelegateUserId}
              showSearch
              filterOption={false}
              loading={userSelect.loading}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onDropdownVisibleChange={userSelect.onDropdownVisibleChange}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">转交原因（选填）</label>
            <Input.TextArea
              value={delegateReason}
              onChange={(e) => setDelegateReason(e.target.value)}
              rows={2}
              placeholder="请填写转交原因..."
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
