import { useState, useEffect, useMemo } from 'react'
import { Table, Select, DatePicker, Input, Button, message, Segmented, Tabs, Spin, Alert } from 'antd'
import { SearchOutlined, DownloadOutlined, UnorderedListOutlined, FieldTimeOutlined, ReloadOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import client from '@/api/client'
import type { AuditLog, PageData, ApiResponse } from '@/api/types'
import type { Dayjs } from 'dayjs'
import { usePageTitle } from '@/hooks/usePageTitle'
import DataView from '@/components/DataView'

const { RangePicker } = DatePicker

const actionConfig: Record<string, { label: string; bg: string; text: string; border: string; icon: string }> = {
  create: { label: '创建', bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-100', icon: 'add_circle' },
  update: { label: '更新', bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100', icon: 'edit' },
  delete: { label: '删除', bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-100', icon: 'delete' },
  qualify: { label: '转化', bg: 'bg-purple-50', text: 'text-purple-600', border: 'border-purple-100', icon: 'swap_horiz' },
  discard: { label: '废弃', bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', icon: 'block' },
  advance: { label: '推进', bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-100', icon: 'arrow_forward' },
  advance_stage: { label: '推进阶段', bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-100', icon: 'arrow_forward' },
  rollback: { label: '回退', bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-100', icon: 'arrow_back' },
  rollback_stage: { label: '回退阶段', bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-100', icon: 'arrow_back' },
  approve: { label: '审批', bg: 'bg-green-50', text: 'text-green-600', border: 'border-green-100', icon: 'check_circle' },
  reject: { label: '驳回', bg: 'bg-orange-50', text: 'text-orange-600', border: 'border-orange-100', icon: 'cancel' },
  sign: { label: '签署', bg: 'bg-cyan-50', text: 'text-cyan-600', border: 'border-cyan-100', icon: 'draw' },
  login: { label: '登录', bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100', icon: 'login' },
  login_failed: { label: '登录失败', bg: 'bg-red-50', text: 'text-red-600', border: 'border-red-100', icon: 'error' },
  merge: { label: '合并', bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-100', icon: 'merge' },
  new_version: { label: '新建版本', bg: 'bg-blue-50', text: 'text-blue-600', border: 'border-blue-100', icon: 'difference' },
  send_quote: { label: '发送报价', bg: 'bg-cyan-50', text: 'text-cyan-600', border: 'border-cyan-100', icon: 'send' },
  batch_message: { label: '群发消息', bg: 'bg-cyan-50', text: 'text-cyan-600', border: 'border-cyan-100', icon: 'campaign' },
  submit_approval: { label: '提交审批', bg: 'bg-indigo-50', text: 'text-indigo-600', border: 'border-indigo-100', icon: 'approval' },
  withdraw_approval: { label: '撤回审批', bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-100', icon: 'undo' },
  delegate_approval: { label: '转交审批', bg: 'bg-purple-50', text: 'text-purple-600', border: 'border-purple-100', icon: 'forward' },
  claim_from_pool: { label: '从公海领取', bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-100', icon: 'pan_tool' },
  release_to_pool: { label: '释放到公海', bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', icon: 'waves' },
  purge_scheduled: { label: '计划清理', bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', icon: 'event' },
  purge_completed: { label: '清理完成', bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', icon: 'task_alt' },
  purge_cancelled: { label: '取消清理', bg: 'bg-slate-50', text: 'text-slate-500', border: 'border-slate-200', icon: 'block' },
}

const resourceLabels: Record<string, string> = {
  customer: '客户',
  customer_relation: '客户关系',
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
  renewal_opportunity: '续约商机',
  approval: '审批',
  attachment: '附件',
  share: '共享',
  auth: '认证',
  activity: '活动',
  ai_prompt_template: 'AI提示词',
  ai_task: 'AI任务',
  change_request: '变更申请',
  delivery_milestone: '交付里程碑',
  erp_order_link: 'ERP订单',
  invoice: '发票',
  payment_plan: '收款计划',
  payment_record: '收款记录',
}

interface AuditStats {
  total: number
  days: number
  by_action: Array<{ action: string; count: number }>
  by_resource: Array<{ resource_type: string; count: number }>
  daily: Array<{ date: string; count: number }>
  top_operators: Array<{ user_id: string; user_name: string; count: number }>
  hourly?: Array<{ hour: number; count: number }>
  resource_action_matrix?: Array<{ resource_type: string; action: string; count: number }>
}

function DiffView({ detail }: { detail: Record<string, unknown> }) {
  const changes = detail.changes as Array<{ field: string; old: unknown; new: unknown }> | undefined
  if (changes && Array.isArray(changes)) {
    return (
      <div className="space-y-1.5">
        {changes.map((c, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            <span className="font-bold text-slate-600 min-w-[80px]">{c.field}</span>
            <span className="text-red-500 line-through">{String(c.old ?? '-')}</span>
            <span className="material-symbols-outlined text-sm text-slate-400">arrow_forward</span>
            <span className="text-emerald-600 font-medium">{String(c.new ?? '-')}</span>
          </div>
        ))}
      </div>
    )
  }
  return <DataView value={detail} />
}

const weekDayLabels = ['日', '一', '二', '三', '四', '五', '六']

function ActivityHeatmap({ daily }: { daily: Array<{ date: string; count: number }> }) {
  const { grid, maxCount, weeks } = useMemo(() => {
    const map = new Map(daily.map((d) => [d.date, d.count]))
    const max = Math.max(...daily.map((d) => d.count), 1)
    // Build 12-week grid ending today
    const today = new Date()
    const totalWeeks = 12
    const cells: Array<{ date: string; count: number; dow: number; week: number }> = []
    for (let i = totalWeeks * 7 - 1; i >= 0; i--) {
      const d = new Date(today)
      d.setDate(d.getDate() - i)
      const ds = d.toISOString().slice(0, 10)
      const dow = d.getDay()
      const week = Math.floor((totalWeeks * 7 - 1 - i) / 7)
      cells.push({ date: ds, count: map.get(ds) || 0, dow, week })
    }
    return { grid: cells, maxCount: max, weeks: totalWeeks }
  }, [daily])

  const getColor = (count: number) => {
    if (count === 0) return 'bg-slate-100'
    const ratio = count / maxCount
    if (ratio <= 0.25) return 'bg-emerald-200'
    if (ratio <= 0.5) return 'bg-emerald-400'
    if (ratio <= 0.75) return 'bg-emerald-500'
    return 'bg-emerald-700'
  }

  return (
    <div>
      <div className="flex gap-1">
        <div className="flex flex-col gap-1 mr-1 mt-5">
          {weekDayLabels.filter((_, i) => i % 2 === 1).map((l) => (
            <div key={l} className="text-[9px] text-slate-400 h-3 leading-3">{l}</div>
          ))}
        </div>
        <div className="flex gap-1">
          {Array.from({ length: weeks }, (_, w) => (
            <div key={w} className="flex flex-col gap-1">
              {Array.from({ length: 7 }, (_, dow) => {
                const cell = grid.find((c) => c.week === w && c.dow === dow)
                return (
                  <div key={dow} className={`w-3 h-3 rounded-sm ${cell ? getColor(cell.count) : 'bg-slate-50'} group relative`}>
                    {cell && cell.count > 0 && (
                      <div className="hidden group-hover:block absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-slate-800 text-white text-[12px] rounded whitespace-nowrap z-10">
                        {cell.date.slice(5)}: {cell.count} 次操作
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-1 mt-2 justify-end">
        <span className="text-[9px] text-slate-400">少</span>
        {['bg-slate-100', 'bg-emerald-200', 'bg-emerald-400', 'bg-emerald-500', 'bg-emerald-700'].map((c) => (
          <div key={c} className={`w-3 h-3 rounded-sm ${c}`} />
        ))}
        <span className="text-[9px] text-slate-400">多</span>
      </div>
    </div>
  )
}

function DailyTrendChart({ daily }: { daily: Array<{ date: string; count: number }> }) {
  const { points, areaPath, maxCount, width, height, labels } = useMemo(() => {
    if (daily.length < 2) return { points: '', areaPath: '', maxCount: 1, width: 0, height: 0, labels: [] as string[] }
    const w = 500, h = 120, pad = 30
    const max = Math.max(...daily.map((d) => d.count), 1)
    const pts = daily.map((d, i) => ({
      x: pad + (i / (daily.length - 1)) * (w - pad * 2),
      y: pad + (1 - d.count / max) * (h - pad * 2),
    }))
    const line = pts.map((p) => `${p.x},${p.y}`).join(' ')
    const area = `M ${pts[0].x},${h - pad} L ${line} L ${pts[pts.length - 1].x},${h - pad} Z`
    const lbls = daily.length > 5
      ? [daily[0].date.slice(5), daily[Math.floor(daily.length / 2)].date.slice(5), daily[daily.length - 1].date.slice(5)]
      : daily.map((d) => d.date.slice(5))
    return { points: line, areaPath: area, maxCount: max, width: w, height: h, labels: lbls }
  }, [daily])

  if (daily.length < 2) return <div className="text-center text-slate-400 text-sm py-8">数据不足</div>

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
      <defs>
        <linearGradient id="areafill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill="url(#areafill)" />
      <polyline points={points} fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {labels.map((l, i) => (
        <text key={i} x={30 + (i / (labels.length - 1)) * (width - 60)} y={height - 5}
          textAnchor="middle" fontSize="9" fill="#94a3b8">{l}</text>
      ))}
      <text x={5} y={35} fontSize="9" fill="#94a3b8">{maxCount}</text>
      <text x={5} y={height - 30} fontSize="9" fill="#94a3b8">0</text>
    </svg>
  )
}

function HourlyChart({ hourly }: { hourly: Array<{ hour: number; count: number }> }) {
  const fullHours = useMemo(() => {
    const map = new Map(hourly.map((h) => [h.hour, h.count]))
    return Array.from({ length: 24 }, (_, i) => ({ hour: i, count: map.get(i) || 0 }))
  }, [hourly])

  const max = Math.max(...fullHours.map((h) => h.count), 1)

  return (
    <div className="flex items-end gap-[3px] h-20">
      {fullHours.map((h) => {
        const pct = (h.count / max) * 100
        const intensity = h.count === 0 ? 'bg-slate-100' :
          pct <= 25 ? 'bg-blue-200' : pct <= 50 ? 'bg-blue-400' : pct <= 75 ? 'bg-blue-500' : 'bg-blue-700'
        return (
          <div key={h.hour} className="flex-1 flex flex-col items-center gap-0.5 group relative">
            <div className={`w-full rounded-sm ${intensity} transition-all`}
              style={{ height: `${Math.max(pct, 4)}%` }} />
            {h.hour % 4 === 0 && <span className="text-[8px] text-slate-400">{h.hour}</span>}
            <div className="hidden group-hover:block absolute bottom-full mb-1 px-2 py-1 bg-slate-800 text-white text-[12px] rounded whitespace-nowrap z-10">
              {h.hour}:00 — {h.count} 次
            </div>
          </div>
        )
      })}
    </div>
  )
}

function ResourceActionMatrix({ matrix, actionCfg }: {
  matrix: Array<{ resource_type: string; action: string; count: number }>
  actionCfg: typeof actionConfig
}) {
  const { resources, actions, grid, maxVal } = useMemo(() => {
    const resSet = new Set<string>()
    const actSet = new Set<string>()
    const map = new Map<string, number>()
    matrix.forEach((m) => {
      resSet.add(m.resource_type)
      actSet.add(m.action)
      map.set(`${m.resource_type}|${m.action}`, m.count)
    })
    const res = Array.from(resSet).slice(0, 8)
    const acts = Array.from(actSet).slice(0, 6)
    const mx = Math.max(...matrix.map((m) => m.count), 1)
    return { resources: res, actions: acts, grid: map, maxVal: mx }
  }, [matrix])

  if (resources.length === 0) return <div className="text-center text-slate-400 text-sm py-4">暂无数据</div>

  const getColor = (count: number) => {
    if (count === 0) return 'bg-slate-50'
    const ratio = count / maxVal
    if (ratio <= 0.2) return 'bg-blue-100'
    if (ratio <= 0.4) return 'bg-blue-200'
    if (ratio <= 0.6) return 'bg-blue-400'
    if (ratio <= 0.8) return 'bg-blue-500'
    return 'bg-blue-700'
  }

  return (
    <div className="overflow-x-auto">
      <table className="text-[12px]">
        <thead>
          <tr>
            <th className="p-1" />
            {actions.map((a) => (
              <th key={a} className={`p-1 font-bold ${actionCfg[a]?.text || 'text-slate-500'}`}>
                {actionCfg[a]?.label || a}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {resources.map((r) => (
            <tr key={r}>
              <td className="p-1 font-bold text-slate-600 whitespace-nowrap">
                {resourceLabels[r] || r}
              </td>
              {actions.map((a) => {
                const count = grid.get(`${r}|${a}`) || 0
                return (
                  <td key={a} className="p-0.5">
                    <div className={`w-8 h-6 rounded ${getColor(count)} flex items-center justify-center group relative`}>
                      {count > 0 && <span className="text-[9px] font-bold text-white mix-blend-difference">{count}</span>}
                      <div className="hidden group-hover:block absolute bottom-full mb-1 px-2 py-1 bg-slate-800 text-white text-[12px] rounded whitespace-nowrap z-10">
                        {resourceLabels[r] || r} · {actionCfg[a]?.label || a}: {count}
                      </div>
                    </div>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function TimelineView({ data, actionCfg }: { data: AuditLog[]; actionCfg: typeof actionConfig }) {
  return (
    <div className="space-y-1 py-2">
      {data.map((log) => {
        const cfg = actionCfg[log.action]
        return (
          <div key={log.id} className="flex items-start gap-3 py-2 px-3 hover:bg-slate-50 rounded-lg transition-colors">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${cfg?.bg || 'bg-slate-100'} ${cfg?.text || 'text-slate-500'}`}>
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{cfg?.icon || 'info'}</span>
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-bold text-slate-800">{log.user_name}</span>
                <span className={`text-[12px] font-bold px-1.5 py-0.5 rounded ${cfg?.bg || 'bg-slate-100'} ${cfg?.text || 'text-slate-500'}`}>
                  {cfg?.label || log.action}
                </span>
                <span className="text-sm text-slate-500">{resourceLabels[log.resource_type] || log.resource_type}</span>
              </div>
              <div className="text-sm text-slate-600 mt-0.5">{log.summary}</div>
              <div className="text-[13px] text-slate-400 mt-0.5">
                {log.created_at ? new Date(log.created_at).toLocaleString('zh-CN') : '-'}
                {log.ip && <span className="ml-2 font-mono">{log.ip}</span>}
              </div>
            </div>
          </div>
        )
      })}
      {data.length === 0 && <div className="text-center text-slate-400 py-8">暂无数据</div>}
    </div>
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
  const [statsLoading, setStatsLoading] = useState(false)
  const [statsError, setStatsError] = useState<string | null>(null)
  const [statsDays, setStatsDays] = useState(30)
  const [tab, setTab] = useState<'list' | 'stats'>('list')
  const [viewMode, setViewMode] = useState<'table' | 'timeline'>('table')

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

  const fetchStats = async (days = statsDays) => {
    setStatsLoading(true)
    setStatsError(null)
    try {
      const res = await client.get<unknown, ApiResponse<AuditStats>>('/api/v1/audit_logs/statistics', { params: { days } })
      setStats(res.data)
    } catch (e: any) {
      // 不能静默吞掉：否则接口 500/403 会被渲染成「暂无统计数据」，看起来像真的没日志
      setStatsError(e?.response?.data?.message || '统计数据加载失败')
    } finally {
      setStatsLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  // 统计接口只在首次切到「统计分析」时才拉，避免打开页面就多发一次重查询
  const onTabChange = (key: string) => {
    setTab(key as 'list' | 'stats')
    if (key === 'stats' && !stats && !statsLoading) fetchStats()
  }

  const doSearch = () => { setPageNo(1); fetchData(1) }

  const buildExportQs = () => {
    const params: string[] = []
    if (dateRange?.[0]) params.push(`start_date=${dateRange[0].format('YYYY-MM-DD')}`)
    if (dateRange?.[1]) params.push(`end_date=${dateRange[1].format('YYYY-MM-DD')}`)
    if (resourceType) params.push(`resource_type=${resourceType}`)
    if (action) params.push(`action=${action}`)
    if (keyword) params.push(`keyword=${encodeURIComponent(keyword)}`)
    return params.length > 0 ? `?${params.join('&')}` : ''
  }

  const handleExport = () => {
    const qs = buildExportQs()
    downloadFile(`/api/v1/audit_logs/export${qs}`, `操作日志_${new Date().toISOString().slice(0, 10)}.xlsx`)
    message.success('正在导出...')
  }

  const handleExportCsv = () => {
    const qs = buildExportQs()
    const fmt = qs ? `${qs}&format=csv` : '?format=csv'
    downloadFile(`/api/v1/audit_logs/export${fmt}`, `操作日志_${new Date().toISOString().slice(0, 10)}.csv`)
    message.success('正在导出CSV...')
  }

  const dailyMax = stats ? Math.max(...stats.daily.map((d) => d.count), 1) : 1
  const actionMax = stats ? Math.max(...stats.by_action.map((a) => a.count), 1) : 1
  const resourceMax = stats ? Math.max(...stats.by_resource.map((r) => r.count), 1) : 1

  const columns = [
    { title: '时间', dataIndex: 'created_at', width: 170,
      render: (v: string) => v ? (
        <span className="text-sm text-slate-500 tabular-nums">{new Date(v).toLocaleString('zh-CN')}</span>
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
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[12px] font-bold uppercase border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
            <span className="material-symbols-outlined text-sm">{cfg.icon}</span>
            {cfg.label}
          </span>
        ) : v
      },
    },
    { title: '资源类型', dataIndex: 'resource_type', width: 90, responsive: ['lg'] as any,
      render: (v: string) => (
        <span className="text-sm text-slate-600">{resourceLabels[v] || v}</span>
      ),
    },
    { title: '摘要', dataIndex: 'summary',
      render: (v: string) => (
        <span className="text-sm text-slate-600">{v}</span>
      ),
    },
    { title: 'IP', dataIndex: 'ip', width: 120, responsive: ['xl'] as any,
      render: (v: string) => v ? (
        <span className="text-sm font-mono text-slate-400">{v}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '资源ID', dataIndex: 'resource_id', width: 100, responsive: ['xl'] as any,
      render: (v: string) => v ? (
        <span className="text-[13px] font-mono text-slate-400">{v.slice(0, 8)}...</span>
      ) : '-',
    },
  ]

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">操作日志</h1>
          <p className="text-sm text-slate-500 mt-0.5">查看系统操作记录和变更历史</p>
        </div>
        <div className="flex gap-2">
          <Button icon={<ReloadOutlined />} onClick={() => (tab === 'stats' ? fetchStats() : fetchData(pageNo))}>
            刷新
          </Button>
        </div>
      </div>

      {/* Tabs: 列表 / 分析 */}
      <Tabs
        activeKey={tab}
        onChange={onTabChange}
        items={[
          { key: 'list', label: '日志列表' },
          { key: 'stats', label: '统计分析' },
        ]}
      />

      {/* ---------- 统计分析 ---------- */}
      {tab === 'stats' && (statsLoading && !stats ? (
        <div className="flex justify-center py-24"><Spin /></div>
      ) : statsError ? (
        <Alert
          type="error"
          showIcon
          className="my-6"
          message="统计数据加载失败"
          description={statsError}
          action={<Button size="small" onClick={() => fetchStats()}>重试</Button>}
        />
      ) : !stats ? (
        <div className="text-center text-slate-400 text-sm py-24">暂无统计数据</div>
      ) : (
        <div className="mb-6 space-y-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold text-slate-400 uppercase tracking-wider">统计区间</span>
            <Segmented
              size="small"
              value={statsDays}
              onChange={(v) => { setStatsDays(v as number); fetchStats(v as number) }}
              options={[
                { value: 7, label: '近 7 天' },
                { value: 30, label: '近 30 天' },
                { value: 90, label: '近 90 天' },
              ]}
            />
            {statsLoading && <Spin size="small" />}
          </div>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">总操作数</div>
              <div className="text-2xl font-black text-slate-900 mt-1">{stats.total.toLocaleString()}</div>
              <div className="text-[12px] text-slate-400 mt-0.5">近 {stats.days} 天</div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">日均操作</div>
              <div className="text-2xl font-black text-primary mt-1">
                {stats.daily.length > 0 ? Math.round(stats.total / stats.daily.length) : 0}
              </div>
              <div className="text-[12px] text-slate-400 mt-0.5">活跃 {stats.daily.length} 天</div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">操作类型</div>
              <div className="text-2xl font-black text-slate-900 mt-1">{stats.by_action.length}</div>
              <div className="text-[12px] text-slate-400 mt-0.5">种操作</div>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <div className="text-sm font-bold text-slate-400 uppercase tracking-wider">活跃用户</div>
              <div className="text-2xl font-black text-slate-900 mt-1">{stats.top_operators.length}</div>
              <div className="text-[12px] text-slate-400 mt-0.5">位操作员</div>
            </div>
          </div>

          {/* Charts Row */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* Activity Heatmap */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">活动热力图</h4>
              {stats.daily.length > 0 ? (
                <ActivityHeatmap daily={stats.daily} />
              ) : (
                <div className="text-center text-slate-400 text-sm py-8">暂无数据</div>
              )}
            </div>

            {/* Action Distribution */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">操作类型分布</h4>
              <div className="space-y-2">
                {stats.by_action.slice(0, 6).map((a) => {
                  const cfg = actionConfig[a.action]
                  const pct = (a.count / actionMax) * 100
                  return (
                    <div key={a.action} className="flex items-center gap-2">
                      <span className={`text-[12px] font-bold w-10 ${cfg?.text || 'text-slate-500'}`}>
                        {cfg?.label || a.action}
                      </span>
                      <div className="flex-1 h-4 bg-slate-100 rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${cfg?.bg || 'bg-slate-200'}`}
                          style={{ width: `${Math.max(pct, 4)}%` }} />
                      </div>
                      <span className="text-[12px] font-bold text-slate-500 w-8 text-right">{a.count}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Top Operators */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">活跃用户</h4>
              <div className="space-y-2">
                {stats.top_operators.slice(0, 5).map((op, i) => (
                  <div key={op.user_id} className="flex items-center gap-2">
                    <span className={`w-5 h-5 flex items-center justify-center rounded-full text-[12px] font-black ${
                      i === 0 ? 'bg-amber-400 text-white' : i === 1 ? 'bg-slate-300 text-white' : i === 2 ? 'bg-amber-600 text-white' : 'bg-slate-100 text-slate-500'
                    }`}>{i + 1}</span>
                    <span className="text-sm font-medium text-slate-700 flex-1 truncate">{op.user_name}</span>
                    <span className="text-sm font-bold text-slate-500">{op.count} 次</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Daily Trend + Hourly + Resource-Action Matrix */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">每日操作趋势</h4>
              {stats.daily.length >= 2 ? (
                <DailyTrendChart daily={stats.daily} />
              ) : (
                <div className="text-center text-slate-400 text-sm py-8">数据不足</div>
              )}
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">小时分布</h4>
              {stats.hourly && stats.hourly.length > 0 ? (
                <HourlyChart hourly={stats.hourly} />
              ) : (
                <div className="text-center text-slate-400 text-sm py-8">暂无数据</div>
              )}
            </div>
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">资源-操作矩阵</h4>
              {stats.resource_action_matrix && stats.resource_action_matrix.length > 0 ? (
                <ResourceActionMatrix matrix={stats.resource_action_matrix} actionCfg={actionConfig} />
              ) : (
                <div className="text-center text-slate-400 text-sm py-8">暂无数据</div>
              )}
            </div>
          </div>

          {/* Resource Type Distribution */}
          {stats.by_resource.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
              <h4 className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">资源类型分布</h4>
              <div className="flex flex-wrap gap-2">
                {stats.by_resource.map((r) => {
                  const pct = Math.round((r.count / stats.total) * 100)
                  return (
                    <div key={r.resource_type}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-50 border border-slate-100">
                      <span className="text-sm font-bold text-slate-700">{resourceLabels[r.resource_type] || r.resource_type}</span>
                      <span className="text-[12px] font-bold text-primary">{r.count}</span>
                      <span className="text-[12px] text-slate-400">({pct}%)</span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      ))}

      {/* ---------- 日志列表 ---------- */}
      {tab === 'list' && (<>
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
          <Button icon={<DownloadOutlined />} onClick={handleExport}>导出Excel</Button>
          <Button icon={<DownloadOutlined />} onClick={handleExportCsv}>导出CSV</Button>
          <Segmented size="small" value={viewMode} onChange={(v) => setViewMode(v as any)}
            options={[
              { value: 'table', icon: <UnorderedListOutlined />, label: '表格' },
              { value: 'timeline', icon: <FieldTimeOutlined />, label: '时间线' },
            ]} />
        </div>
      </div>

      {/* Table / Timeline */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {viewMode === 'table' ? (
          <Table
            rowKey="id"
            columns={columns}
            dataSource={data}
            loading={loading}
            scroll={{ x: 900 }}
            expandable={{
              expandedRowRender: (record: AuditLog) => record.detail ? (
                <DiffView detail={record.detail} />
              ) : <span className="text-slate-400 text-sm">无详细信息</span>,
              rowExpandable: () => true,
            }}
            pagination={{
              current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
              onChange: (p) => { setPageNo(p); fetchData(p) },
            }}
            size="small"
            className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors"
          />
        ) : (
          <div>
            <TimelineView data={data} actionCfg={actionConfig} />
            <div className="px-4 pb-3 flex justify-end">
              <Button size="small" disabled={pageNo <= 1} onClick={() => { setPageNo(pageNo - 1); fetchData(pageNo - 1) }}>上一页</Button>
              <span className="text-sm text-slate-500 mx-3 self-center">{pageNo} / {Math.ceil(total / 20) || 1}</span>
              <Button size="small" disabled={pageNo * 20 >= total} onClick={() => { setPageNo(pageNo + 1); fetchData(pageNo + 1) }}>下一页</Button>
            </div>
          </div>
        )}
      </div>
      </>)}
    </div>
  )
}
