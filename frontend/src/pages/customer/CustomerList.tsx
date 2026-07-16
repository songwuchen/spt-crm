import { useState, useEffect, useRef } from 'react'
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
import { t } from '@/locales'
import { useDataDict } from '@/hooks/useDataDict'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useListView } from '@/hooks/useListView'
import { usePageSize } from '@/hooks/usePageSize'
import { useCountdownConfirm } from '@/hooks/useCountdownConfirm'
import ListToolbar from '@/components/list/ListToolbar'
import EditableCell from '@/components/EditableCell'
import FeatureTip from '@/components/FeatureTip'
import RegionMap from '@/components/RegionMap'
import CustomerTagCloud from '@/components/CustomerTagCloud'
import RegionCascader from '@/components/RegionCascader'
import type { RegionValue } from '@/components/RegionCascader'
import { formatRegion } from '@/utils/address'

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
  usePageTitle(t('customer.title'))
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<Customer[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(Number(searchParams.get('page')) || 1)
  const [keyword, setKeyword] = useState(searchParams.get('q') || '')
  const [industry, setIndustry] = useState<string | undefined>(searchParams.get('industry') || undefined)
  // 结构化地址过滤：regionCode = 行政区划编码前缀(单值=级联精确，逗号多值=大区)；
  // regionName = 所选地区名(省/市/区县或大区名)，与 regionCode 取并集,兼容未回填的 legacy 文本客户；
  // filterRegion 仅用于级联选择器回显
  const [regionCode, setRegionCode] = useState(searchParams.get('region_code') || '')
  const [regionName, setRegionName] = useState(searchParams.get('region') || '')
  const [filterRegion, setFilterRegion] = useState<RegionValue>({})
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [importModal, setImportModal] = useState(false)
  const [transferModal, setTransferModal] = useState(false)
  const [transferForm] = Form.useForm()
  const [messageModal, setMessageModal] = useState(false)
  const [messageForm] = Form.useForm()
  const [messageSending, setMessageSending] = useState(false)
  const [showMap, setShowMap] = useState(false)
  const [showTagCloud, setShowTagCloud] = useState(false)
  const [pageSize, setPageSize] = usePageSize('customers')
  const [regionData, setRegionData] = useState<{ region: string; count: number }[]>([])
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  useEffect(() => {
    if (showMap) {
      customerApi.regionDistribution().then((r) => setRegionData(r.data || [])).catch(() => {})
    }
  }, [showMap])
  const industryDict = useDataDict('industry', defaultIndustries)
  const industryMap = Object.fromEntries(industryDict.options.map((o) => [o.value, o.label]))
  const dangerConfirm = useCountdownConfirm()
  const userSelect = useUserSelect()

  const handleBatchRelease = () => {
    if (!selectedRowKeys.length) return
    Modal.confirm({
      title: t('customer.batchRelease'), content: t('customer.batchReleaseConfirm', { count: selectedRowKeys.length }),
      onOk: async () => {
        const res = await customerApi.batchRelease(selectedRowKeys as string[])
        message.success(t('customer.batchReleaseDone', { count: res.data?.released || 0 }))
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
      message.success(t('customer.transferDone', { count: (res as any).data?.updated || selectedRowKeys.length }))
      setTransferModal(false)
      transferForm.resetFields()
      setSelectedRowKeys([])
      fetchData()
    } catch { message.error(t('common.failed')) }
  }

  const handleBatchDelete = () => {
    if (!selectedRowKeys.length) return
    dangerConfirm({
      title: t('common.batchDelete'),
      content: t('common.batchDeleteConfirm', { count: selectedRowKeys.length }),
      okText: t('common.delete'),
      countdown: 3,
      onOk: async () => {
        const results = await Promise.allSettled(selectedRowKeys.map((id) => customerApi.delete(id as string)))
        const failed = results.filter((r) => r.status === 'rejected').length
        if (failed > 0) {
          message.warning(t('common.batchDeleteDone', { count: selectedRowKeys.length - failed }) + `，${failed} ` + t('common.failed'))
        } else {
          message.success(t('common.batchDeleteDone', { count: selectedRowKeys.length }))
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
      message.success(t('common.success') + `: ${d?.sent || 0} / ${d?.failed || 0}`)
      setMessageModal(false)
      messageForm.resetFields()
    } catch {
      message.error(t('common.failed'))
    } finally {
      setMessageSending(false)
    }
  }

  const fetchData = async (page = pageNo, kw = keyword, ind = industry, rc = regionCode, rn = regionName) => {
    setLoading(true)
    try {
      const res = await customerApi.list({
        pageNo: page, pageSize,
        keyword: kw || undefined, industry: ind,
        region_code: rc || undefined, region: rn || undefined,
        ...view.buildParams(),
      })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取（reload 在 state 更新后再触发，避免读到旧值）
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload])

  const doSearch = () => {
    setPageNo(1)
    const params: Record<string, string> = {}
    if (keyword) params.q = keyword
    if (industry) params.industry = industry
    if (regionCode) params.region_code = regionCode
    if (regionName) params.region = regionName
    setSearchParams(params, { replace: true })
    fetchData(1, keyword, industry, regionCode, regionName)
  }

  const levelColors: Record<string, string> = {
    A: 'bg-red-100 text-red-700 border-red-200',
    B: 'bg-amber-100 text-amber-700 border-amber-200',
    C: 'bg-blue-100 text-blue-700 border-blue-200',
    D: 'bg-slate-100 text-slate-600 border-slate-200',
  }

  const columns: ColumnsType<Customer> = [
    { title: t('customer.name'), key: 'name', width: 240,
      render: (_, record) => (
        <div className="flex items-center gap-3">
          <Monogram name={record.name} />
          <div>
            <a onClick={() => navigate(`/customers/${record.id}`)} className="text-sm font-bold text-slate-900 hover:text-primary">
              {record.name}
            </a>
            {record.short_name && <div className="text-[13px] text-slate-400">{record.short_name}</div>}
          </div>
        </div>
      ),
    },
    { title: t('customer.industry'), dataIndex: 'industry', width: 120,
      render: (v) => v ? (industryMap[v] || v) : <span className="text-slate-300">-</span> },
    { title: t('customer.level'), dataIndex: 'scale_level', width: 80, responsive: ['lg'],
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: t('customer.region'), key: 'region', width: 150,
      render: (_: unknown, record: Customer) => {
        const label = formatRegion(record)
        return label ? <span className="text-sm text-slate-700">{label}</span> : <span className="text-slate-300">-</span>
      },
    },
    { title: t('customer.level'), dataIndex: 'level', width: 90,
      render: (v: string, record: Customer) => (
        <EditableCell value={v} type="select" placeholder={t('customer.level')}
          options={[{ label: 'A', value: 'A' }, { label: 'B', value: 'B' }, { label: 'C', value: 'C' }, { label: 'D', value: 'D' }]}
          onSave={async (val) => { await customerApi.update(record.id, { level: val }); fetchData() }} />
      ),
    },
    { title: t('lead.source'), dataIndex: 'source', width: 100, responsive: ['lg'],
      render: (v) => v ? (sourceLabels[v] || v) : <span className="text-slate-300">-</span> },
    { title: t('customer.status'), dataIndex: 'status', width: 80,
      render: (v) => (
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${v === 'active' ? 'bg-emerald-500' : 'bg-slate-300'}`} />
          <span className="text-sm font-medium text-slate-600">{v === 'active' ? '活跃' : '不活跃'}</span>
        </div>
      ),
    },
    { title: '标签', dataIndex: 'tags_json', width: 150, responsive: ['lg'],
      render: (v: string[]) => v?.length ? (
        <div className="flex gap-1 flex-wrap">{v.slice(0, 3).map((tag) => <Tag key={tag} className="text-[12px] m-0">{tag}</Tag>)}{v.length > 3 && <span className="text-[12px] text-slate-400">+{v.length - 3}</span>}</div>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: t('common.owner'), dataIndex: 'owner_name', width: 100,
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: t('common.createdAt'), dataIndex: 'created_at', width: 110, responsive: ['xl'],
      render: (v) => v ? <span className="text-sm text-slate-500">{new Date(v).toLocaleDateString('zh-CN')}</span> : '-' },
    { title: '', key: 'actions', width: 150, fixed: 'right',
      render: (_, record) => (
        <Space size={0}>
          <a onClick={() => navigate(`/customers/${record.id}`)} className="text-primary text-sm font-bold uppercase tracking-widest px-2">{t('common.detail')}</a>
          <a onClick={() => navigate(`/customers/${record.id}/edit`)} className="text-slate-500 text-sm font-bold uppercase tracking-widest px-2 hover:text-primary">{t('common.edit')}</a>
          <a className="text-sm font-bold uppercase tracking-widest px-2 text-rose-500 hover:text-rose-600" onClick={() => {
            dangerConfirm({
              title: t('common.confirmDelete'),
              content: t('customer.deleteConfirm', { name: record.name }),
              okText: t('common.delete'),
              countdown: 3,
              onOk: async () => {
                await customerApi.delete(record.id)
                message.success(t('common.deleted'))
                fetchData()
              },
            })
          }}>{t('common.delete')}</a>
        </Space>
      ),
    },
  ]

  const view = useListView<Customer>('customer', columns, { pageKey: 'customers' })

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{t('customer.title')}</h1>
          <p className="text-sm text-slate-500 mt-0.5">{t('customer.subtitle')}</p>
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
          <Button icon={<UploadOutlined />} onClick={() => setImportModal(true)}>{t('common.import')}</Button>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/customers/export/excel', 'customers.xlsx')}>{t('common.export')}</Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/customers/new')}
            className="shadow-lg shadow-primary/20 font-bold"
          >
            {t('customer.createCustomer')}
          </Button>
        </Space>
      </div>

      {showTagCloud && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
          <h3 className="text-sm font-bold text-slate-900 mb-3">{t('ai.customerProfile')}</h3>
          <CustomerTagCloud
            tags={data.flatMap((c) => (c.tags_json as unknown as string[]) || [])}
            onClick={(tag) => { setKeyword(tag); setPageNo(1) }}
          />
        </div>
      )}

      {selectedRowKeys.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-700">{t('common.selected', { count: selectedRowKeys.length })}</span>
          <Space>
            <Button size="small" onClick={() => { transferForm.resetFields(); setTransferModal(true) }}>{t('customer.batchTransfer')}</Button>
            <Button size="small" icon={<MailOutlined />} onClick={() => { messageForm.resetFields(); setMessageModal(true) }}>群发消息</Button>
            <Button size="small" onClick={handleBatchRelease}>{t('customer.releaseToPool')}</Button>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>{t('common.batchDelete')}</Button>
            <Button size="small" onClick={() => setSelectedRowKeys([])}>{t('common.cancelSelect')}</Button>
          </Space>
        </div>
      )}

      <FeatureTip id="customer-swipe-actions" title="批量操作提示"
        content="勾选客户后可进行批量转让、群发消息、释放到公海等操作。左滑客户可快速拨号或删除。" />

      {showMap && (
        <div className="mb-4">
          <RegionMap data={regionData} onRegionClick={(code, name) => { setRegionCode(code); setRegionName(name); setFilterRegion({}); setShowMap(false); fetchData(1, keyword, industry, code, name) }} />
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center flex-col sm:flex-row">
          <Input
            placeholder={t('customer.searchPlaceholder')}
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }}
            className="rounded-lg"
          />
          <Select
            placeholder={t('customer.industry')}
            allowClear
            style={{ width: 140 }}
            value={industry}
            onChange={(v) => { setIndustry(v); setPageNo(1); fetchData(1, keyword, v, regionCode, regionName) }}
            options={industryDict.options}
          />
          <div style={{ width: 220 }}>
            <RegionCascader
              value={filterRegion}
              placeholder={t('customer.region')}
              onChange={(v) => {
                setFilterRegion(v)
                const code = v.regionCode || ''
                // 兼容 legacy 文本客户：同时按所选最深层级名称做包含匹配
                const name = v.district || v.city || v.province || ''
                setRegionCode(code)
                setRegionName(name)
                setPageNo(1)
                fetchData(1, keyword, industry, code, name)
              }}
            />
          </div>
          <Button onClick={doSearch}>
            <span className="material-symbols-outlined text-sm mr-1">filter_list</span>
            {t('common.filter')}
          </Button>
          <ListToolbar resource="customer" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table
          rowKey="id"
          columns={view.columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 1100 }}
          rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }}
          pagination={{
            current: pageNo, total, pageSize, showTotal: (tot) => t('common.totalCount', { count: tot }),
            showSizeChanger: true, pageSizeOptions: ['20', '50', '100'],
            onChange: (p) => { setPageNo(p); fetchData(p) },
            onShowSizeChange: (_current, size) => { setPageSize(size); setPageNo(1); fetchData(1) },
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
        title={t('common.import') + t('customer.title')}
        expectedHeaders={['客户名称', '简称', '行业', '规模', '区域', '地址', '来源', '级别']}
      />

      {/* Batch Transfer Modal */}
      <Modal title={t('customer.batchTransfer')} open={transferModal} onOk={handleBatchTransfer}
        onCancel={() => setTransferModal(false)} okText={t('common.confirm')}>
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            {t('customer.transferConfirm', { count: selectedRowKeys.length })}
          </div>
          <Form form={transferForm} layout="vertical">
            <Form.Item name="owner_id" label={t('customer.newOwner')} rules={[{ required: true, message: t('common.confirm') }]}>
              <Select showSearch filterOption={false} placeholder={t('customer.searchUser')}
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
