import { useState, useEffect } from 'react'
import { Table, Tag, Select, Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { deliveryApi } from '@/api/delivery'
import type { DeliveryMilestone } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import dayjs from 'dayjs'

const statusLabels: Record<string, string> = {
  not_start: '未开始', doing: '进行中', done: '已完成', delayed: '已延期',
}
const statusColors: Record<string, string> = {
  not_start: 'default', doing: 'processing', done: 'success', delayed: 'error',
}

export default function MilestoneList() {
  usePageTitle('交付里程碑')
  const navigate = useNavigate()
  const [data, setData] = useState<DeliveryMilestone[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()

  const fetchData = async (page = pageNo, kw = keyword, st = filterStatus) => {
    setLoading(true)
    try {
      const r = await deliveryApi.listAllMilestones({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st }) as any
      setData(r.data?.items || [])
      setTotal(r.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  const today = dayjs()

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">交付里程碑</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看所有项目的交付里程碑</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索里程碑名称/编号..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus) }}
            allowClear style={{ width: 220 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v }))} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={data} loading={loading} size="small"
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          columns={[
            { title: '编号', dataIndex: 'milestone_code', width: 120,
              render: (v: string) => <span className="font-mono text-xs font-bold">{v || '-'}</span>,
            },
            { title: '名称', dataIndex: 'name', width: 200,
              render: (v: string, r: DeliveryMilestone) => (
                <a className="font-bold text-primary" onClick={() => navigate(`/opportunities/${r.project_id}`)}>{v}</a>
              ),
            },
            { title: '状态', dataIndex: 'status', width: 100,
              render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v] || v}</Tag>,
            },
            { title: '计划日期', dataIndex: 'plan_date', width: 120,
              render: (v: string | null, r: DeliveryMilestone) => {
                if (!v) return '-'
                const isOverdue = r.status !== 'done' && dayjs(v).isBefore(today, 'day')
                return <span className={isOverdue ? 'text-rose-500 font-bold' : ''}>{v}{isOverdue ? ' (逾期)' : ''}</span>
              },
            },
            { title: '实际日期', dataIndex: 'actual_date', width: 120,
              render: (v: string | null) => v || '-',
            },
            { title: '备注', dataIndex: 'note', ellipsis: true },
            { title: '创建时间', dataIndex: 'created_at', width: 120,
              render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-',
            },
          ]}
        />
      </div>
    </div>
  )
}
