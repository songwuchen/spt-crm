import { useState, useEffect } from 'react'
import { Button, Table, Input, Tag, Modal, Select, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useDataDict } from '@/hooks/useDataDict'
import type { Customer } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'

export default function CustomerPool() {
  usePageTitle('客户公海')
  const navigate = useNavigate()
  const [items, setItems] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterLevel, setFilterLevel] = useState<string | undefined>()
  const [loading, setLoading] = useState(false)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const levelDict = useDataDict('customer_level', ['A', 'B', 'C', 'D'].map(l => ({ label: `${l}级`, value: l })))

  const fetch = async (p = page) => {
    setLoading(true)
    try {
      const res = await customerApi.listPool({
        pageNo: p, pageSize: 20,
        keyword: keyword || undefined,
        level: filterLevel,
      })
      setItems(res.data?.items || [])
      setTotal(res.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetch(page) }, [page])

  const handleSearch = () => { setPage(1); fetch(1) }

  const handleClaim = (id: string, name: string) => {
    Modal.confirm({
      title: '领取客户',
      content: `确认领取「${name}」？领取后您将成为该客户的负责人。`,
      okText: '确认领取',
      onOk: async () => {
        await customerApi.claim(id)
        message.success(`已成功领取客户「${name}」`)
        fetch()
      },
    })
  }

  const handleBatchClaim = () => {
    if (selectedIds.length === 0) { message.warning('请先勾选客户'); return }
    Modal.confirm({
      title: `批量领取 ${selectedIds.length} 个客户？`,
      content: '领取后您将成为这些客户的负责人',
      okText: '确认领取',
      onOk: async () => {
        let ok = 0
        for (const id of selectedIds) {
          try { await customerApi.claim(id); ok++ } catch { /* skip failed */ }
        }
        message.success(`成功领取 ${ok} 个客户`)
        setSelectedIds([])
        fetch()
      },
    })
  }

  const levelColors: Record<string, string> = { A: 'red', B: 'orange', C: 'blue', D: 'default' }
  const levelCounts = items.reduce<Record<string, number>>((acc, c) => {
    const lv = (c as any).level || '-'
    acc[lv] = (acc[lv] || 0) + 1
    return acc
  }, {})

  const columns: ColumnsType<Customer> = [
    { title: '客户名称', dataIndex: 'name', width: 200,
      render: (v, r) => (
        <a className="font-semibold text-primary" onClick={() => navigate(`/customers/${r.id}`)}>{v}</a>
      ) },
    { title: '级别', dataIndex: 'level', width: 60,
      render: (v) => v ? <Tag color={levelColors[v] || 'default'}>{v}</Tag> : '-' },
    { title: '行业', dataIndex: 'industry', width: 100 },
    { title: '地区', dataIndex: 'region', width: 100 },
    { title: '来源', dataIndex: 'source', width: 80 },
    { title: '释放时间', dataIndex: 'updated_at', width: 150,
      render: (v) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
    { title: '操作', key: 'actions', width: 100,
      render: (_, r) => (
        <Button type="primary" size="small" onClick={() => handleClaim(r.id, r.name)}>
          领取
        </Button>
      ),
    },
  ]

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">客户公海</h1>
          <p className="text-sm text-slate-500 mt-1">无人负责的客户，可自由领取跟进</p>
        </div>
        {selectedIds.length > 0 && (
          <Button type="primary" onClick={handleBatchClaim}>
            批量领取 ({selectedIds.length})
          </Button>
        )}
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="bg-white border border-slate-200 rounded-lg px-4 py-2">
          <span className="text-xs text-slate-500">总数</span>
          <span className="ml-2 text-lg font-black text-slate-900">{total}</span>
        </div>
        {Object.entries(levelCounts).filter(([k]) => k !== '-').map(([lv, cnt]) => (
          <div key={lv} className="bg-white border border-slate-200 rounded-lg px-4 py-2">
            <Tag color={levelColors[lv] || 'default'} className="mr-1">{lv}级</Tag>
            <span className="text-sm font-bold text-slate-700">{cnt}</span>
          </div>
        ))}
      </div>

      <div className="flex items-center gap-3 mb-4">
        <Input.Search placeholder="搜索客户名称" value={keyword} onChange={(e) => setKeyword(e.target.value)}
          onSearch={handleSearch} enterButton style={{ width: 280 }} allowClear />
        <Select placeholder="级别" allowClear style={{ width: 100 }} value={filterLevel}
          onChange={(v) => { setFilterLevel(v); setPage(1); setTimeout(() => fetch(1), 0) }}
          options={levelDict.options} />
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small"
          rowSelection={{
            selectedRowKeys: selectedIds,
            onChange: (keys) => setSelectedIds(keys as string[]),
          }}
          pagination={{ current: page, total, pageSize: 20, onChange: setPage, showTotal: (t) => `共 ${t} 条` }} />
      </div>
    </div>
  )
}
