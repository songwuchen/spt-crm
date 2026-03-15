import { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, InputNumber, Select, Progress, DatePicker, message, Tag } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import dayjs from 'dayjs'

interface Achievement {
  user_id: string; user_name: string
  target_amount: number; target_count: number
  actual_amount: number; actual_count: number
  achievement_rate: number
}

interface TargetRow {
  id: string; user_id: string; user_name: string
  year: number; month: number
  target_amount: number; target_count: number | null
}

export default function SalesTargetPage() {
  usePageTitle('销售目标')
  const now = dayjs()
  const [year, setYear] = useState(now.year())
  const [month, setMonth] = useState<number | undefined>(now.month() + 1)
  const [achievements, setAchievements] = useState<Achievement[]>([])
  const [targets, setTargets] = useState<TargetRow[]>([])
  const [loading, setLoading] = useState(false)
  const [modal, setModal] = useState(false)
  const [form] = Form.useForm()

  const userSelect = useUserSelect()

  const fetch = async () => {
    setLoading(true)
    try {
      const [achRes, tgtRes] = await Promise.all([
        dashboardApi.targetAchievement({ year, month }),
        dashboardApi.listTargets({ year, month }),
      ])
      setAchievements(achRes.data || [])
      setTargets(tgtRes.data || [])
    } finally { setLoading(false) }
  }

  useEffect(() => { fetch() }, [year, month])

  const handleSubmit = async () => {
    const values = await form.validateFields()
    const userName = userSelect.options.find(o => o.value === values.user_id)?.label || ''
    await dashboardApi.upsertTarget({
      user_id: values.user_id,
      user_name: userName,
      year: values.period.year(),
      month: values.period.month() + 1,
      target_amount: values.target_amount,
      target_count: values.target_count,
    })
    message.success('目标已保存')
    setModal(false)
    form.resetFields()
    fetch()
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '确认删除', content: '删除该销售目标？', okType: 'danger',
      onOk: async () => { await dashboardApi.deleteTarget(id); message.success('已删除'); fetch() },
    })
  }

  // Summary totals
  const totalTarget = achievements.reduce((s, a) => s + a.target_amount, 0)
  const totalActual = achievements.reduce((s, a) => s + a.actual_amount, 0)
  const overallRate = totalTarget > 0 ? Math.round(totalActual / totalTarget * 100) : 0

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-slate-900">销售目标与达成</h1>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => {
          form.resetFields(); form.setFieldsValue({ period: dayjs() }); setModal(true)
        }}>设定目标</Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4">
        <Select value={year} onChange={setYear} style={{ width: 100 }}
          options={[now.year() - 1, now.year(), now.year() + 1].map(y => ({ label: `${y}年`, value: y }))} />
        <Select value={month} onChange={setMonth} allowClear placeholder="全年" style={{ width: 100 }}
          options={Array.from({ length: 12 }, (_, i) => ({ label: `${i + 1}月`, value: i + 1 }))} />
      </div>

      {/* Overall Summary */}
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">团队目标</div>
          <div className="text-xl font-black text-slate-900">¥{totalTarget.toLocaleString()}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">已达成</div>
          <div className="text-xl font-black text-emerald-600">¥{totalActual.toLocaleString()}</div>
        </div>
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
          <div className="text-[10px] text-slate-400 uppercase font-bold mb-1">达成率</div>
          <Progress percent={overallRate} size="small" status={overallRate >= 100 ? 'success' : overallRate >= 80 ? 'active' : 'exception'} />
        </div>
      </div>

      {/* Achievement Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden mb-4">
        <div className="p-4 border-b border-slate-100">
          <h3 className="text-sm font-bold text-slate-900">个人达成情况</h3>
        </div>
        <Table rowKey="user_id" dataSource={achievements} loading={loading} size="small" pagination={false}
          columns={[
            { title: '销售人员', dataIndex: 'user_name', width: 120,
              render: (v: string) => <span className="font-semibold text-slate-800">{v || '未知'}</span> },
            { title: '目标金额', dataIndex: 'target_amount', width: 130, align: 'right' as const,
              render: (v: number) => v > 0 ? `¥${v.toLocaleString()}` : <span className="text-slate-300">未设定</span> },
            { title: '实际赢单', dataIndex: 'actual_amount', width: 130, align: 'right' as const,
              render: (v: number) => <span className="font-bold text-emerald-600">¥{v.toLocaleString()}</span> },
            { title: '赢单数', dataIndex: 'actual_count', width: 80, align: 'right' as const },
            { title: '达成率', dataIndex: 'achievement_rate', width: 180,
              render: (v: number) => (
                <div className="flex items-center gap-2">
                  <Progress percent={Math.min(v, 100)} size="small" style={{ width: 100 }}
                    status={v >= 100 ? 'success' : v >= 80 ? 'active' : 'exception'} showInfo={false} />
                  <Tag color={v >= 100 ? 'success' : v >= 80 ? 'processing' : v >= 50 ? 'warning' : 'error'}>
                    {v}%
                  </Tag>
                </div>
              ),
            },
            { title: '差距', key: 'gap', width: 120, align: 'right' as const,
              render: (_: unknown, r: Achievement) => {
                const gap = r.target_amount - r.actual_amount
                return gap > 0
                  ? <span className="text-rose-500 text-xs font-bold">差 ¥{gap.toLocaleString()}</span>
                  : <span className="text-emerald-500 text-xs font-bold">超额 ¥{Math.abs(gap).toLocaleString()}</span>
              },
            },
          ]}
        />
      </div>

      {/* Target Settings Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-slate-100">
          <h3 className="text-sm font-bold text-slate-900">目标设定明细</h3>
        </div>
        <Table rowKey="id" dataSource={targets} loading={loading} size="small" pagination={false}
          columns={[
            { title: '销售人员', dataIndex: 'user_name', width: 120 },
            { title: '年', dataIndex: 'year', width: 70 },
            { title: '月', dataIndex: 'month', width: 50 },
            { title: '目标金额', dataIndex: 'target_amount', width: 130, align: 'right' as const,
              render: (v: number) => `¥${v.toLocaleString()}` },
            { title: '目标单数', dataIndex: 'target_count', width: 80, align: 'right' as const,
              render: (v: number | null) => v ?? '-' },
            { title: '', key: 'actions', width: 60,
              render: (_: unknown, r: TargetRow) => (
                <a className="text-rose-500 text-xs" onClick={() => handleDelete(r.id)}><DeleteOutlined /></a>
              ),
            },
          ]}
        />
      </div>

      {/* Add Target Modal */}
      <Modal title="设定销售目标" open={modal} onOk={handleSubmit} onCancel={() => setModal(false)}>
        <Form form={form} layout="vertical">
          <Form.Item name="user_id" label="销售人员" rules={[{ required: true, message: '请选择' }]}>
            <Select showSearch filterOption={false} placeholder="搜索用户"
              loading={userSelect.loading} options={userSelect.options}
              onSearch={userSelect.onSearch} onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
          </Form.Item>
          <Form.Item name="period" label="目标月份" rules={[{ required: true, message: '请选择' }]}>
            <DatePicker picker="month" className="w-full" />
          </Form.Item>
          <Form.Item name="target_amount" label="目标金额" rules={[{ required: true, message: '请输入' }]}>
            <InputNumber className="w-full" min={0} precision={0} placeholder="目标金额" addonBefore="¥" />
          </Form.Item>
          <Form.Item name="target_count" label="目标单数">
            <InputNumber className="w-full" min={0} placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
