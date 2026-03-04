import { useState, useEffect } from 'react'
import { Table, Select, DatePicker, Input, Button, message } from 'antd'
import { SearchOutlined, DownloadOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import client from '@/api/client'
import type { AuditLog, PageData, ApiResponse } from '@/api/types'
import type { Dayjs } from 'dayjs'
import { usePageTitle } from '@/hooks/usePageTitle'

const { RangePicker } = DatePicker

const actionConfig: Record<string, { label: string; bg: string; text: string; border: string; icon: string }> = {
  create: { label: '创建', bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-100', icon: 'add_circle' },
  update: { label: '更新', bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100', icon: 'edit' },
  delete: { label: '删除', bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-100', icon: 'delete' },
  qualify: { label: '转化', bg: 'bg-purple-50', text: 'text-purple-600', border: 'border-purple-100', icon: 'swap_horiz' },
  discard: { label: '废弃', bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', icon: 'block' },
  advance: { label: '推进', bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-100', icon: 'arrow_forward' },
  rollback: { label: '回退', bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-100', icon: 'arrow_back' },
  approve: { label: '审批', bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-100', icon: 'check_circle' },
  reject: { label: '驳回', bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-100', icon: 'cancel' },
  sign: { label: '签署', bg: 'bg-cyan-50', text: 'text-cyan-600', border: 'border-cyan-100', icon: 'draw' },
}

const resourceLabels: Record<string, string> = {
  customer: '客户',
  contact: '联系人',
  lead: '线索',
  user: '用户',
  project: '商机',
  quote: '报价',
  quote_version: '报价版本',
  contract: '合同',
  contract_version: '合同版本',
  solution: '方案',
  solution_version: '方案版本',
  service_ticket: '工单',
  renewal: '续约',
  approval: '审批',
  attachment: '附件',
  share: '共享',
}

export default function AuditLogPage() {
  usePageTitle('操作日志')
  const [data, setData] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [resourceType, setResourceType] = useState<string | undefined>()
  const [action, setAction] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')
  const [dateRange, setDateRange] = useState<[Dayjs | null, Dayjs | null] | null>(null)

  const fetchData = async (
    page = pageNo, rt = resourceType, act = action,
    kw = keyword, dr = dateRange,
  ) => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = {
        pageNo: page, pageSize: 20,
        resource_type: rt, action: act,
        keyword: kw || undefined,
      }
      if (dr && dr[0]) params.start_date = dr[0].format('YYYY-MM-DD')
      if (dr && dr[1]) params.end_date = dr[1].format('YYYY-MM-DD')

      const res = await client.get<unknown, ApiResponse<PageData<AuditLog>>>('/api/v1/audit_logs', { params })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const doSearch = () => { setPageNo(1); fetchData(1) }

  const handleExport = () => {
    const params: string[] = []
    if (dateRange?.[0]) params.push(`start_date=${dateRange[0].format('YYYY-MM-DD')}`)
    if (dateRange?.[1]) params.push(`end_date=${dateRange[1].format('YYYY-MM-DD')}`)
    if (resourceType) params.push(`resource_type=${resourceType}`)
    if (action) params.push(`action=${action}`)
    const qs = params.length > 0 ? `?${params.join('&')}` : ''
    downloadFile(`/api/v1/audit_logs/export${qs}`, `审计日志_${new Date().toISOString().slice(0, 10)}.xlsx`)
    message.success('正在导出...')
  }

  const columns = [
    { title: '时间', dataIndex: 'created_at', width: 170,
      render: (v: string) => v ? (
        <span className="text-xs text-slate-500 tabular-nums">{new Date(v).toLocaleString('zh-CN')}</span>
      ) : '-',
    },
    { title: '操作人', dataIndex: 'user_name', width: 100,
      render: (v: string) => (
        <span className="text-sm font-semibold text-slate-700">{v}</span>
      ),
    },
    { title: '操作', dataIndex: 'action', width: 90,
      render: (v: string) => {
        const cfg = actionConfig[v]
        return cfg ? (
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
            <span className="material-symbols-outlined text-xs">{cfg.icon}</span>
            {cfg.label}
          </span>
        ) : v
      },
    },
    { title: '资源类型', dataIndex: 'resource_type', width: 90, responsive: ['lg'] as any,
      render: (v: string) => (
        <span className="text-xs text-slate-600">{resourceLabels[v] || v}</span>
      ),
    },
    { title: '摘要', dataIndex: 'summary',
      render: (v: string) => (
        <span className="text-sm text-slate-600">{v}</span>
      ),
    },
    { title: 'IP', dataIndex: 'ip', width: 120, responsive: ['xl'] as any,
      render: (v: string) => v ? (
        <span className="text-xs font-mono text-slate-400">{v}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '资源ID', dataIndex: 'resource_id', width: 100, responsive: ['xl'] as any,
      render: (v: string) => v ? (
        <span className="text-[11px] font-mono text-slate-400">{v.slice(0, 8)}...</span>
      ) : '-',
    },
  ]

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">审计日志</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看系统操作记录和变更历史</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="搜索操作人/摘要..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 200, background: '#f1f5f9', borderColor: 'transparent' }}
            className="rounded-lg"
          />
          <Select
            placeholder="资源类型"
            allowClear
            style={{ width: 120 }}
            value={resourceType}
            onChange={(v) => { setResourceType(v); setPageNo(1); fetchData(1, v, action, keyword, dateRange) }}
            options={Object.entries(resourceLabels).map(([k, v]) => ({ label: v, value: k }))}
          />
          <Select
            placeholder="操作类型"
            allowClear
            style={{ width: 110 }}
            value={action}
            onChange={(v) => { setAction(v); setPageNo(1); fetchData(1, resourceType, v, keyword, dateRange) }}
            options={Object.entries(actionConfig).map(([k, v]) => ({ label: v.label, value: k }))}
          />
          <RangePicker
            onChange={(dates) => {
              setDateRange(dates as [Dayjs | null, Dayjs | null] | null)
              setPageNo(1)
              fetchData(1, resourceType, action, keyword, dates as [Dayjs | null, Dayjs | null] | null)
            }}
          />
          <Button onClick={doSearch}>
            <span className="material-symbols-outlined text-sm mr-1">filter_list</span>
            筛选
          </Button>
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出</Button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 900 }}
          expandable={{
            expandedRowRender: (record: AuditLog) => record.detail ? (
              <pre className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg overflow-auto max-h-40">
                {JSON.stringify(record.detail, null, 2)}
              </pre>
            ) : <span className="text-slate-400 text-xs">无详细信息</span>,
            rowExpandable: () => true,
          }}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          size="small"
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors"
        />
      </div>
    </div>
  )
}
