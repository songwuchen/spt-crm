import { useState, useEffect } from 'react'
import { Button, Table, Input, Tag, Modal, message } from 'antd'
import { useNavigate } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { Customer } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'

export default function CustomerPool() {
  usePageTitle('客户公海')
  const navigate = useNavigate()
  const [items, setItems] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)

  const fetch = async (p = page) => {
    setLoading(true)
    try {
      const res = await customerApi.listPool({ pageNo: p, pageSize: 20, keyword: keyword || undefined })
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

  const levelColors: Record<string, string> = { A: 'red', B: 'orange', C: 'blue', D: 'default' }

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
      </div>

      <div className="flex items-center gap-3 mb-4">
        <Input.Search placeholder="搜索客户名称" value={keyword} onChange={(e) => setKeyword(e.target.value)}
          onSearch={handleSearch} enterButton style={{ width: 280 }} allowClear />
        <div className="flex-1" />
        <div className="text-sm text-slate-500">共 {total} 个客户</div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={columns} dataSource={items} loading={loading} size="small"
          pagination={{ current: page, total, pageSize: 20, onChange: setPage, showTotal: (t) => `共 ${t} 条` }} />
      </div>
    </div>
  )
}
