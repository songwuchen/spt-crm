import { useState, useEffect } from 'react'
import { Button, Table, Tag, Modal, Form, Input, Select, DatePicker, Space, Checkbox, message } from 'antd'
import { PlusOutlined, DeleteOutlined, CheckOutlined, UserSwitchOutlined } from '@ant-design/icons'
import { taskApi } from '@/api/task'
import { userApi } from '@/api/user'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
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
  const [filterPriority, setFilterPriority] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [assignModal, setAssignModal] = useState(false)
  const [form] = Form.useForm()
  const [assignForm] = Form.useForm()
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  const fetch = async (p = page) => {
    setLoading(true)
    try {
      const res = await taskApi.list({ pageNo: p, pageSize: 20, status: filterStatus, priority: filterPriority })
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetch(page) }, [page, filterStatus, filterPriority])

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

  const handleBulkComplete = async () => {
    if (selectedIds.length === 0) { message.warning('请先勾选任务'); return }
    Modal.confirm({
      title: `批量完成 ${selectedIds.length} 项任务？`,
      onOk: async () => {
        await taskApi.batchComplete(selectedIds)
        message.success(`已完成 ${selectedIds.length} 项任务`)
        setSelectedIds([])
        fetch()
      },
    })
  }

  const handleBatchAssign = async () => {
    const values = await assignForm.validateFields()
    const name = userSelect.options.find(o => o.value === values.assignee_id)?.label || ''
    try {
      await taskApi.batchAssign(selectedIds, values.assignee_id, name)
      message.success(`已分配 ${selectedIds.length} 项任务`)
      setAssignModal(false)
      assignForm.resetFields()
      setSelectedIds([])
      fetch()
    } catch { message.error('批量分配失败') }
  }

  const todoCount = items.filter(t => !t.is_completed).length
  const overdueCount = items.filter(t => !t.is_completed && t.due_date && dayjs(t.due_date).isBefore(dayjs(), 'day')).length

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">待办任务</h1>
          <p className="text-sm text-slate-500 mt-1">
            {todoCount} 项待办{overdueCount > 0 ? <span className="text-rose-500 font-bold ml-1">{overdueCount} 项已逾期</span> : ''}
          </p>
        </div>
        <Space>
          {selectedIds.length > 0 && (
            <>
              <Button icon={<UserSwitchOutlined />} onClick={() => { assignForm.resetFields(); setAssignModal(true) }}>
                批量分配 ({selectedIds.length})
              </Button>
              <Button icon={<CheckOutlined />} onClick={handleBulkComplete}>
                批量完成 ({selectedIds.length})
              </Button>
            </>
          )}
          <Button type="primary" icon={<PlusOutlined />} onClick={() => { form.resetFields(); setModal(true) }}>新建任务</Button>
        </Space>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <Select placeholder="状态" allowClear style={{ width: 120 }} value={filterStatus} onChange={(v) => { setFilterStatus(v); setPage(1) }}
          options={Object.entries(statusConfig).map(([k, v]) => ({ label: v.label, value: k }))} />
        <Select placeholder="优先级" allowClear style={{ width: 120 }} value={filterPriority} onChange={(v) => { setFilterPriority(v); setPage(1) }}
          options={Object.entries(priorityConfig).map(([k, v]) => ({ label: v.label, value: k }))} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={items} loading={loading} size="small"
          pagination={{ current: page, total, pageSize: 20, onChange: setPage }}
          rowSelection={{
            selectedRowKeys: selectedIds,
            onChange: (keys) => setSelectedIds(keys as string[]),
            getCheckboxProps: (r: TaskItem) => ({ disabled: r.is_completed }),
          }}
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
                const isToday = dayjs(v).isSame(dayjs(), 'day')
                return (
                  <span className={isOverdue ? 'text-rose-500 font-bold' : isToday ? 'text-amber-600 font-medium' : ''}>
                    {v}{isOverdue ? ' (逾期)' : isToday ? ' (今天)' : ''}
                  </span>
                )
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

      <Modal title="批量分配任务" open={assignModal} onOk={handleBatchAssign}
        onCancel={() => setAssignModal(false)} okText="确认分配">
        <Form form={assignForm} layout="vertical" className="py-2">
          <Form.Item label="分配给" name="assignee_id" rules={[{ required: true, message: '请选择负责人' }]}>
            <Select showSearch filterOption={false} placeholder="搜索用户..."
              loading={userSelect.loading} options={userSelect.options}
              onSearch={userSelect.onSearch} onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
          </Form.Item>
        </Form>
        <p className="text-xs text-slate-400">将选中的 {selectedIds.length} 项任务分配给指定负责人</p>
      </Modal>
    </div>
  )
}
