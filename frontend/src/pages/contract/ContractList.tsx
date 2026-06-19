import { useState, useEffect } from 'react'
import { Table, Tag, Select, Input } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { contractApi } from '@/api/contract'
import type { ContractItem } from '@/api/types'
import { contractStatusLabels, contractStatusColors } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'

const fmtMoney = (v?: number | string | null) => {
  if (v == null || v === '***') return v === '***' ? '***' : '-'
  const n = Number(v)
  return Number.isFinite(n) ? `¥${n.toLocaleString()}` : '-'
}

export default function ContractList() {
  usePageTitle('合同管理')
  const navigate = useNavigate()
  const [data, setData] = useState<ContractItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()

  const fetchData = async (page = pageNo, kw = keyword, st = filterStatus) => {
    setLoading(true)
    try {
      const r = await contractApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st }) as any
      setData(r.data?.items || [])
      setTotal(r.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">合同管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看所有商机项目的合同</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索合同编号..."
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus) }}
            allowClear style={{ width: 220 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(contractStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" dataSource={data} loading={loading} size="small"
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          columns={[
            { title: '合同编号', dataIndex: 'contract_no', width: 180,
              render: (v: string, r: ContractItem) => r.project_id ? (
                <a className="font-mono font-bold text-primary" onClick={() => navigate(`/opportunities/${r.project_id}/contracts/${r.id}`)}>{v}</a>
              ) : <span className="font-mono font-bold text-slate-700">{v}</span>,
            },
            { title: '状态', dataIndex: 'status', width: 100,
              render: (v: string) => <Tag color={contractStatusColors[v] || 'default'}>{contractStatusLabels[v] || v}</Tag>,
            },
            { title: '金额', dataIndex: 'amount_total', width: 140, align: 'right',
              render: (v: number | string) => <span className="font-bold">{fmtMoney(v)}</span> },
            { title: '签约日期', dataIndex: 'signed_date', width: 120,
              render: (v: string) => v || '-' },
            { title: '到期日期', dataIndex: 'end_date', width: 120,
              render: (v: string) => v || '-' },
            { title: '负责人', dataIndex: 'assignee_name', width: 100, render: (v: string) => v || '-' },
            { title: '创建时间', dataIndex: 'created_at', width: 120,
              render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
          ]}
        />
      </div>
    </div>
  )
}
