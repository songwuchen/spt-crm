import { useState, useEffect, useRef } from 'react'
import { Table, Tag, Select, Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { quoteApi } from '@/api/quote'
import type { QuoteItem } from '@/api/types'
import { quoteStatusLabels, quoteStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'
import type { ColumnsType } from 'antd/es/table'

const fmtMoney = (v?: number | null) => {
  if (v == null) return '-'
  const n = Number(v)
  return Number.isFinite(n) ? `¥${n.toLocaleString()}` : '-'
}

export default function QuoteList() {
  usePageTitle('报价管理')
  const navigate = useNavigate()
  const [data, setData] = useState<QuoteItem[]>([])
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
      const r = await quoteApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st, ...view.buildParams() }) as any
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

  const columns: ColumnsType<QuoteItem> = [
    { title: '报价编号', dataIndex: 'quote_no', width: 180,
      render: (v: string, r: QuoteItem) => (
        <a className="font-mono font-bold text-primary" onClick={() => navigate(`/opportunities/${r.project_id}/quotes/${r.id}`)}>{v}</a>
      ),
    },
    { title: '商机名称', dataIndex: 'project_name', width: 200, ellipsis: true, render: (v: string) => v || '-' },
    { title: '客户名称', dataIndex: 'customer_name', width: 180, ellipsis: true, render: (v: string) => v || '-' },
    { title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={quoteStatusColors[v] || 'default'}>{quoteStatusLabels[v] || v}</Tag>,
    },
    { title: '当前版本总价', dataIndex: 'price_total', width: 150, align: 'right',
      render: (v: number | string | null) => <span className="font-bold">{v === '***' ? '***' : fmtMoney(v as number | null)}</span> },
    { title: '毛利率', dataIndex: 'margin_rate', width: 100, align: 'right',
      render: (v: number | string | null) => v === '***' ? '***' : (v != null ? `${(Number(v) * 100).toFixed(1)}%` : '-') },
    { title: '负责人', dataIndex: 'assignee_name', width: 100, render: (v: string) => v || '-' },
    { title: '创建时间', dataIndex: 'created_at', width: 120,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
  ]

  const view = useListView<QuoteItem>('quote', columns, { pageKey: 'quotes' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">报价管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看所有商机项目的报价</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索报价编号..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus) }}
            allowClear style={{ width: 220 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(quoteStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <ListToolbar resource="quote" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={data} loading={loading} size="small"
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          columns={view.columns}
        />
      </div>
    </div>
  )
}
