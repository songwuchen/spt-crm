import { useState, useEffect, useMemo } from 'react'
import { Tabs, Table, Tag, Space, Modal, Input, Button, message, Spin, Checkbox, Select, Card, Statistic, Row, Col, DatePicker } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined, SwapOutlined, UndoOutlined, RedoOutlined, BarChartOutlined, FilterOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { approvalApi } from '@/api/approval'
import client from '@/api/client'
import { useAuthStore } from '@/stores/useAuthStore'
import type { ApprovalFlowItem, ApprovalPendingItem } from '@/api/types'
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

export default function ApprovalCenter() {
  usePageTitle('审批中心')
  const navigate = useNavigate()
  const userInfo = useAuthStore((s) => s.user)
  const [pending, setPending] = useState<ApprovalPendingItem[]>([])
  const [allFlows, setAllFlows] = useState<ApprovalFlowItem[]>([])
  const [loading, setLoading] = useState(true)
  const [decideModal, setDecideModal] = useState(false)
  const [currentTask, setCurrentTask] = useState<ApprovalPendingItem | null>(null)
  const [decideAction, setDecideAction] = useState<'approve' | 'reject'>('approve')
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // Detail modal
  const [detailModal, setDetailModal] = useState(false)
  const [detailFlow, setDetailFlow] = useState<ApprovalFlowItem | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  // Delegate modal
  const [delegateModal, setDelegateModal] = useState(false)
  const [delegateTaskId, setDelegateTaskId] = useState('')
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
      const [pRes, fRes] = await Promise.all([
        approvalApi.myPending(),
        approvalApi.list(),
      ])
      setPending(pRes.data || [])
      setAllFlows(fRes.data?.items || [])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const openDecide = (task: ApprovalPendingItem, action: 'approve' | 'reject') => {
    setCurrentTask(task)
    setDecideAction(action)
    setComment('')
    setDecideModal(true)
  }

  const handleDecide = async () => {
    if (!currentTask) return
    setSubmitting(true)
    try {
      await approvalApi.decide(currentTask.id, { action: decideAction === 'approve' ? 'approved' : 'rejected', comment: comment || undefined })
      message.success(decideAction === 'approve' ? '已通过' : '已驳回')
      setDecideModal(false)
      fetchData()
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
  const openWithdraw = (flowId: string) => {
    setWithdrawFlowId(flowId)
    setWithdrawReason('')
    setWithdrawModal(true)
  }

  const handleWithdraw = async () => {
    setSubmitting(true)
    try {
      await approvalApi.withdraw(withdrawFlowId, { reason: withdrawReason || undefined })
      message.success('审批已撤回')
      setWithdrawModal(false)
      fetchData()
    } finally {
      setSubmitting(false)
    }
  }

  // Delegate
  const openDelegate = (taskId: string) => {
    setDelegateTaskId(taskId)
    setDelegateUserId('')
    setDelegateReason('')
    setDelegateModal(true)
  }

  const handleDelegate = async () => {
    if (!delegateUserId) { message.warning('请选择目标审批人'); return }
    setSubmitting(true)
    try {
      await approvalApi.delegate(delegateTaskId, { target_user_id: delegateUserId, reason: delegateReason || undefined })
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
    const label = action === 'approved' ? '通过' : '驳回'
    Modal.confirm({
      title: `批量${label}确认`,
      content: `确定要${label} ${selectedRowKeys.length} 条审批任务吗？`,
      onOk: async () => {
        setSubmitting(true)
        try {
          const res = await approvalApi.bulkDecide({ task_ids: selectedRowKeys, action })
          const results = res.data || []
          const successCount = results.filter((r: any) => r.success).length
          const failCount = results.filter((r: any) => !r.success).length
          message.info(`完成: 成功 ${successCount} 条，失败 ${failCount} 条`)
          setSelectedRowKeys([])
          fetchData()
        } finally {
          setSubmitting(false)
        }
      },
    })
  }

  // Resubmit
  const handleResubmit = async (flowId: string) => {
    setSubmitting(true)
    try {
      await approvalApi.resubmit(flowId, {})
      message.success('审批已重新提交')
      fetchData()
    } finally {
      setSubmitting(false)
    }
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
      list = list.filter((p) => p.flow?.biz_type === filterBizType)
    }
    if (filterDateRange && filterDateRange[0] && filterDateRange[1]) {
      const start = filterDateRange[0].startOf('day').valueOf()
      const end = filterDateRange[1].endOf('day').valueOf()
      list = list.filter((p) => {
        const t = p.flow?.created_at ? new Date(p.flow.created_at).getTime() : 0
        return t >= start && t <= end
      })
    }
    return list
  }, [pending, filterBizType, filterDateRange])

  const pendingBizTypes = useMemo(() => {
    const types = new Set(pending.map((p) => p.flow?.biz_type).filter(Boolean))
    return Array.from(types).map((t) => ({ value: t!, label: bizTypeLabels[t!] || t! }))
  }, [pending])

  const pendingColumns: ColumnsType<ApprovalPendingItem> = [
    {
      title: '审批标题', dataIndex: ['flow', 'title'], width: 280,
      render: (v: string, r) => (
        <a className="font-semibold text-primary cursor-pointer" onClick={() => openDetail(r.flow_id)}>{v || '审批申请'}</a>
      ),
    },
    {
      title: '类型', dataIndex: ['flow', 'biz_type'], width: 120,
      render: (v: string) => <Tag color="blue">{bizTypeLabels[v] || v}</Tag>,
    },
    {
      title: '模式', dataIndex: ['flow', 'approval_mode'], width: 100,
      render: (v: string) => v ? <Tag color={approvalModeColors[v] || 'blue'}>{approvalModeLabels[v] || v}</Tag> : null,
    },
    {
      title: '发起人', dataIndex: ['flow', 'submitted_by_name'], width: 100,
    },
    {
      title: '进度', key: 'progress', width: 100,
      render: (_, r) => <span className="text-sm text-slate-500">{r.flow.current_node}/{r.flow.total_nodes} 节点</span>,
    },
    {
      title: '发起时间', dataIndex: ['flow', 'created_at'], width: 160,
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
      title: '操作', key: 'actions', width: 220,
      render: (_, r) => (
        <Space>
          <Button type="primary" size="small" icon={<CheckCircleOutlined />}
            onClick={() => openDecide(r, 'approve')}>通过</Button>
          <Button danger size="small" icon={<CloseCircleOutlined />}
            onClick={() => openDecide(r, 'reject')}>驳回</Button>
          <Button size="small" icon={<SwapOutlined />}
            onClick={() => openDelegate(r.id)}>转交</Button>
        </Space>
      ),
    },
  ]

  const myFlows = allFlows.filter((f) => f.submitted_by_id === userInfo?.id)

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

  const mineColumns: ColumnsType<ApprovalFlowItem> = [
    ...historyColumns,
    {
      title: '操作', key: 'actions', width: 160,
      render: (_, r) => (
        <Space>
          {r.status === 'pending' && (
            <Button size="small" icon={<UndoOutlined />} onClick={() => openWithdraw(r.id)}>撤回</Button>
          )}
          {r.status === 'rejected' && (
            <Button size="small" type="primary" icon={<RedoOutlined />} onClick={() => handleResubmit(r.id)}>重新提交</Button>
          )}
        </Space>
      ),
    },
  ]

  if (loading) return <DetailSkeleton />

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">审批中心</h1>
        <p className="text-sm text-slate-500 mt-1">管理待审批任务和审批历史</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <Tabs defaultActiveKey="pending" className="px-4 pt-2"
          onChange={(key) => { if (key === 'stats' && !stats) loadStats() }}
          items={[
            {
              key: 'pending',
              label: <span>待我审批 {pending.length > 0 && <Tag color="red" className="ml-1">{pending.length}</Tag>}</span>,
              children: (
                <div>
                  {pending.length > 0 && (
                    <div className="mb-3 flex flex-wrap items-center gap-2">
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
                  <Table rowKey="id" columns={pendingColumns} dataSource={filteredPending}
                    rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys as string[]) }}
                    pagination={false} size="small"
                    locale={{ emptyText: <div className="py-8 text-slate-400">暂无待审批任务</div> }} />
                </div>
              ),
            },
            {
              key: 'mine',
              label: '我发起的',
              children: (
                <Table rowKey="id" columns={mineColumns}
                  dataSource={myFlows}
                  pagination={{ pageSize: 15, showSizeChanger: false }} size="small"
                  locale={{ emptyText: <div className="py-8 text-slate-400">暂无发起的审批</div> }} />
              ),
            },
            {
              key: 'all',
              label: '所有审批',
              children: (
                <Table rowKey="id" columns={historyColumns} dataSource={allFlows}
                  pagination={{ pageSize: 15, showSizeChanger: false }} size="small" />
              ),
            },
            {
              key: 'stats',
              label: <span><BarChartOutlined className="mr-1" />统计</span>,
              children: statsLoading ? (
                <div className="flex justify-center py-12"><Spin /></div>
              ) : stats ? (
                <div className="py-4">
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
              <div className="text-sm font-bold text-slate-800">{currentTask.flow?.title || '审批申请'}</div>
              <div className="text-sm text-slate-500 mt-1">
                类型: {bizTypeLabels[currentTask.flow?.biz_type] || currentTask.flow?.biz_type} ·
                发起人: {currentTask.flow?.submitted_by_name} ·
                节点 {currentTask.node_order}/{currentTask.flow?.total_nodes}
                {currentTask.flow?.approval_mode && currentTask.flow.approval_mode !== 'sequential' && (
                  <Tag color={approvalModeColors[currentTask.flow.approval_mode]} className="ml-2">
                    {approvalModeLabels[currentTask.flow.approval_mode]}
                  </Tag>
                )}
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
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                        {isApproved ? 'check' : isRejected ? 'close' : isCancelled ? 'block' : isPending ? 'schedule' : 'hourglass_empty'}
                      </span>
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
