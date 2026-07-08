import { useState, useEffect, useMemo } from 'react'
import { Table, Tag, Button, Space, Switch, Tabs, message, Select } from 'antd'
import { CheckOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { notificationApi, type NotificationItem } from '@/api/notification'
import { usePageTitle } from '@/hooks/usePageTitle'

const typeLabels: Record<string, { label: string; color: string }> = {
  approval_pending: { label: '审批待处理', color: 'orange' },
  approval_decided: { label: '审批已决定', color: 'green' },
  approval_sla_overdue: { label: '审批超时', color: 'red' },
  stage_advance: { label: '阶段推进', color: 'blue' },
  stage_change: { label: '阶段变化', color: 'blue' },
  contract_signed: { label: '合同签署', color: 'green' },
  ticket_assigned: { label: '工单分配', color: 'cyan' },
  task_assigned: { label: '任务分配', color: 'cyan' },
  lead_assigned: { label: '线索分配', color: 'cyan' },
  customer_assigned: { label: '客户分配', color: 'cyan' },
  payment_overdue: { label: '回款逾期', color: 'red' },
  receivable_overdue: { label: '应收逾期', color: 'red' },
  guarantee_expiring: { label: '保函到期', color: 'orange' },
  payment_received: { label: '收到回款', color: 'green' },
  ai_task_complete: { label: 'AI完成', color: 'purple' },
  gate_blocked: { label: '门禁拦截', color: 'orange' },
  mention: { label: '提及我', color: 'blue' },
  scheduled_report: { label: '定时报表', color: 'default' },
  system: { label: '系统', color: 'default' },
}

export default function NotificationCenter() {
  usePageTitle('通知中心')
  const navigate = useNavigate()
  const [items, setItems] = useState<NotificationItem[]>([])
  const [loading, setLoading] = useState(false)
  const [filter, setFilter] = useState<string | undefined>(undefined)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [prefTypes, setPrefTypes] = useState<{ key: string; label: string }[]>([])
  const [prefs, setPrefs] = useState<Record<string, boolean>>({})
  const [prefLoading, setPrefLoading] = useState(false)
  const [unreadOnly, setUnreadOnly] = useState(false)

  const fetchData = async () => {
    setLoading(true)
    try {
      const res = await notificationApi.list()
      setItems(res.data || [])
    } finally {
      setLoading(false)
    }
  }

  const fetchPrefs = async () => {
    setPrefLoading(true)
    try {
      const res = await notificationApi.getPreferences()
      setPrefTypes(res.data?.types || [])
      setPrefs(res.data?.preferences || {})
    } finally { setPrefLoading(false) }
  }

  const togglePref = async (key: string, enabled: boolean) => {
    const newPrefs = { ...prefs, [key]: enabled }
    setPrefs(newPrefs)
    try {
      await notificationApi.updatePreferences(newPrefs)
      message.success(enabled ? '已开启' : '已关闭')
    } catch {
      setPrefs(prefs) // rollback
      message.error('更新失败')
    }
  }

  useEffect(() => { fetchData() }, [])

  const filteredItems = items.filter(n => {
    if (filter && n.type !== filter) return false
    if (unreadOnly && n.is_read) return false
    return true
  })

  const handleMarkRead = async () => {
    if (selectedIds.length === 0) return
    try {
      await notificationApi.markRead(selectedIds)
      setItems(prev => prev.map(n => selectedIds.includes(n.id) ? { ...n, is_read: true } : n))
      setSelectedIds([])
      message.success('已标记为已读')
    } catch {
      message.error('操作失败')
    }
  }

  const handleMarkAllRead = async () => {
    try {
      await notificationApi.markAllRead()
      setItems(prev => prev.map(n => ({ ...n, is_read: true })))
      message.success('已全部标记为已读')
    } catch {
      message.error('操作失败')
    }
  }

  const handleRowClick = (item: NotificationItem) => {
    if (!item.is_read) {
      notificationApi.markRead([item.id])
      setItems(prev => prev.map(n => n.id === item.id ? { ...n, is_read: true } : n))
    }
    if (item.biz_type === 'approval_flow' || item.biz_type === 'approval') {
      navigate('/approvals')
    } else if (item.biz_type === 'service_ticket') {
      navigate(`/service-tickets/${item.biz_id}`)
    } else if (item.biz_type === 'project') {
      navigate(`/opportunities/${item.biz_id}`)
    } else if (item.biz_type === 'customer' && item.biz_id) {
      navigate(`/customers/${item.biz_id}`)
    }
  }

  const columns = [
    {
      title: '类型',
      dataIndex: 'type',
      width: 120,
      render: (type: string) => {
        const t = typeLabels[type] || typeLabels.system
        return <Tag color={t.color}>{t.label}</Tag>
      },
    },
    {
      title: '标题',
      dataIndex: 'title',
      render: (title: string, record: NotificationItem) => (
        <span className={!record.is_read ? 'font-bold' : ''}>{title}</span>
      ),
    },
    {
      title: '内容',
      dataIndex: 'content',
      ellipsis: true,
    },
    {
      title: '时间',
      dataIndex: 'created_at',
      width: 160,
      render: (v: string) => {
        if (!v) return ''
        const d = new Date(v)
        const diff = Date.now() - d.getTime()
        const mins = Math.floor(diff / 60000)
        if (mins < 1) return <span className="text-sm text-slate-500">刚刚</span>
        if (mins < 60) return <span className="text-sm text-slate-500">{mins}分钟前</span>
        const hours = Math.floor(mins / 60)
        if (hours < 24) return <span className="text-sm text-slate-500">{hours}小时前</span>
        const days = Math.floor(hours / 24)
        if (days < 7) return <span className="text-sm text-slate-500">{days}天前</span>
        return <span className="text-sm text-slate-500">{d.toLocaleDateString('zh-CN')}</span>
      },
    },
    {
      title: '状态',
      dataIndex: 'is_read',
      width: 80,
      render: (v: boolean) => v ? <Tag color="default">已读</Tag> : <Tag color="blue">未读</Tag>,
    },
  ]

  const unreadCount = items.filter(n => !n.is_read).length

  // Category stats
  const categoryStats = useMemo(() => {
    const stats: Record<string, { total: number; unread: number }> = {}
    items.forEach((n) => {
      if (!stats[n.type]) stats[n.type] = { total: 0, unread: 0 }
      stats[n.type].total++
      if (!n.is_read) stats[n.type].unread++
    })
    return stats
  }, [items])

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">通知中心</h1>
          <p className="text-sm text-slate-500 mt-1">
            共 {items.length} 条通知，{unreadCount} 条未读
          </p>
        </div>
      </div>

      {/* Category Summary */}
      {unreadCount > 0 && (
        <div className="flex gap-2 flex-wrap mb-4">
          {Object.entries(categoryStats).filter(([, s]) => s.unread > 0).map(([type, s]) => {
            const tl = typeLabels[type] || typeLabels.system
            return (
              <button key={type} onClick={() => { setFilter(type); setUnreadOnly(true) }}
                className="px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:border-primary/30 text-sm font-bold text-slate-600 flex items-center gap-1.5 transition-colors">
                <Tag color={tl.color} className="!m-0 !text-[12px]">{tl.label}</Tag>
                <span className="text-red-500">{s.unread}</span>
              </button>
            )
          })}
        </div>
      )}

      <Tabs defaultActiveKey="list" onChange={(key) => { if (key === 'settings') fetchPrefs() }} items={[
        {
          key: 'list',
          label: '全部通知',
          children: (
            <>
              <div className="flex items-center gap-3 mb-4">
                <Select allowClear placeholder="筛选类型" style={{ width: 140 }} value={filter} onChange={setFilter}
                  options={Object.entries(typeLabels).map(([k, v]) => ({ value: k, label: v.label }))} />
                <Button type={unreadOnly ? 'primary' : 'default'} size="small"
                  onClick={() => setUnreadOnly(!unreadOnly)}>
                  {unreadOnly ? '仅未读' : '全部'}
                </Button>
                <div className="flex-1" />
                <Button icon={<CheckOutlined />} disabled={selectedIds.length === 0} onClick={handleMarkRead}>
                  标记已读 ({selectedIds.length})
                </Button>
                <Button onClick={handleMarkAllRead} disabled={unreadCount === 0}>全部已读</Button>
              </div>
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
                <Table rowKey="id" columns={columns} dataSource={filteredItems} loading={loading}
                  pagination={{ pageSize: 20, showSizeChanger: false }} size="small"
                  rowSelection={{ selectedRowKeys: selectedIds, onChange: (keys) => setSelectedIds(keys as string[]) }}
                  onRow={(record) => ({ onClick: () => handleRowClick(record), style: { cursor: 'pointer' } })} />
              </div>
            </>
          ),
        },
        {
          key: 'settings',
          label: '通知设置',
          children: (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 max-w-lg">
              <h3 className="text-sm font-bold text-slate-900 mb-4">通知订阅设置</h3>
              <p className="text-sm text-slate-500 mb-4">选择您希望接收的通知类型，关闭后将不再推送对应消息。</p>
              <div className="space-y-3">
                {prefTypes.map((t) => (
                  <div key={t.key} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                    <span className="text-sm text-slate-700">{t.label}</span>
                    <Switch checked={prefs[t.key] !== false} onChange={(v) => togglePref(t.key, v)} loading={prefLoading} />
                  </div>
                ))}
              </div>
            </div>
          ),
        },
      ]} />
    </div>
  )
}
