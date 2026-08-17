// 从表单实例中选择（核价清单「选择安装图设计通知数据」等）。值为实例 id。
// 对齐简道云 linkfield：按钮「选择数据」弹出可搜索分页表格。
import { useEffect, useMemo, useRef, useState } from 'react'
import { Button, Input, Modal, Space, Table, Typography } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'
import { PRICING_CHECKLIST_LINKS } from '@/constants/pricingChecklistLinks'

type ColDef = { key: string; title: string }
type PickRow = {
  id: string
  label?: string
  business_no?: string | null
  fill?: Record<string, unknown>
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

export function pricingChecklistClearKeys(linkField: string): string[] {
  return PRICING_CHECKLIST_LINKS[linkField]?.dests || []
}

async function fetchPage(params: {
  formCode: string
  linkField?: string
  keyword?: string
  ids?: string[]
  page?: number
  pageSize?: number
}): Promise<PickPage> {
  const r = await client.get<unknown, ApiResponse<PickPage | PickRow[]>>('/api/v1/lc/pickable-form-instances', {
    params: {
      form_code: params.formCode,
      link_field: params.linkField || undefined,
      keyword: params.keyword || undefined,
      ids: params.ids?.length ? params.ids.join(',') : undefined,
      page: params.page || 1,
      page_size: params.pageSize || 20,
    },
    ...silent,
  })
  const raw = r.data
  if (Array.isArray(raw)) {
    return { items: raw, total: raw.length, page: 1, page_size: raw.length, columns: [] }
  }
  return raw || { items: [], total: 0, page: 1, page_size: 20, columns: [] }
}

export default function FormInstanceLookupField({
  formCode,
  linkField,
  value,
  onChange,
  onFill,
  readonly = false,
  placeholder = '请选择',
}: {
  formCode: string
  linkField?: string
  value?: unknown
  onChange?: (v: unknown) => void
  onFill?: (id: string | undefined, fill: Record<string, unknown>) => void
  readonly?: boolean
  placeholder?: string
}) {
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [total, setTotal] = useState(0)
  const [rows, setRows] = useState<PickRow[]>([])
  const [columns, setColumns] = useState<ColDef[]>([])
  const [picked, setPicked] = useState<string>('')
  const [display, setDisplay] = useState('')
  const fillById = useRef<Record<string, Record<string, unknown>>>({})
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const currentId = value != null && value !== '' ? String(value) : ''

  const rememberFills = (items: PickRow[]) => {
    for (const it of items) {
      if (it.fill) fillById.current[it.id] = it.fill
    }
  }

  const loadPage = async (opts?: { kw?: string; page?: number; pageSize?: number }) => {
    setLoading(true)
    try {
      const pack = await fetchPage({
        formCode,
        linkField,
        keyword: opts?.kw ?? keyword,
        page: opts?.page ?? page,
        pageSize: opts?.pageSize ?? pageSize,
      })
      const items = pack.items || []
      rememberFills(items)
      setRows(items)
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
    if (!currentId) {
      setDisplay('')
      return
    }
    if (fillById.current[currentId]) {
      const hit = rows.find((r) => r.id === currentId)
      if (hit?.label) setDisplay(hit.label)
    }
    void fetchPage({ formCode, linkField, ids: [currentId] }).then((pack) => {
      const items = pack.items || []
      rememberFills(items)
      const hit = items.find((r) => r.id === currentId)
      if (hit?.label) setDisplay(hit.label)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentId, formCode, linkField])

  useEffect(() => {
    if (!open) return
    setKeyword('')
    setPicked(currentId)
    setPage(1)
    void loadPage({ kw: '', page: 1 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, formCode, linkField])

  const commit = (id?: string) => {
    onChange?.(id)
    const fill = id ? (fillById.current[id] || {}) : {}
    onFill?.(id, fill)
    if (!id) setDisplay('')
    else {
      const hit = rows.find((r) => r.id === id)
      if (hit?.label) setDisplay(hit.label)
    }
    setOpen(false)
  }

  const tableCols = useMemo(() => {
    const defs = columns.length
      ? columns
      : [{ key: 'label', title: '数据' }]
    return defs.map((c) => ({
      title: c.title,
      dataIndex: c.key,
      key: c.key,
      ellipsis: true,
      render: (_: unknown, row: PickRow) => (row.cols?.[c.key] || (c.key === 'label' ? row.label : '')) || '—',
    }))
  }, [columns])

  if (readonly) {
    return <span>{currentId ? (display || currentId) : '—'}</span>
  }

  return (
    <>
      <Space wrap>
        <Button type="primary" ghost onClick={() => setOpen(true)}>选择数据</Button>
        {currentId ? (
          <>
            <Typography.Text>{display || currentId}</Typography.Text>
            <Button type="link" size="small" onClick={() => commit(undefined)}>清除</Button>
          </>
        ) : (
          <Typography.Text type="secondary">{placeholder}</Typography.Text>
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
          placeholder="搜索数据"
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
