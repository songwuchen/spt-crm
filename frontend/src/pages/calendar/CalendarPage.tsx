import { useState, useEffect } from 'react'
import { Calendar, Badge, Select, Drawer, Tag, Button, Modal, Form, Input, DatePicker, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import { dashboardApi } from '@/api/dashboard'
import { taskApi } from '@/api/task'
import { usePageTitle } from '@/hooks/usePageTitle'

interface CalendarEvent {
  id: string
  date: string
  type: string
  title: string
  color: string
}

const typeLabels: Record<string, { label: string; icon: string; color: string }> = {
  follow_up: { label: '跟进计划', icon: 'event', color: '#3b82f6' },
  payment_due: { label: '回款到期', icon: 'payments', color: '#f59e0b' },
  contract_expiry: { label: '合同到期', icon: 'description', color: '#ef4444' },
  milestone: { label: '里程碑', icon: 'flag', color: '#8b5cf6' },
}

const typeFilters = [
  { value: '', label: '全部类型' },
  { value: 'follow_up', label: '跟进计划' },
  { value: 'payment_due', label: '回款到期' },
  { value: 'contract_expiry', label: '合同到期' },
  { value: 'milestone', label: '里程碑' },
]

const priorityOptions = [
  { value: 'low', label: '低' },
  { value: 'normal', label: '中' },
  { value: 'high', label: '高' },
  { value: 'urgent', label: '紧急' },
]

function getEventLink(e: CalendarEvent): string | null {
  switch (e.type) {
    case 'follow_up': return '/follow-ups'
    case 'payment_due': return '/payments'
    case 'contract_expiry': return '/renewals'
    case 'milestone': return '/opportunities'
    default: return null
  }
}

export default function CalendarPage() {
  usePageTitle('日程日历')
  const navigate = useNavigate()
  const [events, setEvents] = useState<CalendarEvent[]>([])
  const [currentDate, setCurrentDate] = useState(dayjs())
  const [typeFilter, setTypeFilter] = useState('')
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createLoading, setCreateLoading] = useState(false)
  const [form] = Form.useForm()

  const fetchEvents = (d: Dayjs) => {
    dashboardApi.calendarEvents({ year: d.year(), month: d.month() + 1 })
      .then((r: any) => setEvents(r.data || []))
      .catch(() => {})
  }

  useEffect(() => { fetchEvents(currentDate) }, [currentDate.year(), currentDate.month()])

  const filteredEvents = typeFilter ? events.filter((e) => e.type === typeFilter) : events

  const eventsByDate: Record<string, CalendarEvent[]> = {}
  filteredEvents.forEach((e) => {
    if (!eventsByDate[e.date]) eventsByDate[e.date] = []
    eventsByDate[e.date].push(e)
  })

  const handleDateSelect = (value: Dayjs) => {
    const dateStr = value.format('YYYY-MM-DD')
    const dayEvents = eventsByDate[dateStr]
    if (dayEvents && dayEvents.length > 0) {
      setSelectedDate(dateStr)
      setDrawerOpen(true)
    } else {
      // No events — open create modal with this date pre-filled
      form.setFieldsValue({ due_date: value, title: '', priority: 'normal', description: '' })
      setCreateOpen(true)
    }
  }

  const handleCreateEvent = () => {
    form.setFieldsValue({ due_date: dayjs(), title: '', priority: 'normal', description: '' })
    setCreateOpen(true)
  }

  const handleCreateSubmit = async () => {
    const values = await form.validateFields()
    setCreateLoading(true)
    try {
      await taskApi.create({
        title: values.title,
        description: values.description || null,
        due_date: values.due_date.format('YYYY-MM-DD'),
        priority: values.priority || 'normal',
        biz_type: 'follow_up',
      })
      message.success('日程创建成功')
      setCreateOpen(false)
      form.resetFields()
      fetchEvents(currentDate)
    } catch {
      message.error('创建失败')
    } finally {
      setCreateLoading(false)
    }
  }

  const dateCellRender = (value: Dayjs) => {
    const dateStr = value.format('YYYY-MM-DD')
    const dayEvents = eventsByDate[dateStr]
    if (!dayEvents || dayEvents.length === 0) return null
    return (
      <ul className="list-none p-0 m-0">
        {dayEvents.slice(0, 3).map((e) => (
          <li key={e.id} className="mb-0.5">
            <Badge color={e.color} text={
              <span className="text-[10px] text-slate-600 truncate block max-w-full">{e.title}</span>
            } />
          </li>
        ))}
        {dayEvents.length > 3 && (
          <li className="text-[10px] text-slate-400">+{dayEvents.length - 3} 更多</li>
        )}
      </ul>
    )
  }

  const selectedEvents = selectedDate ? (eventsByDate[selectedDate] || []) : []

  // Summary stats
  const totalByType: Record<string, number> = {}
  events.forEach((e) => {
    totalByType[e.type] = (totalByType[e.type] || 0) + 1
  })

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">日程日历</h1>
          <p className="text-sm text-slate-500 mt-0.5">跟进计划、回款到期、合同到期、交付里程碑</p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={typeFilter} onChange={setTypeFilter} options={typeFilters} style={{ width: 140 }} />
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreateEvent}>新建日程</Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="flex gap-3 flex-wrap mb-4">
        {Object.entries(totalByType).map(([type, count]) => {
          const tl = typeLabels[type]
          return tl ? (
            <div key={type} className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg border border-slate-200 shadow-sm cursor-pointer hover:border-primary/40 transition-colors"
              onClick={() => setTypeFilter(typeFilter === type ? '' : type)}>
              <span className="material-symbols-outlined text-base text-slate-400">{tl.icon}</span>
              <span className="text-xs font-bold text-slate-700">{tl.label}</span>
              <span className="text-xs font-black text-primary">{count}</span>
            </div>
          ) : null
        })}
        {Object.keys(totalByType).length === 0 && (
          <span className="text-sm text-slate-400">本月暂无日程</span>
        )}
      </div>

      {/* Calendar */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
        <Calendar
          value={currentDate}
          onPanelChange={(d) => setCurrentDate(d)}
          onSelect={handleDateSelect}
          cellRender={(current, info) => {
            if (info.type === 'date') return dateCellRender(current)
            return null
          }}
        />
      </div>

      {/* Legend */}
      <div className="flex gap-4 mt-4 flex-wrap">
        <div className="flex items-center gap-1.5"><Badge color="#3b82f6" /><span className="text-xs text-slate-500">跟进计划</span></div>
        <div className="flex items-center gap-1.5"><Badge color="#f59e0b" /><span className="text-xs text-slate-500">回款到期</span></div>
        <div className="flex items-center gap-1.5"><Badge color="#ef4444" /><span className="text-xs text-slate-500">合同到期</span></div>
        <div className="flex items-center gap-1.5"><Badge color="#8b5cf6" /><span className="text-xs text-slate-500">里程碑</span></div>
      </div>

      {/* Event Detail Drawer */}
      <Drawer
        title={selectedDate ? `${selectedDate} 日程 (${selectedEvents.length})` : '日程详情'}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        width={380}
      >
        {selectedEvents.length === 0 ? (
          <div className="text-center py-8 text-slate-400 text-sm">该日无日程</div>
        ) : (
          <div className="space-y-3">
            {selectedEvents.map((e) => {
              const tl = typeLabels[e.type]
              const link = getEventLink(e)
              return (
                <div key={e.id}
                  className={`p-3 rounded-lg border border-slate-200 hover:border-primary/40 transition-colors ${link ? 'cursor-pointer' : ''}`}
                  onClick={() => link && navigate(link)}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: e.color }} />
                    {tl && <Tag color={tl.color} className="text-[10px] leading-tight">{tl.label}</Tag>}
                  </div>
                  <div className="text-sm font-semibold text-slate-800 mt-1">{e.title}</div>
                  {link && (
                    <div className="text-[11px] text-primary mt-1 flex items-center gap-0.5">
                      <span className="material-symbols-outlined" style={{ fontSize: 12 }}>open_in_new</span>
                      查看详情
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </Drawer>

      {/* Create Event Modal */}
      <Modal
        title="新建日程"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={handleCreateSubmit}
        confirmLoading={createLoading}
        okText="创建"
        destroyOnClose
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="日程标题" maxLength={200} />
          </Form.Item>
          <Form.Item name="due_date" label="日期" rules={[{ required: true, message: '请选择日期' }]}>
            <DatePicker className="w-full" />
          </Form.Item>
          <Form.Item name="priority" label="优先级" initialValue="normal">
            <Select options={priorityOptions} />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="日程描述（可选）" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
