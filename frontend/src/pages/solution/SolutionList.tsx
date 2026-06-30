import { useState, useEffect, useRef } from 'react'
import { Table, Tag, Select, Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import { solutionApi } from '@/api/solution'
import type { SolutionItem } from '@/api/types'
import { solutionStatusLabels, solutionStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'

export default function SolutionList() {
  usePageTitle('方案管理')
  const navigate = useNavigate()
  const [data, setData] = useState<SolutionItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  const fetchData = async (page = pageNo, kw = keyword, st = filterStatus) => {
    setLoading(true)
    try {
      const r = await solutionApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st, ...view.buildParams() }) as any
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

  const columns: ColumnsType<SolutionItem> = [
    { title: '方案编号', dataIndex: 'solution_no', width: 180,
      render: (v: string, r: SolutionItem) => (
        <a className="font-mono font-bold text-primary" onClick={() => navigate(`/opportunities/${r.project_id}/solutions/${r.id}`)}>{v}</a>
      ),
    },
    { title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={solutionStatusColors[v] || 'default'}>{solutionStatusLabels[v] || v}</Tag>,
    },
    { title: '版本', dataIndex: 'current_version_no', width: 80, render: (v: number) => `V${v ?? 1}` },
    { title: '负责人', dataIndex: 'assignee_name', width: 100, render: (v: string) => v || '-' },
    { title: '创建人', dataIndex: 'created_by_name', width: 100, render: (v: string) => v || '-' },
    { title: '创建时间', dataIndex: 'created_at', width: 120,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
  ]

  const view = useListView<SolutionItem>('solution', columns, { pageKey: 'solutions' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">方案管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看所有商机项目的技术方案</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索方案编号..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus) }}
            allowClear style={{ width: 220 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(solutionStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <ListToolbar resource="solution" view={view} onChange={() => setReload((r) => r + 1)} />
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
