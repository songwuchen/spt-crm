import { useState, useEffect } from 'react'
import { Table, Select, Input, Tag, Modal, DatePicker, message } from 'antd'
import { SearchOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { activityApi } from '@/api/activity'
import { useCustomerSelect } from '@/hooks/useSelectOptions'
import type { ActivityItem } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import dayjs from 'dayjs'

const { TextArea } = Input

const activityTypeConfig: Record<string, { label: string; color: string; icon: string }> = {
  call: { label: '电话', color: 'blue', icon: 'call' },
  visit: { label: '拜访', color: 'green', icon: 'directions_walk' },
  meeting: { label: '会议', color: 'purple', icon: 'groups' },
  email: { label: '邮件', color: 'gold', icon: 'mail' },
  note: { label: '备注', color: 'default', icon: 'edit_note' },
  stage_change: { label: '阶段变更', color: 'red', icon: 'swap_horiz' },
  system: { label: '系统', color: 'default', icon: 'settings' },
}

const bizTypeLabels: Record<string, string> = {
  customer: '客户',
  project: '商机',
  lead: '线索',
  service_ticket: '工单',
}

const bizTypeColors: Record<string, string> = {
  customer: 'blue',
  project: 'green',
  lead: 'orange',
  service_ticket: 'red',
}

export default function FollowUpPage() {
  usePageTitle('跟进记录')
  const navigate = useNavigate()
  const [data, setData] = useState<ActivityItem[]>([])
  const [total, setTotal] = useState(0)
  const [pageNo, setPageNo] = useState(1)
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [filterBizType, setFilterBizType] = useState<string | undefined>()
  const [filterActivityType, setFilterActivityType] = useState<string | undefined>()

  // Create modal
  const [createModal, setCreateModal] = useState(false)
  const [form, setForm] = useState<Record<string, any>>({
    biz_type: 'customer',
    activity_type: 'call',
  })

  const customerSelect = useCustomerSelect()

  const fetchData = async (page = pageNo, bt = filterBizType, at = filterActivityType, kw = keyword) => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {
        pageNo: page, pageSize: 20,
        biz_type: bt, activity_type: at,
        keyword: kw || undefined,
      }
      const res = await activityApi.listAll(params) as any
      setData(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const doSearch = () => { setPageNo(1); fetchData(1) }

  const handleCreate = async () => {
    if (!form.biz_id) { message.warning('请选择关联对象'); return }
    if (!form.subject?.trim()) { message.warning('请填写主题'); return }
    try {
      const data: Record<string, unknown> = { ...form }
      if (data.next_follow_date && dayjs.isDayjs(data.next_follow_date)) {
        data.next_follow_date = (data.next_follow_date as dayjs.Dayjs).format('YYYY-MM-DD')
      }
      // Set biz_name from selected option
      const opt = customerSelect.options.find((o) => o.value === form.biz_id)
      if (opt) data.biz_name = opt.label
      await activityApi.create(data)
      message.success('跟进记录已创建')
      setCreateModal(false)
      setForm({ biz_type: 'customer', activity_type: 'call' })
      fetchData()
    } catch {
      message.error('创建失败')
    }
  }

  const bizTypeUrl = (bizType: string, bizId: string) => {
    const map: Record<string, string> = {
      customer: `/customers/${bizId}`,
      project: `/opportunities/${bizId}`,
      lead: `/leads/${bizId}`,
      service_ticket: `/service-tickets/${bizId}`,
    }
    return map[bizType] || '#'
  }

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">跟进记录</h1>
          <p className="text-sm text-slate-500 mt-1">管理所有客户跟进、拜访、电话及会议记录</p>
        </div>
        <button onClick={() => setCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold shadow-lg shadow-primary/20 hover:bg-primary/90 transition-colors border-0 cursor-pointer">
          <PlusOutlined />
          新建跟进
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined />} placeholder="搜索主题/联系人..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch} allowClear style={{ width: 200 }} />
          <Select placeholder="业务类型" allowClear style={{ width: 120 }}
            value={filterBizType}
            onChange={(v) => { setFilterBizType(v); setPageNo(1); fetchData(1, v, filterActivityType, keyword) }}
            options={Object.entries(bizTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <Select placeholder="活动类型" allowClear style={{ width: 120 }}
            value={filterActivityType}
            onChange={(v) => { setFilterActivityType(v); setPageNo(1); fetchData(1, filterBizType, v, keyword) }}
            options={Object.entries(activityTypeConfig).filter(([k]) => !['stage_change', 'system'].includes(k)).map(([k, v]) => ({ value: k, label: v.label }))} />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={data} loading={loading} size="small" scroll={{ x: 900 }}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          expandable={{
            expandedRowRender: (record: ActivityItem) => record.content ? (
              <div className="text-sm text-slate-600 whitespace-pre-wrap">{record.content}</div>
            ) : <span className="text-slate-400 text-xs">无详细内容</span>,
            rowExpandable: () => true,
          }}
          columns={[
            { title: '时间', dataIndex: 'created_at', width: 150,
              render: (v: string) => <span className="text-xs text-slate-500 tabular-nums">{v ? new Date(v).toLocaleString('zh-CN') : '-'}</span>,
            },
            { title: '类型', dataIndex: 'activity_type', width: 80,
              render: (v: string) => {
                const cfg = activityTypeConfig[v]
                return cfg ? (
                  <Tag color={cfg.color}>
                    <span className="material-symbols-outlined text-xs mr-0.5" style={{ verticalAlign: 'text-bottom' }}>{cfg.icon}</span>
                    {cfg.label}
                  </Tag>
                ) : v
              },
            },
            { title: '主题', dataIndex: 'subject',
              render: (v: string) => <span className="text-sm font-medium text-slate-800">{v || '-'}</span>,
            },
            { title: '关联对象', key: 'biz', width: 160,
              render: (_: unknown, r: ActivityItem) => (
                <div>
                  <Tag color={bizTypeColors[r.biz_type]}>{bizTypeLabels[r.biz_type] || r.biz_type}</Tag>
                  {r.biz_name ? (
                    <a className="text-xs text-primary cursor-pointer ml-1" onClick={() => navigate(bizTypeUrl(r.biz_type, r.biz_id))}>{r.biz_name}</a>
                  ) : (
                    <a className="text-xs text-primary cursor-pointer ml-1" onClick={() => navigate(bizTypeUrl(r.biz_type, r.biz_id))}>查看</a>
                  )}
                </div>
              ),
            },
            { title: '联系人', dataIndex: 'contact_name', width: 100,
              render: (v: string) => v || <span className="text-slate-300">-</span>,
            },
            { title: '下次跟进', dataIndex: 'next_follow_date', width: 110, responsive: ['lg'] as any,
              render: (v: string | null) => {
                if (!v) return <span className="text-slate-300">-</span>
                const isOverdue = new Date(v) < new Date(new Date().toDateString())
                return <span className={`text-xs font-bold ${isOverdue ? 'text-red-500' : 'text-slate-600'}`}>{v}</span>
              },
            },
            { title: '记录人', dataIndex: 'created_by_name', width: 90, responsive: ['lg'] as any,
              render: (v: string) => <span className="text-xs text-slate-500">{v || '-'}</span>,
            },
          ]}
        />
      </div>

      {/* Create Modal */}
      <Modal title="新建跟进记录" open={createModal} onOk={handleCreate} onCancel={() => setCreateModal(false)} width={520}>
        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">业务类型</label>
              <Select className="w-full" value={form.biz_type}
                onChange={(v) => setForm({ ...form, biz_type: v, biz_id: undefined })}
                options={Object.entries(bizTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">活动类型</label>
              <Select className="w-full" value={form.activity_type}
                onChange={(v) => setForm({ ...form, activity_type: v })}
                options={Object.entries(activityTypeConfig).filter(([k]) => !['stage_change', 'system'].includes(k)).map(([k, v]) => ({ value: k, label: v.label }))} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">关联对象 <span className="text-red-500">*</span></label>
            <Select className="w-full" showSearch filterOption={false} placeholder="搜索并选择..."
              value={form.biz_id} onChange={(v) => setForm({ ...form, biz_id: v })}
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">主题 <span className="text-red-500">*</span></label>
            <Input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="跟进主题" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">联系人</label>
              <Input value={form.contact_name} onChange={(e) => setForm({ ...form, contact_name: e.target.value })} placeholder="联系人姓名" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">下次跟进日期</label>
              <DatePicker className="w-full" value={form.next_follow_date ? dayjs(form.next_follow_date) : null}
                onChange={(v) => setForm({ ...form, next_follow_date: v })} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">详细内容</label>
            <TextArea rows={3} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })} placeholder="跟进详情..." />
          </div>
        </div>
      </Modal>
    </div>
  )
}
