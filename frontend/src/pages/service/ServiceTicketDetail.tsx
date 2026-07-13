import { useState, useEffect } from 'react'
import { Button, Tag, Select, Input, Space, Spin, Descriptions, Modal, Rate, Table, message } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { serviceTicketApi } from '@/api/serviceTicket'
import { orderApi } from '@/api/order'
import { activityApi } from '@/api/activity'
import AttachmentPanel from '@/components/AttachmentPanel'
import ActivityTimeline from '@/components/ActivityTimeline'
import type { ServiceTicketItem, ActivityItem, Order } from '@/api/types'
import { ticketTypeLabels as typeLabels, ticketPriorityLabels as priorityLabels, ticketPriorityColors as priorityColors, ticketStatusColors as statusColors, ticketStatusLabels as statusLabels } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'
import { useUserSelect } from '@/hooks/useSelectOptions'
import SubscribeButton from '@/components/SubscribeButton'
import SlaCountdown from '@/components/SlaCountdown'
import InternalNotes from '@/components/InternalNotes'
import DataView from '@/components/DataView'

const { TextArea } = Input
const statusFlow: Record<string, string[]> = {
  open: ['assigned', 'in_progress'],
  assigned: ['in_progress'],
  in_progress: ['resolved'],
  resolved: ['closed'],
  closed: [],
}

export default function ServiceTicketDetail() {
  usePageTitle('工单详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [ticket, setTicket] = useState<ServiceTicketItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [orderInfo, setOrderInfo] = useState<Order | null>(null)
  const [submitting, setSubmitting] = useState(false)

  // Edit fields
  const [editModal, setEditModal] = useState(false)
  const [editDesc, setEditDesc] = useState('')
  const [editResolution, setEditResolution] = useState('')
  const [editPriority, setEditPriority] = useState('')

  // Assign modal
  const [assignModal, setAssignModal] = useState(false)
  const [assigneeId, setAssigneeId] = useState('')

  // Satisfaction rating
  const [rateScore, setRateScore] = useState(0)
  const [rateComment, setRateComment] = useState('')
  const [rateSubmitting, setRateSubmitting] = useState(false)

  // Knowledge base
  const [kbKeyword, setKbKeyword] = useState('')
  const [kbResults, setKbResults] = useState<{ id: string; ticket_no: string; type: string; description: string; resolution: string }[]>([])
  const [kbLoading, setKbLoading] = useState(false)
  const [kbOpen, setKbOpen] = useState(false)

  const searchKnowledge = async (kw: string) => {
    if (kw.length < 2) return
    setKbLoading(true)
    try {
      const r = await serviceTicketApi.knowledgeSearch(kw)
      setKbResults(r.data || [])
    } finally { setKbLoading(false) }
  }

  const userSelect = useUserSelect()

  const fetchTicket = async () => {
    setLoading(true)
    try {
      const res = await serviceTicketApi.get(id!)
      setTicket(res.data)
      if (res.data.order_id) {
        orderApi.get(res.data.order_id).then((r) => setOrderInfo(r.data)).catch(() => setOrderInfo(null))
      } else {
        setOrderInfo(null)
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSubmitApproval = () => {
    Modal.confirm({
      title: '提交售后审批', content: `确认提交工单 ${ticket?.ticket_no} 进入审批流程（生产主任审批并分配售后人员）？`,
      onOk: async () => {
        setSubmitting(true)
        try { await serviceTicketApi.submit(id!); message.success('已提交审批，请在审批中心查看进度') }
        catch { message.error('提交失败，请确认已在「系统设置→审批策略」配置售后审批') }
        finally { setSubmitting(false) }
        fetchTicket()
      },
    })
  }

  const fetchActivities = async () => {
    try {
      const res = await activityApi.list('service_ticket', id!)
      setActivities(res.data || [])
    } catch { /* ignore */ }
  }

  useEffect(() => {
    fetchTicket()
    fetchActivities()
  }, [id])

  const handleStatusChange = async (newStatus: string) => {
    await serviceTicketApi.update(id!, { status: newStatus })
    message.success('状态已更新')
    fetchTicket()
  }

  const handleEditSave = async () => {
    await serviceTicketApi.update(id!, {
      description: editDesc,
      resolution: editResolution,
      priority: editPriority,
    })
    message.success('已更新')
    setEditModal(false)
    fetchTicket()
  }

  const openEditModal = () => {
    if (!ticket) return
    setEditDesc(ticket.description || '')
    setEditResolution(ticket.resolution || '')
    setEditPriority(ticket.priority)
    setEditModal(true)
  }

  const openAssignModal = () => {
    setAssigneeId(ticket?.assigned_to_id || '')
    // 播种当前受理人姓名，否则已分配工单再分配时 value 会直接显示为 id
    if (ticket?.assigned_to_id && ticket?.assigned_to_name) {
      userSelect.setInitialOption({ label: ticket.assigned_to_name, value: ticket.assigned_to_id })
    }
    setAssignModal(true)
  }

  const handleAssign = async () => {
    const userOpt = userSelect.options.find((o) => o.value === assigneeId)
    await serviceTicketApi.update(id!, {
      assigned_to_id: assigneeId,
      assigned_to_name: userOpt?.label || '',
      status: ticket?.status === 'open' ? 'assigned' : undefined,
    })
    message.success('已分配')
    setAssignModal(false)
    fetchTicket()
  }

  if (loading || !ticket) return <DetailSkeleton />

  const nextStatuses = statusFlow[ticket.status] || []

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h1 className="text-2xl font-bold text-slate-900">{ticket.ticket_no}</h1>
            <Tag color={statusColors[ticket.status]}>{statusLabels[ticket.status] || ticket.status}</Tag>
            <Tag color={priorityColors[ticket.priority]}>{priorityLabels[ticket.priority] || ticket.priority}</Tag>
            <Tag>{typeLabels[ticket.type] || ticket.type}</Tag>
          </div>
          <p className="text-sm text-slate-500">
            创建人: {ticket.created_by_name || '-'} · {ticket.created_at ? new Date(ticket.created_at).toLocaleString('zh-CN') : ''}
          </p>
        </div>
        <Space>
          {nextStatuses.map((s) => (
            <Button key={s} type={s === 'resolved' || s === 'closed' ? 'primary' : 'default'}
              onClick={() => handleStatusChange(s)}>
              {statusLabels[s]}
            </Button>
          ))}
          {(ticket.status === 'open' || ticket.status === 'assigned') && (
            <Button type="primary" ghost loading={submitting} onClick={handleSubmitApproval}>提交审批</Button>
          )}
          <Button onClick={openAssignModal}>分配</Button>
          <Button onClick={openEditModal}>编辑</Button>
          <SubscribeButton bizType="service_ticket" bizId={id!} bizName={ticket.ticket_no} />
          <Button onClick={() => navigate('/service-tickets')}>返回列表</Button>
        </Space>
      </div>

      {/* SLA Countdown */}
      {(ticket.sla_respond_by || ticket.sla_resolve_by) && (
        <div className="flex gap-4 mb-6">
          <SlaCountdown label="响应时限" deadline={ticket.sla_respond_by} completedAt={ticket.sla_responded_at} />
          <SlaCountdown label="解决时限" deadline={ticket.sla_resolve_by} completedAt={ticket.sla_resolved_at} />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Main Content */}
        <div className="lg:col-span-2 space-y-4">
          {/* Description */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-slate-400" style={{ fontSize: 18 }}>description</span>
              问题描述
            </h3>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{ticket.description || '暂无描述'}</p>
          </div>

          {/* 关联订单 + 产品信息 */}
          {orderInfo && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                  <span className="material-symbols-outlined text-indigo-500" style={{ fontSize: 18 }}>inventory_2</span>
                  关联订单 · 产品信息
                </h3>
                <a className="text-primary text-sm font-bold" onClick={() => navigate('/orders')}>
                  {orderInfo.order_no}
                </a>
              </div>
              <Table
                rowKey={(r, i) => (r.id || String(i)) as string}
                size="small" pagination={false}
                dataSource={orderInfo.lines || []}
                locale={{ emptyText: '该订单暂无产品明细' }}
                columns={[
                  { title: '产品名称', dataIndex: 'product_name' },
                  { title: '规格型号', dataIndex: 'spec', render: (v: string) => v || '-' },
                  { title: '单位', dataIndex: 'unit', width: 60, render: (v: string) => v || '-' },
                  { title: '数量', dataIndex: 'quantity', width: 70, align: 'right' },
                ]}
              />
            </div>
          )}

          {/* Resolution */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-500" style={{ fontSize: 18 }}>check_circle</span>
              解决方案
            </h3>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{ticket.resolution || '暂未填写'}</p>
          </div>

          {/* Satisfaction Rating */}
          {(ticket.status === 'resolved' || ticket.status === 'closed') && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-amber-500" style={{ fontSize: 18 }}>star</span>
                满意度评价
              </h3>
              {ticket.satisfaction_score ? (
                <div>
                  <div className="flex items-center gap-3 mb-2">
                    <Rate disabled value={ticket.satisfaction_score} />
                    <span className="text-sm font-bold text-slate-700">{ticket.satisfaction_score}/5</span>
                  </div>
                  {ticket.satisfaction_comment && (
                    <div className="text-sm text-slate-600 bg-slate-50 rounded-lg p-3">{ticket.satisfaction_comment}</div>
                  )}
                  {ticket.satisfaction_at && (
                    <div className="text-sm text-slate-400 mt-2">评价时间: {new Date(ticket.satisfaction_at).toLocaleString('zh-CN')}</div>
                  )}
                </div>
              ) : (
                <div>
                  <div className="mb-3">
                    <Rate value={rateScore} onChange={setRateScore} />
                    {rateScore > 0 && <span className="ml-2 text-sm text-slate-500">{['', '非常不满意', '不满意', '一般', '满意', '非常满意'][rateScore]}</span>}
                  </div>
                  <Input.TextArea rows={2} placeholder="请输入评价内容（可选）" value={rateComment} onChange={(e) => setRateComment(e.target.value)} className="mb-3" />
                  <Button type="primary" size="small" disabled={rateScore === 0} loading={rateSubmitting}
                    onClick={async () => {
                      setRateSubmitting(true)
                      try {
                        const res = await serviceTicketApi.rate(id!, { score: rateScore, comment: rateComment })
                        setTicket(res.data)
                        message.success('评价已提交')
                      } catch { message.error('评价失败') }
                      finally { setRateSubmitting(false) }
                    }}>提交评价</Button>
                </div>
              )}
            </div>
          )}

          {/* Knowledge Base Search */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <span className="material-symbols-outlined text-blue-500" style={{ fontSize: 18 }}>menu_book</span>
                知识库
              </h3>
              <Button size="small" onClick={() => setKbOpen(!kbOpen)}>{kbOpen ? '收起' : '搜索类似工单'}</Button>
            </div>
            {kbOpen && (
              <div>
                <Input.Search placeholder="输入关键词搜索历史解决方案..." value={kbKeyword}
                  onChange={(e) => setKbKeyword(e.target.value)}
                  onSearch={searchKnowledge} loading={kbLoading} enterButton className="mb-3" />
                {kbResults.length > 0 ? (
                  <div className="space-y-2 max-h-64 overflow-auto">
                    {kbResults.map((r) => (
                      <div key={r.id} className="border border-slate-100 rounded-lg p-3 hover:bg-slate-50">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="font-mono text-sm text-slate-400">{r.ticket_no}</span>
                          <Tag className="text-[12px]">{typeLabels[r.type] || r.type}</Tag>
                        </div>
                        <div className="text-sm text-slate-500 mb-1">{r.description}</div>
                        <div className="text-sm text-emerald-700 bg-emerald-50 rounded p-2 mt-1">
                          <span className="font-bold">解决方案: </span>{r.resolution}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : kbKeyword && !kbLoading ? (
                  <div className="text-center text-sm text-slate-400 py-4">未找到相关解决方案</div>
                ) : null}
              </div>
            )}
          </div>

          {/* Attachments */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-3">附件</h3>
            <AttachmentPanel bizType="service_ticket" bizId={id!} />
          </div>

          {/* Internal Notes */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-amber-500" style={{ fontSize: 18 }}>sticky_note_2</span>
              内部备忘
            </h3>
            <InternalNotes bizType="service_ticket" bizId={id!} />
          </div>

          {/* Activity Timeline */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <ActivityTimeline bizType="service_ticket" bizId={id!} />
          </div>
        </div>

        {/* Right: Sidebar */}
        <div className="space-y-4">
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-3">工单信息</h3>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="工单编号">
                <span className="font-mono text-sm">{ticket.ticket_no}</span>
              </Descriptions.Item>
              <Descriptions.Item label="类型">
                <Tag>{typeLabels[ticket.type] || ticket.type}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="优先级">
                <Tag color={priorityColors[ticket.priority]}>{priorityLabels[ticket.priority]}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusColors[ticket.status]}>{statusLabels[ticket.status]}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="负责人">
                {ticket.assigned_to_name || <span className="text-slate-400">未分配</span>}
              </Descriptions.Item>
              <Descriptions.Item label="创建人">{ticket.created_by_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {ticket.created_at ? new Date(ticket.created_at).toLocaleString('zh-CN') : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="更新时间">
                {ticket.updated_at ? new Date(ticket.updated_at).toLocaleString('zh-CN') : '-'}
              </Descriptions.Item>
            </Descriptions>
          </div>

          {ticket.ai_summary_json && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
              <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
                <span className="material-symbols-outlined text-purple-500" style={{ fontSize: 18 }}>psychology</span>
                AI 摘要
              </h3>
              <DataView value={ticket.ai_summary_json} />
            </div>
          )}
        </div>
      </div>

      {/* Edit Modal */}
      <Modal title="编辑工单" open={editModal} onOk={handleEditSave} onCancel={() => setEditModal(false)} width={600}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">优先级</label>
            <Select className="w-full" value={editPriority} onChange={setEditPriority}
              options={Object.entries(priorityLabels).map(([k, v]) => ({ value: k, label: v }))} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">问题描述</label>
            <TextArea rows={4} value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">解决方案</label>
            <TextArea rows={4} value={editResolution} onChange={(e) => setEditResolution(e.target.value)} placeholder="填写解决方案..." />
          </div>
        </div>
      </Modal>

      {/* Assign Modal */}
      <Modal title="分配工单" open={assignModal} onOk={handleAssign} onCancel={() => setAssignModal(false)}>
        <div className="py-2">
          <label className="text-sm font-medium text-slate-700 mb-1 block">选择负责人</label>
          <Select className="w-full" value={assigneeId} onChange={setAssigneeId} showSearch
            filterOption={false}
            loading={userSelect.loading}
            options={userSelect.options}
            onSearch={userSelect.onSearch}
            onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
        </div>
      </Modal>
    </div>
  )
}
