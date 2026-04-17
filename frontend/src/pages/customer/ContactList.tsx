import { useState, useEffect } from 'react'
import { Table, Input, Select, Tag } from 'antd'
import { SearchOutlined, PhoneOutlined, MailOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { contactApi } from '@/api/contact'
import type { Contact } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePageSize } from '@/hooks/usePageSize'

const roleTypeLabels: Record<string, string> = {
  decision_maker: '决策人',
  influencer: '影响者',
  user: '使用者',
  finance: '财务',
  procurement: '采购',
}
const roleTypeColors: Record<string, string> = {
  decision_maker: 'red',
  influencer: 'orange',
  user: 'blue',
  finance: 'green',
  procurement: 'purple',
}

type ContactItem = Contact & { customer_name?: string }

export default function ContactList() {
  usePageTitle('联系人')
  const navigate = useNavigate()
  const [data, setData] = useState<ContactItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [roleType, setRoleType] = useState<string | undefined>()
  const [pageSize, setPageSize] = usePageSize('contacts')

  const fetchData = async (page = pageNo, kw = keyword, rt = roleType) => {
    setLoading(true)
    try {
      const res = await contactApi.listAll({
        pageNo: page, pageSize,
        keyword: kw || undefined, role_type: rt,
      })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const doSearch = () => { setPageNo(1); fetchData(1) }

  const columns: ColumnsType<ContactItem> = [
    {
      title: '姓名', dataIndex: 'name', width: 150,
      render: (v: string, r) => (
        <span className="font-semibold text-slate-800">{v}{r.is_primary && <Tag color="gold" className="ml-1 text-[10px]">主联系人</Tag>}</span>
      ),
    },
    { title: '职位', dataIndex: 'title', width: 120, render: (v: string) => v || '-' },
    {
      title: '角色', dataIndex: 'role_type', width: 100,
      render: (v: string) => v ? <Tag color={roleTypeColors[v]}>{roleTypeLabels[v] || v}</Tag> : '-',
    },
    {
      title: '所属客户', dataIndex: 'customer_name', width: 180,
      render: (v: string, r) => (
        <a className="text-primary cursor-pointer" onClick={() => navigate(`/customers/${r.customer_id}`)}>{v || '-'}</a>
      ),
    },
    {
      title: '电话', key: 'phone', width: 150,
      render: (_, r) => (
        <span className="text-slate-600">
          {r.mobile && <span><PhoneOutlined className="mr-1" />{r.mobile}</span>}
          {!r.mobile && r.phone && <span><PhoneOutlined className="mr-1" />{r.phone}</span>}
          {!r.mobile && !r.phone && '-'}
        </span>
      ),
    },
    {
      title: '邮箱', dataIndex: 'email', width: 200,
      render: (v: string) => v ? <span><MailOutlined className="mr-1 text-slate-400" />{v}</span> : '-',
    },
    { title: '备注', dataIndex: 'remark', ellipsis: true },
  ]

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">联系人管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">跨客户搜索和管理所有联系人</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder="搜索姓名/电话/邮箱..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }}
          />
          <Select
            placeholder="角色类型"
            allowClear
            style={{ width: 140 }}
            value={roleType}
            onChange={(v) => { setRoleType(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(roleTypeLabels).map(([k, v]) => ({ label: v, value: k }))}
          />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 900 }}
          pagination={{
            current: pageNo, total, pageSize, showTotal: (t) => `共 ${t} 条`,
            showSizeChanger: true, pageSizeOptions: ['20', '50', '100'],
            onChange: (p) => { setPageNo(p); fetchData(p) },
            onShowSizeChange: (_current, size) => { setPageSize(size); setPageNo(1); fetchData(1) },
          }}
        />
      </div>
    </div>
  )
}
