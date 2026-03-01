import { useState, useEffect } from 'react'
import { Table, Button, Input, Space, Tag, Select, Modal, Upload, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import type { Customer } from '@/api/types'
import { sourceLabels } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { usePageTitle } from '@/hooks/usePageTitle'

const industries = ['电子制造', '汽车零部件', '机械装备', '航空航天', '医疗器械', '半导体', '新能源', '其他']

function Monogram({ name }: { name: string }) {
  const initials = name.slice(0, 2)
  return (
    <div className="w-9 h-9 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center text-sm font-bold text-slate-600 shrink-0">
      {initials}
    </div>
  )
}

export default function CustomerList() {
  usePageTitle('客户管理')
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(Number(searchParams.get('page')) || 1)
  const [keyword, setKeyword] = useState(searchParams.get('q') || '')
  const [industry, setIndustry] = useState<string | undefined>(searchParams.get('industry') || undefined)
  const [region, setRegion] = useState(searchParams.get('region') || '')
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])

  const handleBatchDelete = () => {
    if (!selectedRowKeys.length) return
    Modal.confirm({
      title: '批量删除', content: `确定要删除选中的 ${selectedRowKeys.length} 个客户？`, okType: 'danger',
      onOk: async () => {
        const results = await Promise.allSettled(selectedRowKeys.map((id) => customerApi.delete(id as string)))
        const failed = results.filter((r) => r.status === 'rejected').length
        if (failed > 0) {
          message.warning(`${selectedRowKeys.length - failed} 个已删除，${failed} 个删除失败`)
        } else {
          message.success(`已删除 ${selectedRowKeys.length} 个客户`)
        }
        setSelectedRowKeys([])
        fetchData()
      },
    })
  }

  const fetchData = async (page = pageNo, kw = keyword, ind = industry, reg = region) => {
    setLoading(true)
    try {
      const res = await customerApi.list({
        pageNo: page, pageSize: 20,
        keyword: kw || undefined, industry: ind, region: reg || undefined,
      })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const doSearch = () => {
    setPageNo(1)
    const params: Record<string, string> = {}
    if (keyword) params.q = keyword
    if (industry) params.industry = industry
    if (region) params.region = region
    setSearchParams(params, { replace: true })
    fetchData(1, keyword, industry, region)
  }

  const levelColors: Record<string, string> = {
    A: 'bg-red-100 text-red-700 border-red-200',
    B: 'bg-amber-100 text-amber-700 border-amber-200',
    C: 'bg-blue-100 text-blue-700 border-blue-200',
    D: 'bg-slate-100 text-slate-600 border-slate-200',
  }

  const columns: ColumnsType<Customer> = [
    { title: '客户', key: 'name', width: 240,
      render: (_, record) => (
        <div className="flex items-center gap-3">
          <Monogram name={record.name} />
          <div>
            <a onClick={() => navigate(`/customers/${record.id}`)} className="text-sm font-bold text-slate-900 hover:text-primary">
              {record.name}
            </a>
            {record.short_name && <div className="text-[11px] text-slate-400">{record.short_name}</div>}
          </div>
        </div>
      ),
    },
    { title: '行业', dataIndex: 'industry', width: 120,
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '规模', dataIndex: 'scale_level', width: 80, responsive: ['lg'],
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '区域', dataIndex: 'region', width: 100,
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '级别', dataIndex: 'level', width: 70,
      render: (v) => v ? (
        <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-black uppercase border ${levelColors[v] || levelColors.D}`}>
          {v}
        </span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '来源', dataIndex: 'source', width: 100, responsive: ['lg'],
      render: (v) => v ? (sourceLabels[v] || v) : <span className="text-slate-300">-</span> },
    { title: '状态', dataIndex: 'status', width: 80,
      render: (v) => (
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${v === 'active' ? 'bg-emerald-500' : 'bg-slate-300'}`} />
          <span className="text-xs font-medium text-slate-600">{v === 'active' ? '活跃' : '不活跃'}</span>
        </div>
      ),
    },
    { title: '负责人', dataIndex: 'owner_name', width: 100,
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '创建时间', dataIndex: 'created_at', width: 110, responsive: ['xl'],
      render: (v) => v ? <span className="text-xs text-slate-500">{new Date(v).toLocaleDateString('zh-CN')}</span> : '-' },
    { title: '', key: 'actions', width: 150, fixed: 'right',
      render: (_, record) => (
        <Space size={0}>
          <a onClick={() => navigate(`/customers/${record.id}`)} className="text-primary text-xs font-bold uppercase tracking-widest px-2">详情</a>
          <a onClick={() => navigate(`/customers/${record.id}/edit`)} className="text-slate-500 text-xs font-bold uppercase tracking-widest px-2 hover:text-primary">编辑</a>
          <a className="text-xs font-bold uppercase tracking-widest px-2 text-rose-500 hover:text-rose-600" onClick={() => {
            Modal.confirm({
              title: '确认删除', content: `确定要删除客户「${record.name}」及其所有联系人？`,
              okType: 'danger',
              onOk: async () => {
                await customerApi.delete(record.id)
                message.success('客户已删除')
                fetchData()
              },
            })
          }}>删除</a>
        </Space>
      ),
    },
  ]

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">客户管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理和跟踪所有客户信息</p>
        </div>
        <Space wrap>
          <Upload accept=".xlsx,.xls" showUploadList={false} customRequest={async ({ file }) => {
            const formData = new FormData()
            formData.append('file', file as File)
            try {
              const token = localStorage.getItem('access_token')
              const res = await fetch('/api/v1/customers/import/excel', {
                method: 'POST', body: formData,
                headers: { Authorization: `Bearer ${token}` },
              })
              const json = await res.json()
              if (json.code === 0) {
                message.success(`导入成功: ${json.data.created} 条${json.data.errors?.length ? `, ${json.data.errors.length} 条失败` : ''}`)
                fetchData()
              } else { message.error(json.message || '导入失败') }
            } catch { message.error('导入失败') }
          }}>
            <Button icon={<UploadOutlined />}>导入</Button>
          </Upload>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/customers/export/excel', 'customers.xlsx')}>导出</Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/customers/new')}
            className="shadow-lg shadow-primary/20 font-bold"
          >
            新建客户
          </Button>
        </Space>
      </div>

      {selectedRowKeys.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-700">已选中 {selectedRowKeys.length} 项</span>
          <Space>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>批量删除</Button>
            <Button size="small" onClick={() => setSelectedRowKeys([])}>取消选择</Button>
          </Space>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center flex-col sm:flex-row">
          <Input
            placeholder="搜索客户名称..."
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }}
            className="rounded-lg"
          />
          <Select
            placeholder="行业"
            allowClear
            style={{ width: 140 }}
            value={industry}
            onChange={(v) => { setIndustry(v); setPageNo(1); fetchData(1, keyword, v, region) }}
            options={industries.map((i) => ({ label: i, value: i }))}
          />
          <Input
            placeholder="区域"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 140 }}
          />
          <Button onClick={doSearch}>
            <span className="material-symbols-outlined text-sm mr-1">filter_list</span>
            筛选
          </Button>
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 1100 }}
          rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors"
        />
      </div>
    </div>
  )
}
