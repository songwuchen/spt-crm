import { useState, useEffect } from 'react'
import { Table, Button, Input, Space, Tag, Select, Modal, Form, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, UploadOutlined, DeleteOutlined, MailOutlined } from '@ant-design/icons'
import ImportModal from '@/components/ImportModal'
import { downloadFile } from '@/utils/download'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import type { Customer } from '@/api/types'
import { sourceLabels } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useRemoteSelect } from '@/hooks/useRemoteSelect'
import { useDataDict } from '@/hooks/useDataDict'
import { useColumnConfig } from '@/hooks/useColumnConfig'
import { useCountdownConfirm } from '@/hooks/useCountdownConfirm'
import { userApi } from '@/api/user'
import SavedViewSelect from '@/components/SavedViewSelect'
import ColumnConfigDropdown from '@/components/ColumnConfigDropdown'
import EditableCell from '@/components/EditableCell'
import FeatureTip from '@/components/FeatureTip'
import RegionMap from '@/components/RegionMap'
import CustomerTagCloud from '@/components/CustomerTagCloud'

const defaultIndustries = ['电子制造', '汽车零部件', '机械装备', '航空航天', '医疗器械', '半导体', '新能源', '其他'].map(i => ({ label: i, value: i }))

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
  const [importModal, setImportModal] = useState(false)
  const [transferModal, setTransferModal] = useState(false)
  const [transferForm] = Form.useForm()
  const [messageModal, setMessageModal] = useState(false)
  const [messageForm] = Form.useForm()
  const [messageSending, setMessageSending] = useState(false)
  const [showMap, setShowMap] = useState(false)
  const [showTagCloud, setShowTagCloud] = useState(false)
  const [regionData, setRegionData] = useState<{ region: string; count: number }[]>([])

  useEffect(() => {
    if (showMap) {
      customerApi.regionDistribution().then((r) => setRegionData(r.data || [])).catch(() => {})
    }
  }, [showMap])
  const industryDict = useDataDict('industry', defaultIndustries)
  const dangerConfirm = useCountdownConfirm()
  const userSelect = useRemoteSelect(async (kw) => {
    const r = await userApi.list({ pageNo: 1, pageSize: 100, keyword: kw })
    return (r.data?.items || []).map((u: any) => ({ label: u.real_name || u.username, value: u.id }))
  })

  const handleBatchRelease = () => {
    if (!selectedRowKeys.length) return
    Modal.confirm({
      title: '批量释放到公海', content: `确定要将选中的 ${selectedRowKeys.length} 个客户释放到公海池？`,
      onOk: async () => {
        const res = await customerApi.batchRelease(selectedRowKeys as string[])
        message.success(`已释放 ${res.data?.released || 0} 个客户到公海`)
        setSelectedRowKeys([])
        fetchData()
      },
    })
  }

  const handleBatchTransfer = async () => {
    const values = await transferForm.validateFields()
    const ownerName = userSelect.options.find(o => o.value === values.owner_id)?.label || ''
    try {
      const res = await customerApi.batchTransfer(selectedRowKeys as string[], values.owner_id, ownerName)
      message.success(`已转让 ${(res as any).data?.updated || selectedRowKeys.length} 个客户`)
      setTransferModal(false)
      transferForm.resetFields()
      setSelectedRowKeys([])
      fetchData()
    } catch { message.error('批量转让失败') }
  }

  const handleBatchDelete = () => {
    if (!selectedRowKeys.length) return
    dangerConfirm({
      title: '批量删除',
      content: `确定要删除选中的 ${selectedRowKeys.length} 个客户？此操作不可撤销。`,
      okText: '删除',
      countdown: 3,
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

  const handleBatchMessage = async () => {
    const values = await messageForm.validateFields()
    setMessageSending(true)
    try {
      const res = await customerApi.batchMessage({
        customer_ids: selectedRowKeys as string[],
        channel: values.channel,
        subject: values.subject,
        content: values.content,
      })
      const d = res.data
      message.success(`发送完成: 成功 ${d?.sent || 0}，失败 ${d?.failed || 0}`)
      setMessageModal(false)
      messageForm.resetFields()
    } catch {
      message.error('批量发送失败')
    } finally {
      setMessageSending(false)
    }
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
      render: (v: string, record: Customer) => (
        <EditableCell value={v} type="text" placeholder="区域"
          onSave={async (val) => { await customerApi.update(record.id, { region: val }); fetchData() }} />
      ),
    },
    { title: '级别', dataIndex: 'level', width: 90,
      render: (v: string, record: Customer) => (
        <EditableCell value={v} type="select" placeholder="级别"
          options={[{ label: 'A', value: 'A' }, { label: 'B', value: 'B' }, { label: 'C', value: 'C' }, { label: 'D', value: 'D' }]}
          onSave={async (val) => { await customerApi.update(record.id, { level: val }); fetchData() }} />
      ),
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
    { title: '标签', dataIndex: 'tags_json', width: 150, responsive: ['lg'],
      render: (v: string[]) => v?.length ? (
        <div className="flex gap-1 flex-wrap">{v.slice(0, 3).map((t) => <Tag key={t} className="text-[10px] m-0">{t}</Tag>)}{v.length > 3 && <span className="text-[10px] text-slate-400">+{v.length - 3}</span>}</div>
      ) : <span className="text-slate-300">-</span>,
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
            dangerConfirm({
              title: '确认删除',
              content: `确定要删除客户「${record.name}」及其所有联系人？此操作不可撤销。`,
              okText: '删除',
              countdown: 3,
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

  const { visibleColumns, hiddenKeys, setColumnConfig, allColumnKeys } = useColumnConfig('customers', columns)

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">客户管理</h1>
          <p className="text-sm text-slate-500 mt-0.5">管理和跟踪所有客户信息</p>
        </div>
        <Space wrap>
          <Button onClick={() => setShowTagCloud(!showTagCloud)}
            type={showTagCloud ? 'primary' : 'default'} ghost={showTagCloud}>
            <span className="material-symbols-outlined text-sm mr-1" style={{ fontSize: 14 }}>sell</span>
            标签云
          </Button>
          <Button onClick={() => setShowMap(!showMap)}
            type={showMap ? 'primary' : 'default'} ghost={showMap}>
            <span className="material-symbols-outlined text-sm mr-1" style={{ fontSize: 14 }}>map</span>
            {showMap ? '列表' : '地图'}
          </Button>
          <Button icon={<UploadOutlined />} onClick={() => setImportModal(true)}>导入</Button>
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

      {showTagCloud && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
          <h3 className="text-sm font-bold text-slate-900 mb-3">客户标签画像</h3>
          <CustomerTagCloud
            tags={data.flatMap((c) => (c.tags_json as unknown as string[]) || [])}
            onClick={(tag) => { setKeyword(tag); setPageNo(1) }}
          />
        </div>
      )}

      {selectedRowKeys.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-700">已选中 {selectedRowKeys.length} 项</span>
          <Space>
            <Button size="small" onClick={() => { transferForm.resetFields(); setTransferModal(true) }}>批量转让</Button>
            <Button size="small" icon={<MailOutlined />} onClick={() => { messageForm.resetFields(); setMessageModal(true) }}>群发消息</Button>
            <Button size="small" onClick={handleBatchRelease}>释放到公海</Button>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>批量删除</Button>
            <Button size="small" onClick={() => setSelectedRowKeys([])}>取消选择</Button>
          </Space>
        </div>
      )}

      <FeatureTip id="customer-swipe-actions" title="批量操作提示"
        content="勾选客户后可进行批量转让、群发消息、释放到公海等操作。左滑客户可快速拨号或删除。" />

      {showMap && (
        <div className="mb-4">
          <RegionMap data={regionData} onRegionClick={(r) => { setRegion(r); setShowMap(false); fetchData(1, keyword, industry, r) }} />
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
            options={industryDict.options}
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
          <ColumnConfigDropdown allColumnKeys={allColumnKeys} hiddenKeys={hiddenKeys} onChange={setColumnConfig} />
          <SavedViewSelect
            page="customers"
            currentFilters={{ keyword, industry, region }}
            onApply={(f) => {
              setKeyword(f.keyword || ''); setIndustry(f.industry || undefined); setRegion(f.region || '')
              fetchData(1, f.keyword || '', f.industry, f.region || '')
            }}
          />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={visibleColumns}
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

      {/* Import Modal */}
      <ImportModal
        open={importModal}
        onClose={() => setImportModal(false)}
        onSuccess={() => fetchData()}
        previewUrl="/api/v1/customers/import/preview"
        importUrl="/api/v1/customers/import/excel"
        templateUrl="/api/v1/customers/import/template"
        title="导入客户"
        expectedHeaders={['客户名称', '简称', '行业', '规模', '区域', '地址', '来源', '级别']}
      />

      {/* Batch Transfer Modal */}
      <Modal title="批量转让客户" open={transferModal} onOk={handleBatchTransfer}
        onCancel={() => setTransferModal(false)} okText="确认转让">
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            将选中的 <b>{selectedRowKeys.length}</b> 个客户转让给新的负责人
          </div>
          <Form form={transferForm} layout="vertical">
            <Form.Item name="owner_id" label="新负责人" rules={[{ required: true, message: '请选择' }]}>
              <Select showSearch filterOption={false} placeholder="搜索用户"
                loading={userSelect.loading} options={userSelect.options}
                onSearch={userSelect.onSearch} onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            </Form.Item>
          </Form>
        </div>
      </Modal>

      {/* Batch Message Modal */}
      <Modal title="群发消息" open={messageModal} onOk={handleBatchMessage}
        onCancel={() => setMessageModal(false)} okText="发送" confirmLoading={messageSending}>
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            向选中的 <b>{selectedRowKeys.length}</b> 个客户的主要联系人发送消息
          </div>
          <Form form={messageForm} layout="vertical" initialValues={{ channel: 'email' }}>
            <Form.Item name="channel" label="发送渠道" rules={[{ required: true }]}>
              <Select options={[{ label: '邮件', value: 'email' }, { label: '短信', value: 'sms' }]} />
            </Form.Item>
            <Form.Item name="subject" label="主题" rules={[{ required: true, message: '请输入主题' }]}>
              <Input placeholder="消息主题" />
            </Form.Item>
            <Form.Item name="content" label="内容" rules={[{ required: true, message: '请输入内容' }]}>
              <Input.TextArea rows={4} placeholder="消息正文内容" />
            </Form.Item>
          </Form>
        </div>
      </Modal>
    </div>
  )
}
