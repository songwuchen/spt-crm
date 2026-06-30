import { useState, useEffect, useRef } from 'react'
import { Table, Button, Tag, Select, Input, Space } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import { changeApi } from '@/api/change'
import type { ChangeRequestItem } from '@/api/types'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'

const changeTypeLabels: Record<string, string> = {
  requirement: '需求变更', quote: '报价变更', contract: '合同变更', delivery: '交付变更', scope: '范围变更',
}
const statusLabels: Record<string, string> = {
  draft: '草稿', reviewing: '评审中', approved: '已批准', rejected: '已驳回', implemented: '已实施',
}
const statusColors: Record<string, string> = {
  draft: 'default', reviewing: 'processing', approved: 'success', rejected: 'error', implemented: 'cyan',
}

export default function ChangeRequestList() {
  usePageTitle('变更管理')
  const navigate = useNavigate()
  const [data, setData] = useState<ChangeRequestItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [filterType, setFilterType] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  const fetchData = async (page = pageNo, kw = keyword, st = filterStatus, tp = filterType) => {
    setLoading(true)
    try {
      const r = await changeApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st, change_type: tp, ...view.buildParams() }) as any
      setData(r.data?.items || [])
      setTotal(r.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取（reload 在 state 更新后再触发，避免读到旧值）
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload])

  const columns: ColumnsType<ChangeRequestItem> = [
    { title: '变更编号', dataIndex: 'change_no', width: 160,
      render: (v: string, r: ChangeRequestItem) => (
        <a className="font-mono font-bold text-primary" onClick={() => navigate(`/opportunities/${r.project_id}`)}>{v}</a>
      ),
    },
    { title: '类型', dataIndex: 'change_type', width: 110,
      render: (v: string) => <Tag>{changeTypeLabels[v] || v}</Tag>,
    },
    { title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={statusColors[v]}>{statusLabels[v] || v}</Tag>,
    },
    { title: '原因', dataIndex: 'reason', ellipsis: true },
    { title: '创建人', dataIndex: 'created_by_name', width: 100 },
    { title: '创建时间', dataIndex: 'created_at', width: 120,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-',
    },
  ]

  const view = useListView<ChangeRequestItem>('change', columns, { pageKey: 'change_requests' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">变更管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看所有商机项目的变更请求</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索变更编号/原因..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus, filterType) }}
            allowClear style={{ width: 220 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v, filterType) }}
            options={Object.entries(statusLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <Select placeholder="变更类型" allowClear style={{ width: 140 }} value={filterType}
            onChange={(v) => { setFilterType(v); setPageNo(1); fetchData(1, keyword, filterStatus, v) }}
            options={Object.entries(changeTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <ListToolbar resource="change" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={data} loading={loading} size="small"
          columns={view.columns}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
        />
      </div>
    </div>
  )
}
