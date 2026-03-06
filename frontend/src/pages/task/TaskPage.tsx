import { useState, useEffect } from 'react'
import { Button, Table, Tag, Modal, Form, Input, Select, DatePicker, Space, Checkbox, message } from 'antd'
import { PlusOutlined, DeleteOutlined, CheckOutlined } from '@ant-design/icons'
import { taskApi } from '@/api/task'
import { usePageTitle } from '@/hooks/usePageTitle'
import dayjs from 'dayjs'

interface TaskItem {
  id: string; title: string; description: string | null
  due_date: string | null; priority: string; status: string
  assignee_name: string | null; created_by_name: string | null
  biz_type: string | null; biz_name: string | null
  is_completed: boolean; created_at: string
}

const priorityConfig: Record<string, { label: string; color: string }> = {
  urgent: { label: '紧急', color: 'red' },
  high: { label: '高', color: 'orange' },
  normal: { label: '中', color: 'blue' },
  low: { label: '低', color: 'default' },
}

const statusConfig: Record<string, { label: string; color: string }> = {
  todo: { label: '待办', color: 'default' },
  in_progress: { label: '进行中', color: 'processing' },
  done: { label: '完成', color: 'success' },
}

export default function TaskPage() {
  usePageTitle('待办任务')
  const [items, setItems] = useState<TaskItem[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [form] = Form.useForm()

  const fetch = async (p = page) => {
    setLoading(true)
    try {
      const res = await taskApi.list({ pageNo: p, pageSize: 20, status: filterStatus })
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetch(page) }, [page, filterStatus])

  const handleCreate = async () => {
    const values = await form.validateFields()
    await taskApi.create({
      ...values,
      due_date: values.due_date ? values.due_date.format('YYYY-MM-DD') : undefined,
    })
    message.success('任务已创建')
    setModal(false)
    form.resetFields()
    fetch()
  }

  const toggleComplete = async (t: TaskItem) => {
    const newCompleted = !t.is_completed
    await taskApi.update(t.id, { is_completed: newCompleted, status: newCompleted ? 'done' : 'todo' })
    message.success(newCompleted ? '已完成' : '已恢复')
    fetch()
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '确认删除', okType: 'danger',
      onOk: async () => { await taskApi.delete(id); message.success('已删除'); fetch() },
    })
  }

  const todoCount = items.filter(t => !t.is_completed).length
  const overdueCount = items.filter(t => !t.is_completed && t.due_date && dayjs(t.due_date).isBefore(dayjs(), 'day')).length

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">待办任务</h1>
          <p className="text-sm text-slate-500 mt-1">
            {todoCount} 项待办{overdueCount > 0 ? `，${overdueCount} 项已逾期` : ''}
          </p>
        </div>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModal(true) }}>新建任务</Button>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <Select placeholder="状态" allowClear style={{ width: 120 }} value={filterStatus} onChange={(v) => { setFilterStatus(v); setPage(1) }}
          options={Object.entries(statusConfig).map(([k, v]) => ({ label: v.label, value: k }))} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={items} loading={loading} size="small"
          pagination={{ current: page, total, pageSize: 20, onChange: setPage }}
          columns={[
            { title: '', key: 'check', width: 40,
              render: (_, r: TaskItem) => (
                <Checkbox checked={r.is_completed} onChange={() => toggleComplete(r)} />
              ),
            },
            { title: '任务', dataIndex: 'title', width: 250,
              render: (v: string, r: TaskItem) => (
                <span className={`font-semibold ${r.is_completed ? 'line-through text-slate-400' : 'text-slate-800'}`}>{v}</span>
              ),
            },
            { title: '优先级', dataIndex: 'priority', width: 80,
              render: (v: string) => { const c = priorityConfig[v] || priorityConfig.normal; return <Tag color={c.color}>{c.label}</Tag> },
            },
            { title: '状态', dataIndex: 'status', width: 80,
              render: (v: string) => { const c = statusConfig[v] || statusConfig.todo; return <Tag color={c.color}>{c.label}</Tag> },
            },
            { title: '截止日期', dataIndex: 'due_date', width: 110,
              render: (v: string | null, r: TaskItem) => {
                if (!v) return '-'
                const isOverdue = !r.is_completed && dayjs(v).isBefore(dayjs(), 'day')
                return <span className={isOverdue ? 'text-rose-500 font-bold' : ''}>{v}</span>
              },
            },
            { title: '关联', dataIndex: 'biz_name', width: 120, ellipsis: true,
              render: (v: string | null, r: TaskItem) => v ? <Tag>{r.biz_type}: {v}</Tag> : '-' },
            { title: '负责人', dataIndex: 'assignee_name', width: 80 },
            { title: '', key: 'actions', width: 60,
              render: (_, r: TaskItem) => (
                <a className="text-rose-500 text-xs" onClick={() => handleDelete(r.id)}><DeleteOutlined /></a>
              ),
            },
          ]}
        />
      </div>

      <Modal title="新建任务" open={modal} onOk={handleCreate} onCancel={() => setModal(false)}>
        <Form form={form} layout="vertical" initialValues={{ priority: 'normal' }}>
          <Form.Item name="title" label="任务标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="请输入任务标题" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="任务描述" />
          </Form.Item>
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="due_date" label="截止日期">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="priority" label="优先级">
              <Select options={Object.entries(priorityConfig).map(([k, v]) => ({ label: v.label, value: k }))} />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  )
}
