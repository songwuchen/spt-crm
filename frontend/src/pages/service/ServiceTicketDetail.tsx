import { useState, useEffect } from 'react'
import { Button, Tag, Select, Input, Space, Spin, Descriptions, Modal, message } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import { serviceTicketApi } from '@/api/serviceTicket'
import { activityApi } from '@/api/activity'
import { userApi } from '@/api/user'
import AttachmentPanel from '@/components/AttachmentPanel'
import ActivityTimeline from '@/components/ActivityTimeline'
import type { ServiceTicketItem, ActivityItem } from '@/api/types'
import { ticketTypeLabels as typeLabels, ticketPriorityLabels as priorityLabels, ticketPriorityColors as priorityColors, ticketStatusColors as statusColors, ticketStatusLabels as statusLabels } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import DetailSkeleton from '@/components/DetailSkeleton'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import SubscribeButton from '@/components/SubscribeButton'

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

  // Edit fields
  const [editModal, setEditModal] = useState(false)
  const [editDesc, setEditDesc] = useState('')
  const [editResolution, setEditResolution] = useState('')
  const [editPriority, setEditPriority] = useState('')

  // Assign modal
  const [assignModal, setAssignModal] = useState(false)
  const [assigneeId, setAssigneeId] = useState('')

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

  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  const fetchTicket = async () => {
    setLoading(true)
    try {
      const res = await serviceTicketApi.get(id!)
      setTicket(res.data)
    } finally {
      setLoading(false)
    }
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
          <Button onClick={openAssignModal}>分配</Button>
          <Button onClick={openEditModal}>编辑</Button>
          <SubscribeButton bizType="service_ticket" bizId={id!} bizName={ticket.ticket_no} />
          <Button onClick={() => navigate('/service-tickets')}>返回列表</Button>
        </Space>
      </div>

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

          {/* Resolution */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
            <h3 className="text-sm font-bold text-slate-900 mb-3 flex items-center gap-2">
              <span className="material-symbols-outlined text-emerald-500" style={{ fontSize: 18 }}>check_circle</span>
              解决方案
            </h3>
            <p className="text-sm text-slate-700 whitespace-pre-wrap">{ticket.resolution || '暂未填写'}</p>
          </div>

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
                          <span className="font-mono text-xs text-slate-400">{r.ticket_no}</span>
                          <Tag className="text-[10px]">{typeLabels[r.type] || r.type}</Tag>
                        </div>
                        <div className="text-xs text-slate-500 mb-1">{r.description}</div>
                        <div className="text-xs text-emerald-700 bg-emerald-50 rounded p-2 mt-1">
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
              <pre className="bg-slate-50 p-3 rounded-lg text-xs text-slate-700 overflow-auto">
                {JSON.stringify(ticket.ai_summary_json, null, 2)}
              </pre>
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
