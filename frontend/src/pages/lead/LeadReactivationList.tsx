import { useCallback, useEffect, useState } from 'react'
import { Button, Drawer, Input, Select, Space, message } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import FillHeightTable from '@/components/list/FillHeightTable'
import LeadReactivationDetailPanel from '@/components/lead/LeadReactivationDetailPanel'
import { leadReactivationApi, type LeadReactivationStats } from '@/api/lead'
import type { LeadReactivationDetail, LeadReactivationRecord } from '@/api/types'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail } from '@/types/lowcode'
import { leadReactivationFilterOptions, leadReactivationFlowLabel } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePageSize } from '@/hooks/usePageSize'
import { useWfProcessDrawer } from '@/components/lowcode/WfProcessDrawer'

function JdyTag({ text, tone }: { text: string; tone: string }) {
  const tones: Record<string, string> = {
    red: 'bg-red-500 text-white',
    amber: 'bg-amber-500 text-white',
    orange: 'bg-orange-500 text-white',
    green: 'bg-emerald-500 text-white',
    teal: 'bg-teal-500 text-white',
    blue: 'bg-blue-500 text-white',
    cyan: 'bg-cyan-500 text-white',
    slate: 'bg-slate-400 text-white',
  }
  return (
    <span className={`inline-flex max-w-full truncate px-2 py-0.5 rounded text-[12px] font-medium ${tones[tone] || tones.slate}`}>
      {text}
    </span>
  )
}

function StatChip({
  label, value, active, onClick,
}: { label: string; value: number; active?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-3 py-2 text-left transition ${
        active
          ? 'border-teal-500 bg-teal-50 shadow-sm'
          : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      <div className="text-[11px] font-bold uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-xl font-extrabold text-slate-900">{value}</div>
    </button>
  )
}

export default function LeadReactivationList() {
  usePageTitle('180天项目激活')
  const navigate = useNavigate()
  const [pageSize, setPageSize] = usePageSize('lead_reactivations')
  const [pageNo, setPageNo] = useState(1)
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [items, setItems] = useState<LeadReactivationRecord[]>([])
  const [keyword, setKeyword] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('__all__')
  const [stats, setStats] = useState<LeadReactivationStats | null>(null)

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [detailRow, setDetailRow] = useState<LeadReactivationDetail | null>(null)
  const [detailWf, setDetailWf] = useState<WfInstanceDetail | null>(null)
  const [pendingTaskId, setPendingTaskId] = useState<string | undefined>()

  const buildListParams = useCallback(() => {
    const params: Record<string, unknown> = { pageNo, pageSize, keyword: keyword || undefined }
    if (statusFilter === '__active__') {
      params.flow_status = 'active'
    } else if (statusFilter === '__completed__') {
      params.flow_status = 'completed'
    } else if (statusFilter === '__closed__') {
      params.flow_status = 'closed'
    } else if (statusFilter && !statusFilter.startsWith('__')) {
      params.flow_status = 'active'
      params.reactivation_status = statusFilter
    }
    return params
  }, [pageNo, pageSize, keyword, statusFilter])

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const res = await leadReactivationApi.list(buildListParams())
      setItems(res.data?.items || [])
      setTotal(res.data?.total ?? 0)
    } catch {
      message.error('加载 180 天激活列表失败')
    } finally {
      setLoading(false)
    }
  }, [buildListParams])

  const fetchStats = useCallback(async () => {
    try {
      const res = await leadReactivationApi.stats()
      setStats(res.data || null)
    } catch {
      setStats(null)
    }
  }, [])

  const reloadList = () => { void fetchData(); void fetchStats() }
  const { openWith: openWfDrawer, node: wfDrawerNode } = useWfProcessDrawer(reloadList)

  useEffect(() => { void fetchData() }, [fetchData])
  useEffect(() => { void fetchStats() }, [fetchStats])

  const openDetail = async (recordId: string) => {
    setDrawerOpen(true)
    setDetailLoading(true)
    setDetailRow(null)
    setDetailWf(null)
    setPendingTaskId(undefined)
    try {
      const res = await leadReactivationApi.get(recordId)
      setDetailRow(res.data)
      if (res.data?.lead_id) {
        const [wfRes, todoRes] = await Promise.all([
          workflowApi.byBiz({ biz_type: 'lead_reactivation', biz_id: res.data.lead_id }),
          workflowApi.todo({
            pageNo: 1,
            pageSize: 5,
            biz_type: 'lead_reactivation',
            biz_id: res.data.lead_id,
          }),
        ])
        setDetailWf(wfRes.data || null)
        const pending = (todoRes.data?.items || []).find((t) => t.status === 'pending')
        setPendingTaskId(pending?.task_id)
      }
    } catch {
      message.error('加载详情失败')
      setDrawerOpen(false)
    } finally {
      setDetailLoading(false)
    }
  }

  const handleWfComment = async (content: string) => {
    if (!detailWf?.id || !detailRow) return
    await workflowApi.comment(detailWf.id, content)
    await openDetail(detailRow.id)
  }

  const handleFromList = () => {
    if (!detailRow) return
    if (detailWf?.id && pendingTaskId) {
      setDrawerOpen(false)
      openWfDrawer(detailWf.id, pendingTaskId)
      return
    }
    navigate(`/leads/${detailRow.lead_id}?react=1`)
  }

  const columns: ColumnsType<LeadReactivationRecord> = [
    {
      title: '原项目编号',
      dataIndex: 'original_lead_code',
      width: 140,
      fixed: 'left',
      render: (v: string | null, row) => (
        <a className="text-primary font-medium" onClick={() => void openDetail(row.id)}>
          {v || '-'}
        </a>
      ),
    },
    {
      title: '项目名称',
      dataIndex: 'lead_title',
      width: 220,
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    {
      title: '项目状态',
      dataIndex: 'report_project_status',
      width: 96,
      render: (v: string | null) => v || '-',
    },
    {
      title: '项目近况',
      dataIndex: 'project_recent',
      width: 160,
      ellipsis: true,
      render: (v: string | null) => v || '-',
    },
    {
      title: '申报人',
      dataIndex: 'lead_reporter_name',
      width: 88,
      render: (v: string | null) => v || '-',
    },
    {
      title: '填表人',
      dataIndex: 'lead_filler_name',
      width: 88,
      render: (v: string | null) => v || '-',
    },
    {
      title: '轮次',
      dataIndex: 'round_no',
      width: 72,
      render: (v: number) => (v != null ? `第${v}轮` : '-'),
    },
    {
      title: '流程状态',
      key: 'flow_status',
      width: 108,
      render: (_, row) => {
        const cfg = leadReactivationFlowLabel(row)
        return <JdyTag text={cfg.label} tone={cfg.tone} />
      },
    },
    {
      title: '提交时间',
      dataIndex: 'submitted_at',
      width: 160,
      render: (v: string | null) => (v ? new Date(v).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      width: 160,
      render: (v: string | null) => (v ? new Date(v).toLocaleString('zh-CN') : '-'),
    },
    {
      title: '',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, row) => (
        <Space size={0}>
          <a className="text-primary text-sm font-bold px-2" onClick={() => void openDetail(row.id)}>
            查看
          </a>
          {row.is_current_round && ['awaiting_reporter', 'awaiting_filler', 'pending_review'].includes(row.reactivation_status || '') && (
            <a
              className="text-amber-600 text-sm font-bold px-2"
              onClick={() => navigate(`/leads/${row.lead_id}?react=1`)}
            >
              办理
            </a>
          )}
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">180天项目激活</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          每条记录对应简道云一条「180天项目激活」数据；流程已结束的记录同样保留在此列表
        </p>
      </div>

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
          <StatChip
            label="全部"
            value={stats.total}
            active={statusFilter === '__all__'}
            onClick={() => { setStatusFilter('__all__'); setPageNo(1) }}
          />
          <StatChip
            label="流程进行中"
            value={stats.active}
            active={statusFilter === '__active__'}
            onClick={() => { setStatusFilter('__active__'); setPageNo(1) }}
          />
          <StatChip
            label="流程已结束"
            value={stats.completed}
            active={statusFilter === '__completed__'}
            onClick={() => { setStatusFilter('__completed__'); setPageNo(1) }}
          />
          <StatChip
            label="已关闭"
            value={stats.closed}
            active={statusFilter === '__closed__'}
            onClick={() => { setStatusFilter('__closed__'); setPageNo(1) }}
          />
        </div>
      )}

      <div className="flex flex-wrap gap-3 mb-4">
        <Input
          allowClear
          prefix={<SearchOutlined className="text-slate-400" />}
          placeholder="项目编号 / 名称 / 公司"
          className="w-64"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={() => { setPageNo(1); void fetchData() }}
        />
        <Select
          className="w-52"
          value={statusFilter}
          options={leadReactivationFilterOptions}
          onChange={(v) => { if (v !== '__sep__') { setStatusFilter(v); setPageNo(1) } }}
        />
        <Button type="primary" onClick={() => { setPageNo(1); void fetchData() }}>查询</Button>
      </div>

      <FillHeightTable
        rowKey="id"
        loading={loading}
        columns={columns}
        dataSource={items}
        scroll={{ x: 1400 }}
        pagination={{
          current: pageNo,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPageNo(p); if (ps) setPageSize(ps) },
        }}
      />

      <Drawer
        title={detailRow?.original_lead_code || '180天项目激活详情'}
        width="min(1100px, 96vw)"
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        destroyOnClose
      >
        <LeadReactivationDetailPanel
          row={detailRow}
          wfInstance={detailWf}
          loading={detailLoading}
          onWfComment={handleWfComment}
          onHandle={handleFromList}
          compact
        />
      </Drawer>
      {wfDrawerNode}
    </div>
  )
}
