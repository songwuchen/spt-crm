// 合同选择字段(contract)。值为合同 id；对齐简道云 linkfield：按钮「选择数据」+ 可搜索分页表格。
// 审批人未必有 contract:view：回显走 /lc/pickable-contracts，只读不拉全量列表。
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Button, Input, Modal, Space, Table, Tag, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

interface COpt { label: string; value: string }
type ContractRow = { id: string; contract_no?: string | null; drawing_no?: string | null }
type ColDef = { key: string; title: string }
type PickRow = {
  id: string
  label?: string
  contract_no?: string | null
  drawing_no?: string | null
  cols?: Record<string, string>
}
type PickPage = {
  items?: PickRow[]
  total?: number
  page?: number
  page_size?: number
  columns?: ColDef[]
}

const silent = { headers: { 'X-Silent-Error': '1' } }

/** 关联合同：优先显示图纸编号；无图纸号时显示合同号。 */
function contractLabel(c: ContractRow): string {
  const draw = String(c.drawing_no || '').trim()
  const no = String(c.contract_no || '').trim()
  if (draw && no && draw !== no) return `${draw}（${no}）`
  return draw || no || c.id
}

function toOpts(rows: ContractRow[]): COpt[] {
  return (rows || []).map((c) => ({ label: contractLabel(c), value: c.id }))
}

function highlightText(text: string, kw: string): ReactNode {
  const raw = text || '—'
  const q = kw.trim()
  if (!q) return raw
  const lower = raw.toLowerCase()
  const idx = lower.indexOf(q.toLowerCase())
  if (idx < 0) return raw
  return (
    <>
      {raw.slice(0, idx)}
      <span style={{ color: '#52c41a', fontWeight: 600 }}>{raw.slice(idx, idx + q.length)}</span>
      {raw.slice(idx + q.length)}
    </>
  )
}

async function fetchPage(params: {
  keyword?: string
  departmentId?: string | null
  ids?: string[]
  page?: number
  pageSize?: number
}): Promise<PickPage> {
  const r = await client.get<unknown, ApiResponse<PickPage | ContractRow[]>>('/api/v1/lc/pickable-contracts', {
    params: {
      keyword: params.keyword || undefined,
      department_id: params.departmentId || undefined,
      ids: params.ids?.length ? params.ids.join(',') : undefined,
      page: params.page || 1,
      page_size: params.pageSize || 20,
    },
    ...silent,
  })
  const raw = r.data
  if (Array.isArray(raw)) {
    return {
      items: raw.map((c) => ({
        id: c.id,
        label: contractLabel(c),
        contract_no: c.contract_no,
        drawing_no: c.drawing_no,
        cols: {
          drawing_no: String(c.drawing_no || '').trim(),
        },
      })),
      total: raw.length,
      page: 1,
      page_size: raw.length,
      columns: [{ key: 'drawing_no', title: '图纸编号' }],
    }
  }
  return raw || { items: [], total: 0, page: 1, page_size: 20, columns: [] }
}

async function hydrateMissing(ids: string[], opts: COpt[]): Promise<COpt[]> {
  let next = opts
  const have = new Set(next.map((o) => o.value))
  const missing = ids.filter((id) => id && !have.has(id))
  if (!missing.length) return next
  try {
    const pack = await fetchPage({ ids: missing })
    for (const row of pack.items || []) {
      if (!have.has(row.id)) {
        next = [...next, { label: row.label || row.id, value: row.id }]
        have.add(row.id)
      }
    }
    for (const id of missing) {
      if (!have.has(id)) {
        next = [...next, { label: id, value: id }]
        have.add(id)
      }
    }
  } catch {
    for (const id of missing) {
      if (!have.has(id)) {
        next = [...next, { label: id, value: id }]
        have.add(id)
      }
    }
  }
  return next
}

/** 列表/导出用：合同 id → 图纸编号（优先） */
export async function getContractLabelMap(ids: string[]): Promise<Record<string, string>> {
  const raws = [...new Set((ids || []).map(String).filter(Boolean))]
  let opts: COpt[] = []
  if (raws.length) opts = await hydrateMissing(raws, [])
  else {
    const pack = await fetchPage({ page: 1, pageSize: 20 })
    opts = (pack.items || []).map((c) => ({ label: c.label || c.id, value: c.id }))
  }
  const map: Record<string, string> = {}
  for (const o of opts) map[o.value] = o.label
  return map
}

/** 生产卡 / 开票申请 / 发货通知选合同带出 */
export async function fetchProdCardContractFill(
  contractId: string,
  mode: 'drawing_no_query' | 'contract_no_select' | 'invoice_application' | 'shipment_notice',
): Promise<Record<string, unknown>> {
  const r = await client.get<unknown, ApiResponse<{ fill?: Record<string, unknown> }>>(
    `/api/v1/lc/pickable-contracts/${encodeURIComponent(contractId)}/prod-card-fill`,
    { params: { mode }, ...silent },
  )
  return (r.data?.fill && typeof r.data.fill === 'object') ? r.data.fill : {}
}

export const PROD_CARD_FILL_CLEAR: Record<
  'drawing_no_query' | 'contract_no_select' | 'invoice_application' | 'shipment_notice',
  string[]
> = {
  drawing_no_query: [
    'no_drawing_no', 'no_sales_person', 'yes_customer_name', 'prod_card_line_items',
    'tech_params', 'packaging_req', 'remark_prod_card', 'paint_req',
    'special_reminder', 'no_warranty_period', 'project_name',
    'contract_tech_review_sn',
  ],
  contract_no_select: [
    'yes_contract_no', 'yes_sales_person', 'yes_customer_name', 'contract_tech_review_sn',
  ],
  invoice_application: [
    'drawing_no', 'customer_name', 'dept_contract_no', 'customer_no', 'customer_code',
    'sales_person', 'contract_data', 'contract_lines_new', 'total_amount',
    'taxpayer_id', 'invoice_address_phone', 'bank_account',
  ],
  shipment_notice: [
    'consignee_unit', 'contract_no_text', 'department', 'sales_person', 'dept_contract_no',
    'need_install', 'counterparty_contract_no', 'accept_method', 'accept_docs', 'contract_amount',
    'ship_lines',
  ],
}

export default function ContractField({
  value, onChange, readonly, placeholder, departmentId,
}: {
  value: unknown
  onChange?: (v: string | undefined) => void
  readonly?: boolean
  placeholder?: string
  /** 按合同所属部门过滤（生产卡：所在部门） */
  departmentId?: string | null
}) {
  const raw = value == null || value === '' ? undefined : String(value)
  const dept = departmentId || undefined
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [rows, setRows] = useState<PickRow[]>([])
  const [columns, setColumns] = useState<ColDef[]>([])
  const [picked, setPicked] = useState('')
  const [display, setDisplay] = useState('')
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const loadPage = async (opts?: { kw?: string; page?: number; pageSize?: number }) => {
    setLoading(true)
    try {
      const pack = await fetchPage({
        keyword: opts?.kw ?? keyword,
        departmentId: dept,
        page: opts?.page ?? page,
        pageSize: opts?.pageSize ?? pageSize,
      })
      setRows(pack.items || [])
      setTotal(pack.total || 0)
      setPage(pack.page || 1)
      setPageSize(pack.page_size || 20)
      if (pack.columns?.length) setColumns(pack.columns)
    } catch {
      setRows([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!raw) {
      setDisplay('')
      return
    }
    void fetchPage({ ids: [raw], departmentId: dept }).then((pack) => {
      const hit = (pack.items || []).find((r) => r.id === raw)
      if (hit?.label) setDisplay(hit.label)
      else if (hit) setDisplay(contractLabel(hit))
    })
  }, [raw, dept])

  useEffect(() => {
    if (!open) return
    setKeyword('')
    setPicked(raw || '')
    setPage(1)
    void loadPage({ kw: '', page: 1 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, dept])

  const commit = (id?: string) => {
    onChange?.(id)
    if (!id) setDisplay('')
    else {
      const hit = rows.find((r) => r.id === id)
      if (hit?.label) setDisplay(hit.label)
      else if (hit) setDisplay(contractLabel(hit))
    }
    setOpen(false)
  }

  const tableCols = useMemo(() => {
    const defs = columns.length
      ? columns
      : [
        { key: 'change_status', title: '合同状态' },
        { key: 'drawing_no', title: '图纸编号' },
        { key: 'customer_name', title: '收货单位' },
        { key: 'department_name', title: '部门' },
      ]
    return defs.map((c) => ({
      title: c.title,
      dataIndex: c.key,
      key: c.key,
      ellipsis: true,
      render: (_: unknown, row: PickRow) => {
        const text = row.cols?.[c.key] || (c.key === 'drawing_no' ? row.drawing_no || '' : '') || '—'
        if (c.key === 'change_status' && text && text !== '—') {
          const color = text === '新增' ? 'red' : text === '变动' ? 'blue' : 'default'
          return <Tag color={color}>{text}</Tag>
        }
        if (c.key === 'drawing_no') return highlightText(String(text), keyword)
        return text
      },
    }))
  }, [columns, keyword])

  if (readonly) {
    return <span>{raw ? (display || raw) : '—'}</span>
  }

  return (
    <>
      <Space wrap>
        <Button type="primary" ghost onClick={() => setOpen(true)}>选择数据</Button>
        {raw ? (
          <>
            <Typography.Text>{display || raw}</Typography.Text>
            <Button type="link" size="small" onClick={() => commit(undefined)}>清除</Button>
          </>
        ) : (
          <Typography.Text type="secondary">{placeholder || '请选择合同'}</Typography.Text>
        )}
      </Space>
      <Modal
        title="选择数据"
        open={open}
        onCancel={() => setOpen(false)}
        width={920}
        destroyOnClose
        okText="确定"
        cancelText="取消"
        onOk={() => commit(picked || undefined)}
        okButtonProps={{ disabled: !picked }}
      >
        <Input
          allowClear
          prefix={<SearchOutlined className="text-slate-400" />}
          placeholder={dept ? '按图纸编号/合同号搜索（本部门合同）' : '按图纸编号/合同号搜索'}
          value={keyword}
          onChange={(e) => {
            const kw = e.target.value
            setKeyword(kw)
            if (searchTimer.current) clearTimeout(searchTimer.current)
            searchTimer.current = setTimeout(() => {
              setPage(1)
              void loadPage({ kw, page: 1 })
            }, 300)
          }}
          style={{ marginBottom: 12 }}
        />
        <Table<PickRow>
          size="small"
          rowKey="id"
          loading={loading}
          dataSource={rows}
          columns={tableCols}
          scroll={{ x: true, y: 420 }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: [10, 20, 50],
            showTotal: (n) => `共 ${n} 条`,
            onChange: (p, ps) => {
              setPage(p)
              setPageSize(ps)
              void loadPage({ page: p, pageSize: ps })
            },
          }}
          rowSelection={{
            type: 'radio',
            selectedRowKeys: picked ? [picked] : [],
            onChange: (keys) => setPicked(String(keys[0] || '')),
          }}
          onRow={(row) => ({
            onClick: () => setPicked(row.id),
            onDoubleClick: () => commit(row.id),
          })}
        />
      </Modal>
    </>
  )
}
