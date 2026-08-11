import { useState, useEffect, useRef, useMemo, type ReactNode } from 'react'
import { Button, Input, Space, Select, Tag, Modal, message } from 'antd'
import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import { useNavigate } from 'react-router-dom'
import FillHeightTable from '@/components/list/FillHeightTable'
import ListToolbar from '@/components/list/ListToolbar'
import { useListView } from '@/hooks/useListView'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'
import {
  CONTRACT_REVIEW_STATUS,
  CONTRACT_REVIEW_LIST_COLUMNS,
  type ReviewListColumnDef,
} from '@/constants/contractReview'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  CONTRACT_REVIEW_STATUS.map((s) => [s.value, s.label]),
)
const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  submitted: 'processing',
  approved: 'success',
  rejected: 'error',
}

const TAG_PALETTE = ['blue', 'cyan', 'geekblue', 'purple', 'magenta', 'volcano', 'orange', 'gold', 'lime', 'green'] as const

function optionTagColor(label: string): string {
  if (/^(否|无|不是|未)/.test(label)) return 'gold'
  if (/^(是|有|需要)/.test(label)) return 'green'
  if (/高/.test(label)) return 'red'
  if (/中/.test(label)) return 'orange'
  if (/低/.test(label)) return 'green'
  if (/合同评审/.test(label)) return 'blue'
  if (/项目评审/.test(label)) return 'purple'
  if (/核价/.test(label)) return 'cyan'
  if (/安装/.test(label)) return 'geekblue'
  let h = 0
  for (let i = 0; i < label.length; i++) h = (h + label.charCodeAt(i)) % TAG_PALETTE.length
  return TAG_PALETTE[h]
}

function money(v?: number | null) {
  if (v == null) return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return `¥${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

function dash(v: unknown): string {
  if (v == null || v === '') return '—'
  return String(v)
}

function fmtDate(v?: string | null) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleDateString('zh-CN')
}

function linkText(text: string): ReactNode {
  if (!text || text === '—') return '—'
  return <span className="text-primary cursor-default">{text}</span>
}

function readColValue(row: ContractReview, col: ReviewListColumnDef): unknown {
  if (col.source === 'reg') {
    const rj = (row.review_json || {}) as Record<string, unknown>
    return rj[col.key]
  }
  if (col.kind === 'person' || col.kind === 'dept') {
    const nameKey = col.nameKey
    if (nameKey) return (row as unknown as Record<string, unknown>)[nameKey]
  }
  return (row as unknown as Record<string, unknown>)[col.key]
}

function renderCell(col: ReviewListColumnDef, row: ContractReview, navigate: (p: string) => void): ReactNode {
  const raw = readColValue(row, col)
  const kind = col.kind || 'text'

  if (col.key === 'review_code') {
    return (
      <a className="text-primary font-bold font-mono" onClick={() => navigate(`/contract-reviews/${row.id}`)}>
        {dash(raw)}
      </a>
    )
  }

  if (kind === 'status') {
    const v = String(raw || '')
    return <Tag color={STATUS_COLOR[v] || 'default'}>{STATUS_LABEL[v] || v || '—'}</Tag>
  }
  if (kind === 'tag') {
    if (raw == null || raw === '') return '—'
    const lab = String(raw)
    return <Tag color={optionTagColor(lab)} style={{ marginInlineEnd: 0 }}>{lab}</Tag>
  }
  if (kind === 'money') return <span className="font-medium">{money(raw as number | null)}</span>
  if (kind === 'date') return fmtDate(raw as string | null)
  if (kind === 'number') {
    if (raw == null || raw === '') return '—'
    return String(raw)
  }
  if (kind === 'person' || kind === 'dept') return linkText(dash(raw))
  const s = dash(raw)
  if (s === '—') return s
  return <span className="truncate inline-block max-w-full align-bottom" title={s}>{s}</span>
}

export default function ContractReviewList() {
  usePageTitle('合同评审')
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const canCreate = hasPermission('contract_review:create')
  const canDelete = hasPermission('contract_review:delete')

  const [data, setData] = useState<ContractReview[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [reviewType, setReviewType] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const kwRef = useRef(keyword)
  kwRef.current = keyword

  const baseColumns: ColumnsType<ContractReview> = useMemo(() => {
    const cols: ColumnsType<ContractReview> = CONTRACT_REVIEW_LIST_COLUMNS.map((col) => ({
      key: col.key,
      dataIndex: col.key,
      title: col.title,
      width: col.width,
      ellipsis: true,
      fixed: col.fixed,
      // 供 useListView：长文/次要列默认隐藏，可在列配置调出
      ...({ __optIn: !!col.defaultHidden } as object),
      render: (_: unknown, row: ContractReview) => renderCell(col, row, navigate),
    }))
    cols.push({
      title: '操作',
      key: 'actions',
      width: 120,
      fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          <a className="text-primary text-sm px-2" onClick={() => navigate(`/contract-reviews/${r.id}`)}>详情</a>
          {canDelete && (
            <a
              className="text-rose-500 text-sm px-2"
              onClick={() => {
                Modal.confirm({
                  title: '确认删除',
                  content: `确定删除合同评审「${r.review_code}」？`,
                  okType: 'danger',
                  onOk: async () => {
                    await contractReviewApi.delete(r.id)
                    message.success('已删除')
                    setReload((n) => n + 1)
                  },
                })
              }}
            >
              删除
            </a>
          )}
        </Space>
      ),
    })
    return cols
  }, [navigate, canDelete])

  // pageKey v2：列定义对齐简道云后重置本地列配置缓存
  const view = useListView<ContractReview>('contract_review', baseColumns, {
    pageKey: 'contract_reviews_jdy_v2',
    entityType: 'contract_review',
  })

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await contractReviewApi.list({
        pageNo: p,
        pageSize,
        keyword: kwRef.current || undefined,
        status,
        review_type: reviewType,
        ...view.buildParams(),
      })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(1)
    setPage(1)
  }, [status, reviewType, reload]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-xl font-semibold m-0">合同评审</h2>
          <p className="text-sm text-slate-500 mt-0.5 m-0">列表列对齐简道云「合同评审」数据管理；可横向滚动，列配置可调出更多字段</p>
        </div>
        {canCreate && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/contract-reviews/new')}>
            新建评审
          </Button>
        )}
      </div>
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <Input
          allowClear
          placeholder="编号/公司/项目/业务员"
          prefix={<SearchOutlined />}
          className="w-64"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={() => { setPage(1); fetchData(1) }}
        />
        <Select
          allowClear
          placeholder="流程状态"
          className="w-32"
          options={[...CONTRACT_REVIEW_STATUS]}
          value={status}
          onChange={setStatus}
        />
        <Select
          allowClear
          placeholder="合同评审/项目评审"
          className="w-40"
          options={[
            { value: '合同评审', label: '合同评审' },
            { value: '项目评审', label: '项目评审' },
          ]}
          value={reviewType}
          onChange={setReviewType}
        />
        <Button onClick={() => { setPage(1); fetchData(1) }}>查询</Button>
        <ListToolbar resource="contract_review" view={view} onChange={() => setReload((r) => r + 1)} />
      </div>
      <FillHeightTable
        rowKey="id"
        loading={loading}
        size="small"
        columns={view.columns}
        dataSource={data}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize,
          total,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => { setPage(p); fetchData(p) },
        }}
      />
    </div>
  )
}
