import { useState, useEffect } from 'react'
import { Tabs, Table, Tag, Button, Modal, Form, Input, Select, Space, Spin, message } from 'antd'
import { PlusOutlined, ReloadOutlined, EyeOutlined } from '@ant-design/icons'
import { aiApi } from '@/api/ai'
import type { AiTaskItem, AiResultItem, AiPromptTemplateItem } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { usePageTitle } from '@/hooks/usePageTitle'

const { TextArea } = Input

const taskTypeLabels: Record<string, string> = {
  meeting_summary: '会议纪要', requirement_extraction: '需求提取',
  quote_risk_analysis: '报价风险分析', contract_risk: '合同风险',
  customer_insight: '客户洞察', next_action: '下一步建议',
}

const statusColors: Record<string, string> = {
  queued: 'default', running: 'processing', done: 'success', failed: 'error', cancelled: 'warning',
}
const statusLabels: Record<string, string> = {
  queued: '排队中', running: '执行中', done: '已完成', failed: '失败', cancelled: '已取消',
}

const bizTypeLabels: Record<string, string> = {
  project: '商机', customer: '客户', lead: '线索', quote: '报价',
  contract: '合同', service_ticket: '工单',
}

export default function AiCenterPage() {
  usePageTitle('AI 中心')
  const [tasks, setTasks] = useState<AiTaskItem[]>([])
  const [templates, setTemplates] = useState<AiPromptTemplateItem[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [bizTypeFilter, setBizTypeFilter] = useState<string | undefined>(undefined)

  // Task detail/result modal
  const [resultModal, setResultModal] = useState(false)
  const [resultLoading, setResultLoading] = useState(false)
  const [selectedTask, setSelectedTask] = useState<AiTaskItem | null>(null)
  const [taskResult, setTaskResult] = useState<AiResultItem | null>(null)

  // Template modal
  const [templateModal, setTemplateModal] = useState(false)
  const [editingTemplate, setEditingTemplate] = useState<AiPromptTemplateItem | null>(null)
  const [templateForm] = Form.useForm()

  const fetchTasks = async () => {
    setLoading(true)
    try {
      const res = await aiApi.listTasks({ status: statusFilter, biz_type: bizTypeFilter })
      setTasks(res.data || [])
    } finally {
      setLoading(false)
    }
  }

  const fetchTemplates = async () => {
    const res = await aiApi.listTemplates()
    setTemplates(res.data || [])
  }

  useEffect(() => { fetchTasks() }, [statusFilter, bizTypeFilter])
  useEffect(() => { fetchTemplates() }, [])

  const viewResult = async (task: AiTaskItem) => {
    setSelectedTask(task)
    setResultModal(true)
    setResultLoading(true)
    try {
      if (task.status === 'done') {
        const res = await aiApi.getResult(task.id)
        setTaskResult(res.data)
      } else {
        setTaskResult(null)
      }
    } finally {
      setResultLoading(false)
    }
  }

  const handleTemplateSave = async () => {
    const values = await templateForm.validateFields()
    if (editingTemplate) {
      await aiApi.updateTemplate(editingTemplate.id, values)
      message.success('模板已更新')
    } else {
      await aiApi.createTemplate(values)
      message.success('模板已创建')
    }
    setTemplateModal(false)
    templateForm.resetFields()
    setEditingTemplate(null)
    fetchTemplates()
  }

  const handleDeleteTemplate = (id: string) => {
    Modal.confirm({
      title: '确认删除', content: '确定要删除此模板？', okType: 'danger',
      onOk: async () => {
        await aiApi.deleteTemplate(id)
        message.success('已删除')
        fetchTemplates()
      },
    })
  }

  const taskColumns: ColumnsType<AiTaskItem> = [
    {
      title: '任务类型', dataIndex: 'task_type', width: 140,
      render: (v: string) => <Tag color="blue">{taskTypeLabels[v] || v}</Tag>,
    },
    {
      title: '关联业务', key: 'biz', width: 120,
      render: (_, r) => r.biz_type ? (
        <span className="text-xs text-slate-500">{bizTypeLabels[r.biz_type] || r.biz_type}</span>
      ) : '-',
    },
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v] || v}</Tag>,
    },
    {
      title: '模型', dataIndex: 'model_name', width: 120,
      render: (v: string) => v || '-',
    },
    {
      title: 'Token', key: 'tokens', width: 120,
      render: (_, r) => (r.token_in || r.token_out) ? (
        <span className="text-xs text-slate-500">{r.token_in || 0} / {r.token_out || 0}</span>
      ) : '-',
    },
    {
      title: '费用', dataIndex: 'cost_est', width: 80,
      render: (v: number | null) => v != null ? `¥${v.toFixed(3)}` : '-',
    },
    {
      title: '创建人', dataIndex: 'created_by_name', width: 100,
    },
    {
      title: '创建时间', dataIndex: 'created_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '', key: 'actions', width: 80,
      render: (_, r) => (
        <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => viewResult(r)}>查看</Button>
      ),
    },
  ]

  const templateColumns: ColumnsType<AiPromptTemplateItem> = [
    { title: '编码', dataIndex: 'code', width: 160, render: (v: string) => <span className="font-mono text-sm">{v}</span> },
    { title: '名称', dataIndex: 'name', width: 200, render: (v: string) => <span className="font-semibold">{v}</span> },
    {
      title: '任务类型', dataIndex: 'task_type', width: 140,
      render: (v: string) => <Tag color="blue">{taskTypeLabels[v] || v}</Tag>,
    },
    {
      title: '状态', dataIndex: 'is_active', width: 80,
      render: (v: boolean) => <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '停用'}</Tag>,
    },
    {
      title: '更新时间', dataIndex: 'updated_at', width: 160,
      render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-',
    },
    {
      title: '', key: 'actions', width: 120,
      render: (_, r) => (
        <Space size={4}>
          <a className="text-primary text-xs font-bold" onClick={() => {
            setEditingTemplate(r)
            templateForm.setFieldsValue(r)
            setTemplateModal(true)
          }}>编辑</a>
          <a className="text-rose-500 text-xs font-bold" onClick={() => handleDeleteTemplate(r.id)}>删除</a>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">AI 任务中心</h1>
        <p className="text-sm text-slate-500 mt-1">管理 AI 分析任务、查看结果、配置 Prompt 模板</p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: '总任务', value: tasks.length, icon: 'smart_toy', color: 'bg-blue-50 text-blue-600' },
          { label: '执行中', value: tasks.filter((t) => t.status === 'running').length, icon: 'sync', color: 'bg-amber-50 text-amber-600' },
          { label: '已完成', value: tasks.filter((t) => t.status === 'done').length, icon: 'check_circle', color: 'bg-emerald-50 text-emerald-600' },
          { label: '失败', value: tasks.filter((t) => t.status === 'failed').length, icon: 'error', color: 'bg-red-50 text-red-600' },
        ].map((card) => (
          <div key={card.label} className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-lg ${card.color} flex items-center justify-center`}>
              <span className="material-symbols-outlined" style={{ fontSize: 20 }}>{card.icon}</span>
            </div>
            <div>
              <div className="text-2xl font-black text-slate-900">{card.value}</div>
              <div className="text-xs text-slate-400 font-bold">{card.label}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
        <Tabs defaultActiveKey="tasks" className="px-4 pt-2"
          items={[
            {
              key: 'tasks',
              label: 'AI 任务',
              children: (
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <Space>
                      <Select allowClear placeholder="状态筛选" value={statusFilter} onChange={setStatusFilter}
                        style={{ width: 140 }}
                        options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v }))} />
                      <Select allowClear placeholder="业务类型" value={bizTypeFilter} onChange={setBizTypeFilter}
                        style={{ width: 140 }}
                        options={Object.entries(bizTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
                    </Space>
                    <Button icon={<ReloadOutlined />} onClick={fetchTasks}>刷新</Button>
                  </div>
                  <Table rowKey="id" columns={taskColumns} dataSource={tasks} loading={loading}
                    pagination={{ pageSize: 15, showSizeChanger: false }} size="small" />
                </div>
              ),
            },
            {
              key: 'templates',
              label: 'Prompt 模板',
              children: (
                <div>
                  <div className="flex justify-end mb-4">
                    <Button type="primary" icon={<PlusOutlined />} onClick={() => {
                      setEditingTemplate(null)
                      templateForm.resetFields()
                      setTemplateModal(true)
                    }}>新建模板</Button>
                  </div>
                  <Table rowKey="id" columns={templateColumns} dataSource={templates}
                    pagination={{ pageSize: 15, showSizeChanger: false }} size="small" />
                </div>
              ),
            },
          ]}
        />
      </div>

      {/* Task Result Modal */}
      <Modal title="任务详情" open={resultModal} onCancel={() => { setResultModal(false); setSelectedTask(null); setTaskResult(null) }}
        footer={null} width={700}>
        {selectedTask && (
          <div>
            <div className="mb-4 p-4 bg-slate-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <Tag color="blue">{taskTypeLabels[selectedTask.task_type] || selectedTask.task_type}</Tag>
                <Tag color={statusColors[selectedTask.status]}>{statusLabels[selectedTask.status] || selectedTask.status}</Tag>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs text-slate-500 mt-2">
                <div>关联: {selectedTask.biz_type ? `${bizTypeLabels[selectedTask.biz_type] || selectedTask.biz_type}` : '无'}</div>
                <div>模型: {selectedTask.model_name || '-'}</div>
                <div>Token: {selectedTask.token_in || 0} in / {selectedTask.token_out || 0} out</div>
                <div>费用: {selectedTask.cost_est != null ? `¥${selectedTask.cost_est.toFixed(3)}` : '-'}</div>
                <div>创建: {selectedTask.created_by_name} · {selectedTask.created_at ? new Date(selectedTask.created_at).toLocaleString('zh-CN') : ''}</div>
                <div>重试: {selectedTask.retry_count} 次</div>
              </div>
              {selectedTask.error_message && (
                <div className="mt-2 p-2 bg-red-50 rounded text-xs text-red-600">{selectedTask.error_message}</div>
              )}
            </div>

            {selectedTask.input_ref_json && (
              <div className="mb-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">输入参考</h4>
                <pre className="bg-slate-50 p-3 rounded-lg text-xs text-slate-700 overflow-auto max-h-40">
                  {JSON.stringify(selectedTask.input_ref_json, null, 2)}
                </pre>
              </div>
            )}

            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">执行结果</h4>
            {resultLoading ? (
              <div className="flex justify-center py-8"><Spin /></div>
            ) : taskResult ? (
              <div>
                {taskResult.risk_level && (
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-bold text-slate-500">风险等级:</span>
                    <Tag color={taskResult.risk_level === 'H' ? 'error' : taskResult.risk_level === 'M' ? 'warning' : 'success'}>
                      {taskResult.risk_level}
                    </Tag>
                    {taskResult.quality_score != null && (
                      <>
                        <span className="text-xs font-bold text-slate-500 ml-2">质量分:</span>
                        <span className="text-sm font-bold">{taskResult.quality_score}</span>
                      </>
                    )}
                  </div>
                )}
                <div className="bg-slate-50 p-3 rounded-lg overflow-auto max-h-60">
                  {taskResult.result_json && typeof taskResult.result_json === 'object' && !Array.isArray(taskResult.result_json) ? (
                    <div className="space-y-2">
                      {Object.entries(taskResult.result_json as Record<string, unknown>).map(([key, val]) => (
                        <div key={key} className="text-xs">
                          <span className="font-bold text-slate-500">{key}:</span>{' '}
                          {typeof val === 'object' && val !== null ? (
                            Array.isArray(val) ? (
                              <ul className="list-disc list-inside mt-1 ml-2 space-y-0.5">
                                {(val as unknown[]).map((item, i) => (
                                  <li key={i} className="text-slate-700">{typeof item === 'object' ? JSON.stringify(item) : String(item)}</li>
                                ))}
                              </ul>
                            ) : (
                              <span className="text-slate-700">{JSON.stringify(val)}</span>
                            )
                          ) : (
                            <span className="text-slate-700">{String(val ?? '-')}</span>
                          )}
                        </div>
                      ))}
                    </div>
                  ) : Array.isArray(taskResult.result_json) ? (
                    <ul className="list-disc list-inside space-y-1 text-xs text-slate-700">
                      {(taskResult.result_json as unknown[]).map((item, i) => (
                        <li key={i}>{typeof item === 'object' ? JSON.stringify(item) : String(item)}</li>
                      ))}
                    </ul>
                  ) : (
                    <div className="text-xs text-slate-700 whitespace-pre-wrap">{JSON.stringify(taskResult.result_json, null, 2)}</div>
                  )}
                </div>
                {taskResult.evidence_json && (
                  <div className="mt-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">证据</h4>
                    <div className="bg-slate-50 p-3 rounded-lg overflow-auto max-h-40">
                      {Array.isArray(taskResult.evidence_json) ? (
                        <ul className="list-decimal list-inside space-y-1 text-xs text-slate-700">
                          {(taskResult.evidence_json as unknown[]).map((item, i) => (
                            <li key={i}>{typeof item === 'object' ? JSON.stringify(item) : String(item)}</li>
                          ))}
                        </ul>
                      ) : typeof taskResult.evidence_json === 'object' ? (
                        <div className="space-y-1">
                          {Object.entries(taskResult.evidence_json as Record<string, unknown>).map(([k, v]) => (
                            <div key={k} className="text-xs"><span className="font-bold text-slate-500">{k}:</span> <span className="text-slate-700">{typeof v === 'object' ? JSON.stringify(v) : String(v ?? '-')}</span></div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-xs text-slate-700 whitespace-pre-wrap">{JSON.stringify(taskResult.evidence_json, null, 2)}</div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-center py-6 text-slate-400 text-sm">
                {selectedTask.status === 'done' ? '结果为空' : '任务尚未完成'}
              </div>
            )}
          </div>
        )}
      </Modal>

      {/* Template Modal */}
      <Modal title={editingTemplate ? '编辑模板' : '新建模板'} open={templateModal}
        onOk={handleTemplateSave} onCancel={() => { setTemplateModal(false); setEditingTemplate(null); templateForm.resetFields() }}
        width={600}>
        <Form form={templateForm} layout="vertical">
          <div className="grid grid-cols-2 gap-4">
            <Form.Item name="code" label="编码" rules={[{ required: true, message: '请输入编码' }]}>
              <Input placeholder="如: meeting_summary_v1" disabled={!!editingTemplate} />
            </Form.Item>
            <Form.Item name="task_type" label="任务类型" rules={[{ required: true, message: '请选择' }]}>
              <Select options={Object.entries(taskTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </Form.Item>
          </div>
          <Form.Item name="name" label="名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="模板名称" />
          </Form.Item>
          <Form.Item name="template_text" label="Prompt 模板">
            <TextArea rows={6} placeholder="输入 Prompt 模板内容，可使用 {{variable}} 占位..." />
          </Form.Item>
          <Form.Item name="is_active" label="状态" initialValue={true}>
            <Select options={[{ value: true, label: '启用' }, { value: false, label: '停用' }]} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
