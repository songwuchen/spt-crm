import { useState, useEffect } from 'react'
import { Tabs, Table, Tag, Space, Modal, Input, Button, message, Spin } from 'antd'
import { CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { approvalApi } from '@/api/approval'
import client from '@/api/client'
import { useAuthStore } from '@/stores/useAuthStore'
import type { ApprovalFlowItem, ApprovalPendingItem } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { approvalBizTypeLabels as bizTypeLabels, approvalStatusColors as statusColors, approvalStatusLabels as statusLabels } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'

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

  const fetchData = async () => {
    setLoading(true)
    try {
      const [pRes, fRes] = await Promise.all([
        approvalApi.myPending(),
        approvalApi.list(),
      ])
      setPending(pRes.data || [])
      setAllFlows(fRes.data || [])
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
      await approvalApi.decide(currentTask.id, { action: decideAction, comment: comment || undefined })
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
        // Fetch quote version to get the quote → project link
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
        navigate(`/opportunities/${bizId}`)
        return
      } else if (bizType === 'solution') {
        navigate(`/opportunities/${bizId}`)
        return
      }
    } catch {
      // Fallback: just show a message
    }
    message.info('无法定位到具体业务页面')
  }

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
      title: '发起人', dataIndex: ['flow', 'submitted_by_name'], width: 100,
    },
    {
      title: '进度', key: 'progress', width: 100,
      render: (_, r) => <span className="text-xs text-slate-500">{r.flow.current_node}/{r.flow.total_nodes} 节点</span>,
    },
    {
      title: '发起时间', dataIndex: ['flow', 'created_at'], width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '操作', key: 'actions', width: 160,
      render: (_, r) => (
        <Space>
          <Button type="primary" size="small" icon={<CheckCircleOutlined />}
            onClick={() => openDecide(r, 'approve')}>通过</Button>
          <Button danger size="small" icon={<CloseCircleOutlined />}
            onClick={() => openDecide(r, 'reject')}>驳回</Button>
        </Space>
      ),
    },
  ]

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
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v] || v}</Tag>,
    },
    {
      title: '发起人', dataIndex: 'submitted_by_name', width: 100,
    },
    {
      title: '进度', key: 'progress', width: 100,
      render: (_, r) => <span className="text-xs text-slate-500">{r.current_node}/{r.total_nodes} 节点</span>,
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

  if (loading) return <DetailSkeleton />

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">审批中心</h1>
        <p className="text-sm text-slate-500 mt-1">管理待审批任务和审批历史</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <Tabs defaultActiveKey="pending" className="px-4 pt-2"
          items={[
            {
              key: 'pending',
              label: <span>待我审批 {pending.length > 0 && <Tag color="red" className="ml-1">{pending.length}</Tag>}</span>,
              children: (
                <Table rowKey="id" columns={pendingColumns} dataSource={pending}
                  pagination={false} size="small"
                  locale={{ emptyText: <div className="py-8 text-slate-400">暂无待审批任务</div> }} />
              ),
            },
            {
              key: 'mine',
              label: '我发起的',
              children: (
                <Table rowKey="id" columns={historyColumns}
                  dataSource={allFlows.filter((f) => f.submitted_by_id === userInfo?.id)}
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
              <div className="text-xs text-slate-500 mt-1">
                类型: {bizTypeLabels[currentTask.flow?.biz_type] || currentTask.flow?.biz_type} ·
                发起人: {currentTask.flow?.submitted_by_name} ·
                节点 {currentTask.node_order}/{currentTask.flow?.total_nodes}
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
        width={600}
      >
        {detailLoading ? (
          <div className="flex justify-center py-8"><Spin /></div>
        ) : detailFlow ? (
          <div>
            <div className="mb-4 p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-lg font-bold text-slate-900">{detailFlow.title || '审批申请'}</span>
                <Tag color={statusColors[detailFlow.status]}>{statusLabels[detailFlow.status] || detailFlow.status}</Tag>
              </div>
              <div className="text-sm text-slate-500">
                类型: {bizTypeLabels[detailFlow.biz_type] || detailFlow.biz_type} ·
                发起人: {detailFlow.submitted_by_name} ·
                发起时间: {detailFlow.created_at ? new Date(detailFlow.created_at).toLocaleString('zh-CN') : '-'}
              </div>
              {detailFlow.biz_id && (
                <Button size="small" className="mt-2" onClick={() => { setDetailModal(false); navigateToBiz(detailFlow.biz_type, detailFlow.biz_id) }}>
                  查看关联业务
                </Button>
              )}
            </div>

            {/* Approval Timeline */}
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-3">审批流程</h4>
            <div className="space-y-3">
              {(detailFlow.tasks || []).map((task, idx) => {
                const isApproved = task.status === 'approved'
                const isRejected = task.status === 'rejected'
                const isPending = task.status === 'pending'
                return (
                  <div key={task.id} className="flex items-start gap-3">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      isApproved ? 'bg-emerald-100 text-emerald-600' :
                      isRejected ? 'bg-red-100 text-red-600' :
                      'bg-slate-100 text-slate-400'
                    }`}>
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                        {isApproved ? 'check' : isRejected ? 'close' : 'schedule'}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-slate-800">
                          节点 {task.node_order}: {task.assignee_name || '审批人'}
                        </span>
                        <Tag color={isApproved ? 'success' : isRejected ? 'error' : 'default'}>
                          {isApproved ? '已通过' : isRejected ? '已驳回' : '待审批'}
                        </Tag>
                      </div>
                      {task.comment && (
                        <div className="text-xs text-slate-500 mt-1">意见: {task.comment}</div>
                      )}
                      {task.decided_at && (
                        <div className="text-[11px] text-slate-400 mt-0.5">{task.decided_at}</div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
