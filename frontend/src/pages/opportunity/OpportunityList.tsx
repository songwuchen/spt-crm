import { useState, useEffect } from 'react'
import { Table, Button, Input, Select, Space, Modal, Form, Progress, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'
import { t } from '@/locales'
import ImportModal from '@/components/ImportModal'
import { downloadFile } from '@/utils/download'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import type { OpportunityProject, Customer } from '@/api/types'
import { stageLabels, stageColors, riskLabels, riskColors } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { opportunityStatusMap as statusMap } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useColumnConfig } from '@/hooks/useColumnConfig'
import { usePageSize } from '@/hooks/usePageSize'
import SavedViewSelect from '@/components/SavedViewSelect'
import ColumnConfigDropdown from '@/components/ColumnConfigDropdown'

const STAGES = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6']

export default function OpportunityList() {
  usePageTitle(t('opportunity.title'))
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<OpportunityProject[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(Number(searchParams.get('page')) || 1)
  const [keyword, setKeyword] = useState(searchParams.get('q') || '')
  const [stageCode, setStageCode] = useState<string | undefined>(searchParams.get('stage') || undefined)
  const [status, setStatus] = useState<string | undefined>(searchParams.get('status') || undefined)
  const [customerMap, setCustomerMap] = useState<Record<string, string>>({})
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [batchStageModal, setBatchStageModal] = useState(false)
  const [batchStage, setBatchStage] = useState<string>('S1')
  const [importModal, setImportModal] = useState(false)
  const [batchTransferModal, setBatchTransferModal] = useState(false)
  const [transferForm] = Form.useForm()
  const userSelect = useUserSelect()
  const [pageSize, setPageSize] = usePageSize('opportunities')

  const handleBatchStageChange = async () => {
    const results = await Promise.allSettled(
      selectedRowKeys.map((id) => projectApi.update(id as string, { stage_code: batchStage }))
    )
    const ok = results.filter(r => r.status === 'fulfilled').length
    message.success(t('opportunity.batchStageDone', { count: ok }))
    setBatchStageModal(false)
    setSelectedRowKeys([])
    fetchData()
  }

  const handleBatchTransfer = async () => {
    const values = await transferForm.validateFields()
    const ownerName = userSelect.options.find(o => o.value === values.owner_id)?.label || ''
    const results = await Promise.allSettled(
      selectedRowKeys.map((id) => projectApi.update(id as string, { owner_id: values.owner_id, owner_name: ownerName }))
    )
    const ok = results.filter(r => r.status === 'fulfilled').length
    message.success(t('opportunity.batchTransferDone', { count: ok }))
    setBatchTransferModal(false)
    transferForm.resetFields()
    setSelectedRowKeys([])
    fetchData()
  }

  const handleBatchDelete = () => {
    Modal.confirm({
      title: t('common.batchDelete'),
      content: t('common.batchDeleteConfirm', { count: selectedRowKeys.length }),
      okType: 'danger',
      onOk: async () => {
        await Promise.all(selectedRowKeys.map((id) => projectApi.delete(id as string)))
        message.success(t('common.batchDeleteDone', { count: selectedRowKeys.length }))
        setSelectedRowKeys([])
        fetchData()
      },
    })
  }

  const fetchData = async (page = pageNo, kw = keyword, sc = stageCode, st = status) => {
    setLoading(true)
    try {
      const res = await projectApi.list({
        pageNo: page, pageSize,
        keyword: kw || undefined, stage_code: sc, status: st,
      })
      setData(res.data.items)
      setTotal(res.data.total)

      // Fetch customer names for display
      const ids = [...new Set(res.data.items.map((p) => p.customer_id).filter(Boolean))] as string[]
      if (ids.length > 0) {
        const custRes = await customerApi.list({ pageNo: 1, pageSize: 100 })
        const map: Record<string, string> = {}
        custRes.data.items.forEach((c: Customer) => { map[c.id] = c.name })
        setCustomerMap(map)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData() }, [])

  const doSearch = () => {
    setPageNo(1)
    const params: Record<string, string> = {}
    if (keyword) params.q = keyword
    if (stageCode) params.stage = stageCode
    if (status) params.status = status
    setSearchParams(params, { replace: true })
    fetchData(1, keyword, stageCode, status)
  }

  const allColumns: ColumnsType<OpportunityProject> = [
    { title: t('opportunity.name'), key: 'name', width: 260,
      render: (_, r) => (
        <div>
          <a onClick={() => navigate(`/opportunities/${r.id}`)} className="text-sm font-bold text-slate-900 hover:text-primary">
            {r.name}
          </a>
          <div className="text-[11px] text-slate-400 font-mono">{r.project_code}</div>
        </div>
      ),
    },
    { title: t('opportunity.customer'), key: 'customer', width: 140,
      render: (_, r) => r.customer_id ? (
        <span className="text-sm text-slate-700">{customerMap[r.customer_id] || '-'}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: t('opportunity.stage'), key: 'stage', width: 110,
      render: (_, r) => (
        <span className={`inline-flex items-center px-2.5 py-1 rounded text-[10px] font-black uppercase border ${stageColors[r.stage_code] || stageColors.S1}`}>
          {r.stage_code} {stageLabels[r.stage_code]}
        </span>
      ),
    },
    { title: t('opportunity.amount'), key: 'amount', width: 120, align: 'right',
      render: (_, r) => r.amount_expect != null ? (
        <span className="text-sm font-bold text-slate-800">{Number(r.amount_expect).toLocaleString('zh-CN', { style: 'currency', currency: 'CNY', minimumFractionDigits: 0 })}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: t('opportunity.probability'), key: 'probability', width: 110, responsive: ['lg'],
      render: (_, r) => r.probability != null ? (
        <div className="flex items-center gap-2">
          <Progress percent={r.probability} size="small" showInfo={false} strokeColor="#6366f1" className="flex-1 m-0" />
          <span className="text-xs font-bold text-slate-600 w-8 text-right">{r.probability}%</span>
        </div>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: t('opportunity.risk'), key: 'risk', width: 70, responsive: ['xl'],
      render: (_, r) => r.risk_level ? (
        <span className={`inline-flex px-2 py-0.5 rounded text-[10px] font-bold border ${riskColors[r.risk_level] || ''}`}>
          {riskLabels[r.risk_level]}
        </span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: '状态', key: 'status', width: 90,
      render: (_, r) => {
        const s = statusMap[r.status] || statusMap.active
        return (
          <div className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${s.dot}`} />
            <span className="text-xs font-medium text-slate-600">{s.label}</span>
          </div>
        )
      },
    },
    { title: t('opportunity.owner'), dataIndex: 'owner_name', width: 90,
      render: (v) => v || <span className="text-slate-300">-</span> },
    { title: '', key: 'actions', width: 150, fixed: 'right',
      render: (_, r) => (
        <Space size={0}>
          <a onClick={() => navigate(`/opportunities/${r.id}`)} className="text-primary text-xs font-bold uppercase tracking-widest px-2">{t('common.detail')}</a>
          <a onClick={() => navigate(`/opportunities/${r.id}/edit`)} className="text-slate-500 text-xs font-bold uppercase tracking-widest px-2 hover:text-primary">{t('common.edit')}</a>
          <a className="text-xs font-bold uppercase tracking-widest px-2 text-rose-500 hover:text-rose-600" onClick={() => {
            Modal.confirm({
              title: t('common.confirmDelete'), content: t('opportunity.deleteConfirm', { name: r.name }), okType: 'danger',
              onOk: async () => { await projectApi.delete(r.id); message.success(t('common.deleted')); fetchData() },
            })
          }}>{t('common.delete')}</a>
        </Space>
      ),
    },
  ]

  const { visibleColumns, hiddenKeys, setColumnConfig, allColumnKeys } = useColumnConfig('opportunities', allColumns)

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900">{t('opportunity.title')}</h1>
          <p className="text-sm text-slate-500 mt-0.5">{t('opportunity.subtitle')}</p>
        </div>
        <div className="flex gap-2 flex-wrap">
          {selectedRowKeys.length > 0 && (
            <>
              <Button onClick={() => setBatchStageModal(true)}>{t('opportunity.batchStageChange')}</Button>
              <Button onClick={() => { transferForm.resetFields(); setBatchTransferModal(true) }}>{t('opportunity.batchTransfer')}</Button>
              <Button danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>
                {t('opportunity.deleteSelected', { count: selectedRowKeys.length })}
              </Button>
            </>
          )}
          <Button icon={<UploadOutlined />} onClick={() => setImportModal(true)}>{t('common.import')}</Button>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/projects/export/excel', 'projects.xlsx')}>{t('common.export')}</Button>
          <button onClick={() => navigate('/opportunities/kanban')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 bg-white text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors">
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>view_kanban</span>
            {t('common.kanban')}
          </button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/opportunities/new')}
            className="shadow-lg shadow-primary/20 font-bold">
            {t('opportunity.createOpportunity')}
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input placeholder={t('opportunity.searchPlaceholder')} prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword} onChange={(e) => setKeyword(e.target.value)} onPressEnter={doSearch}
            allowClear style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }} />
          <Select placeholder={t('opportunity.stage')} allowClear style={{ width: 130 }} value={stageCode}
            onChange={(v) => { setStageCode(v); setPageNo(1); fetchData(1, keyword, v, status) }}
            options={STAGES.map((s) => ({ label: `${s} ${stageLabels[s]}`, value: s }))} />
          <Select placeholder="状态" allowClear style={{ width: 110 }} value={status}
            onChange={(v) => { setStatus(v); setPageNo(1); fetchData(1, keyword, stageCode, v) }}
            options={Object.entries(statusMap).map(([k, v]) => ({ label: v.label, value: k }))} />
          <Button onClick={doSearch}>
            <span className="material-symbols-outlined text-sm mr-1">filter_list</span>
            {t('common.filter')}
          </Button>
          <ColumnConfigDropdown allColumnKeys={allColumnKeys} hiddenKeys={hiddenKeys} onChange={setColumnConfig} />
          <SavedViewSelect
            page="opportunities"
            currentFilters={{ keyword, stage_code: stageCode, status }}
            onApply={(f) => {
              setKeyword(f.keyword || ''); setStageCode(f.stage_code || undefined); setStatus(f.status || undefined)
              fetchData(1, f.keyword || '', f.stage_code, f.status)
            }}
          />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Table rowKey="id" columns={visibleColumns} dataSource={data} loading={loading} scroll={{ x: 1200 }}
          rowSelection={{ selectedRowKeys, onChange: (keys) => setSelectedRowKeys(keys) }}
          pagination={{
            current: pageNo, total, pageSize, showTotal: (n) => t('common.totalCount', { count: n }),
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
        previewUrl="/api/v1/projects/import/preview"
        importUrl="/api/v1/projects/import/excel"
        title={t('opportunity.importOpportunity')}
        expectedHeaders={['项目名称', '预计金额', '概率(%)', '预计关闭日', '风险等级', '备注']}
      />

      {/* Batch Stage Modal */}
      <Modal title={t('opportunity.batchStageChange')} open={batchStageModal} onOk={handleBatchStageChange}
        onCancel={() => setBatchStageModal(false)} okText={t('opportunity.confirmChange')}>
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            {t('opportunity.batchStageMsg', { count: selectedRowKeys.length })}
          </div>
          <Select className="w-full" value={batchStage} onChange={setBatchStage}
            options={STAGES.map((s) => ({ label: `${s} ${stageLabels[s]}`, value: s }))} />
        </div>
      </Modal>

      {/* Batch Transfer Modal */}
      <Modal title={t('opportunity.batchTransfer')} open={batchTransferModal} onOk={handleBatchTransfer}
        onCancel={() => setBatchTransferModal(false)} okText={t('opportunity.confirmTransfer')}>
        <div className="py-2">
          <div className="mb-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            {t('opportunity.batchTransferMsg', { count: selectedRowKeys.length })}
          </div>
          <Form form={transferForm} layout="vertical">
            <Form.Item name="owner_id" label={t('common.owner')} rules={[{ required: true }]}>
              <Select showSearch filterOption={false} placeholder="搜索用户"
                loading={userSelect.loading} options={userSelect.options}
                onSearch={userSelect.onSearch} onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            </Form.Item>
          </Form>
        </div>
      </Modal>
    </div>
  )
}
