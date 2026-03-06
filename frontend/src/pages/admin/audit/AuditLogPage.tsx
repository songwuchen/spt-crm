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

interface AuditStats {
  total: number
  days: number
  by_action: Array<{ action: string; count: number }>
  by_resource: Array<{ resource_type: string; count: number }>
  daily: Array<{ date: string; count: number }>
  top_operators: Array<{ user_id: string; user_name: string; count: number }>
}

function DiffView({ detail }: { detail: Record<string, unknown> }) {
  const changes = detail.changes as Array<{ field: string; old: unknown; new: unknown }> | undefined
  if (changes && Array.isArray(changes)) {
    return (
      <div className="space-y-1.5">
        {changes.map((c, i) => (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span className="font-bold text-slate-600 min-w-[80px]">{c.field}</span>
            <span className="text-red-500 line-through">{String(c.old ?? '-')}</span>
            <span className="material-symbols-outlined text-xs text-slate-400">arrow_forward</span>
            <span className="text-emerald-600 font-medium">{String(c.new ?? '-')}</span>
          </div>
        ))}
      </div>
    )
  }
  return (
    <pre className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg overflow-auto max-h-40">
      {JSON.stringify(detail, null, 2)}
    </pre>
  )
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
  const [stats, setStats] = useState<AuditStats | null>(null)
  const [showStats, setShowStats] = useState(true)

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

  const fetchStats = async () => {
    try {
      const res = await client.get<unknown, ApiResponse<AuditStats>>('/api/v1/audit_logs/statistics', { params: { days: 30 } })
      setStats(res.data)
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchData(); fetchStats() }, [])

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

  const dailyMax = stats ? Math.max(...stats.daily.map((d) => d.count), 1) : 1
  const actionMax = stats ? Math.max(...stats.by_action.map((a) => a.count), 1) : 1
  const resourceMax = stats ? Math.max(...stats.by_resource.map((r) => r.count), 1) : 1

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
        <button onClick={() => setShowStats(!showStats)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 text-sm font-bold hover:bg-slate-200 transition-colors border-0 cursor-pointer">
          <span className="material-symbols-outlined text-base">{showStats ? 'visibility_off' : 'bar_chart'}</span>
          {showStats ? '隐藏统计' : '显示统计'}
        </button>
      </div>

      {/* Statistics Panel */}
      {showStats && stats && (
        <div className="mb-6 space-y-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">总操作数</div>
              <div className="text-2xl font-black text-slate-900 mt-1">{stats.total.toLocaleString()}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">近 {stats.days} 天</div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">日均操作</div>
              <div className="text-2xl font-black text-primary mt-1">
                {stats.daily.length > 0 ? Math.round(stats.total / stats.daily.length) : 0}
              </div>
              <div className="text-[10px] text-slate-400 mt-0.5">活跃 {stats.daily.length} 天</div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">操作类型</div>
              <div className="text-2xl font-black text-slate-900 mt-1">{stats.by_action.length}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">种操作</div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-xs font-bold text-slate-400 uppercase tracking-wider">活跃用户</div>
              <div className="text-2xl font-black text-slate-900 mt-1">{stats.top_operators.length}</div>
              <div className="text-[10px] text-slate-400 mt-0.5">位操作员</div>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Daily Activity */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">每日活动</h4>
              {stats.daily.length > 0 ? (
                <div className="flex items-end gap-[2px] h-24">
                  {stats.daily.slice(-30).map((d) => {
                    const h = Math.max((d.count / dailyMax) * 100, 4)
                    return (
                      <div key={d.date} className="flex-1 min-w-0 group relative">
                        <div className="bg-primary/80 hover:bg-primary rounded-t transition-colors"
                          style={{ height: `${h}%` }} />
                        <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-slate-800 text-white text-[10px] rounded whitespace-nowrap z-10">
                          {d.date.slice(5)}: {d.count}
                        </div>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="text-center text-slate-400 text-xs py-8">暂无数据</div>
              )}
            </div>

            {/* Action Distribution */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">操作类型分布</h4>
              <div className="space-y-2">
                {stats.by_action.slice(0, 6).map((a) => {
                  const cfg = actionConfig[a.action]
                  const pct = (a.count / actionMax) * 100
                  return (
                    <div key={a.action} className="flex items-center gap-2">
                      <span className={`text-[10px] font-bold w-10 ${cfg?.text || 'text-slate-500'}`}>
                        {cfg?.label || a.action}
                      </span>
                      <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${cfg?.bg || 'bg-slate-200'}`}
                          style={{ width: `${Math.max(pct, 4)}%` }} />
                      </div>
                      <span className="text-[10px] font-bold text-slate-500 w-8 text-right">{a.count}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Top Operators */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">活跃用户</h4>
              <div className="space-y-2">
                {stats.top_operators.slice(0, 5).map((op, i) => (
                  <div key={op.user_id} className="flex items-center gap-2">
                    <span className={`w-5 h-5 flex items-center justify-center rounded-full text-[10px] font-black ${
                      i === 0 ? 'bg-amber-400 text-white' : i === 1 ? 'bg-slate-300 text-white' : i === 2 ? 'bg-amber-600 text-white' : 'bg-slate-100 text-slate-500'
                    }`}>{i + 1}</span>
                    <span className="text-sm font-medium text-slate-700 flex-1 truncate">{op.user_name}</span>
                    <span className="text-xs font-bold text-slate-500">{op.count} 次</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Resource Type Distribution */}
          {stats.by_resource.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">资源类型分布</h4>
              <div className="flex flex-wrap gap-2">
                {stats.by_resource.map((r) => {
                  const pct = Math.round((r.count / stats.total) * 100)
                  return (
                    <div key={r.resource_type}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-100">
                      <span className="text-xs font-bold text-slate-700">{resourceLabels[r.resource_type] || r.resource_type}</span>
                      <span className="text-[10px] font-bold text-primary">{r.count}</span>
                      <span className="text-[10px] text-slate-400">({pct}%)</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

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
              <DiffView detail={record.detail} />
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
