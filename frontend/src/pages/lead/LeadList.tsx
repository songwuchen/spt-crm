import { useState, useEffect } from 'react'
import { Table, Button, Input, Space, Select, Modal, Upload, Form, DatePicker, message } from 'antd'
import { PlusOutlined, SearchOutlined, DownloadOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { leadApi } from '@/api/lead'
import type { Lead } from '@/api/types'
import { sourceLabels } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { leadStatusConfig as statusConfig } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useColumnConfig } from '@/hooks/useColumnConfig'
import SavedViewSelect from '@/components/SavedViewSelect'
import ColumnConfigDropdown from '@/components/ColumnConfigDropdown'
import { t } from '@/locales'

function ScoreBar({ score }: { score: number }) {
  const getColor = (s: number) => {
    if (s >= 80) return 'bg-emerald-500'
    if (s >= 60) return 'bg-primary'
    if (s >= 40) return 'bg-amber-500'
    return 'bg-slate-300'
  }
  const getLabel = (s: number) => {
    if (s >= 80) return 'text-emerald-600'
    if (s >= 60) return 'text-primary'
    if (s >= 40) return 'text-amber-600'
    return 'text-slate-400'
  }
  return (
    <div className="flex items-center gap-2.5 min-w-[100px]">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${getColor(score)}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`text-xs font-black tabular-nums ${getLabel(score)}`}>{score}</span>
    </div>
  )
}

export default function LeadList() {
  usePageTitle(t('lead.title'))
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [data, setData] = useState<Lead[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const pageNo = parseInt(searchParams.get('page') || '1', 10) || 1
  const keyword = searchParams.get('keyword') || ''
  const status = searchParams.get('status') || undefined
  const source = searchParams.get('source') || undefined

  const updateParams = (updates: Record<string, string | undefined>) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      for (const [k, v] of Object.entries(updates)) {
        if (v) next.set(k, v)
        else next.delete(k)
      }
      return next
    }, { replace: true })
  }
  const setPageNo = (p: number) => updateParams({ page: p > 1 ? String(p) : undefined })
  const setKeyword = (v: string) => updateParams({ keyword: v || undefined })
  const setStatus = (v: string | undefined) => updateParams({ status: v, page: undefined })
  const setSource = (v: string | undefined) => updateParams({ source: v, page: undefined })
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [assignModal, setAssignModal] = useState(false)
  const [assignForm] = Form.useForm()
  const userSelect = useUserSelect()

  const handleBatchAssign = async () => {
    const values = await assignForm.validateFields()
    const ownerName = userSelect.options.find(o => o.value === values.owner_id)?.label || ''
    try {
      const res = await leadApi.batchAssign(selectedRowKeys as string[], values.owner_id, ownerName)
      message.success(t('lead.batchAssignDone', { count: (res as any).data?.updated || selectedRowKeys.length }))
      setAssignModal(false)
      assignForm.resetFields()
      setSelectedRowKeys([])
      fetchData()
    } catch { message.error(t('lead.batchAssignFailed')) }
  }

  const handleBatchDelete = () => {
    if (!selectedRowKeys.length) return
    Modal.confirm({
      title: t('common.batchDelete'), content: t('common.batchDeleteConfirm', { count: selectedRowKeys.length }), okType: 'danger',
      onOk: async () => {
        await Promise.all(selectedRowKeys.map((id) => leadApi.delete(id as string)))
        message.success(t('common.batchDeleteDone', { count: selectedRowKeys.length }))
        setSelectedRowKeys([])
        fetchData()
      },
    })
  }

  const handleBatchConvert = () => {
    if (!selectedRowKeys.length) return
    Modal.confirm({
      title: t('lead.batchConvert'), content: t('lead.batchConvertConfirm', { count: selectedRowKeys.length }),
      okText: t('common.confirm'),
      onOk: async () => {
        const results = await Promise.allSettled(
          selectedRowKeys.map((id) => leadApi.qualify(id as string))
        )
        const ok = results.filter(r => r.status === 'fulfilled').length
        const fail = results.filter(r => r.status === 'rejected').length
        if (fail > 0) {
          message.warning(t('lead.batchConvertPartial', { ok, fail }))
        } else {
          message.success(t('lead.batchConvertDone', { count: ok }))
        }
        setSelectedRowKeys([])
        fetchData()
      },
    })
  }

  const fetchData = async (page = pageNo, kw = keyword, st = status, src = source) => {
    setLoading(true)
    try {
      const res = await leadApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st, source: src })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { fetchData(pageNo, keyword, status, source) }, [searchParams])

  const doSearch = () => { updateParams({ page: undefined }) }

  const allColumns: ColumnsType<Lead> = [
    { title: t('lead.name'), key: 'title', width: 260,
      render: (_, record) => (
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-slate-100 border border-slate-200 flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-sm text-slate-400">trending_up</span>
          </div>
          <div>
            <a onClick={() => navigate(`/leads/${record.id}`)} className="text-sm font-bold text-slate-900 hover:text-primary">
              {record.title}
            </a>
            <div className="text-[11px] text-slate-400">
              {record.lead_code && <span className="font-mono mr-2">{record.lead_code}</span>}
              {record.company_name}
            </div>
          </div>
        </div>
      ),
    },
    { title: t('lead.contact'), dataIndex: 'contact_name', width: 100,
      render: (v) => v ? (
        <span className="text-sm text-slate-700">{v}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: t('lead.source'), dataIndex: 'source', width: 90, responsive: ['lg'],
      render: (v: string) => v ? (
        <span className="text-xs text-slate-600">{sourceLabels[v] || v}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: t('lead.score'), dataIndex: 'score', width: 140,
      render: (v: number) => <ScoreBar score={v ?? 0} />,
    },
    { title: t('lead.status'), dataIndex: 'status', width: 100,
      render: (v: string) => {
        const cfg = statusConfig[v] || statusConfig.new
        return (
          <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[10px] font-bold uppercase border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
            {cfg.label}
          </span>
        )
      },
    },
    { title: t('common.owner'), dataIndex: 'owner_name', width: 90,
      render: (v) => v ? (
        <span className="text-sm text-slate-600">{v}</span>
      ) : <span className="text-slate-300">-</span>,
    },
    { title: t('common.createdAt'), dataIndex: 'created_at', width: 110, responsive: ['xl'],
      render: (v) => v ? <span className="text-xs text-slate-500">{new Date(v).toLocaleDateString('zh-CN')}</span> : '-',
    },
    { title: '', key: 'actions', width: 160, fixed: 'right',
      render: (_, record) => (
        <Space size={0}>
          <a onClick={() => navigate(`/leads/${record.id}`)} className="text-primary text-xs font-bold uppercase tracking-widest px-2">{t('common.detail')}</a>
          {record.status !== 'qualified' && record.status !== 'discarded' && (
            <a onClick={() => navigate(`/leads/${record.id}/edit`)} className="text-slate-500 text-xs font-bold uppercase tracking-widest px-2 hover:text-primary">{t('common.edit')}</a>
          )}
          <a className="text-xs font-bold uppercase tracking-widest px-2 text-rose-500 hover:text-rose-600" onClick={() => {
            Modal.confirm({
              title: t('common.confirmDelete'), content: t('lead.deleteConfirm', { name: record.title }),
              okType: 'danger',
              onOk: async () => {
                await leadApi.delete(record.id)
                message.success(t('lead.deleted'))
                fetchData()
              },
            })
          }}>{t('common.delete')}</a>
        </Space>
      ),
    },
  ]

  const { visibleColumns, hiddenKeys, setColumnConfig, allColumnKeys } = useColumnConfig('leads', allColumns)

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{t('lead.title')}</h1>
          <p className="text-sm text-slate-500 mt-0.5">{t('lead.subtitle')}</p>
        </div>
        <Space>
          <Upload accept=".xlsx,.xls" showUploadList={false} customRequest={async ({ file }) => {
            const formData = new FormData()
            formData.append('file', file as File)
            try {
              const token = localStorage.getItem('access_token')
              const res = await fetch('/api/v1/leads/import/excel', {
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
            <Button icon={<UploadOutlined />}>{t('common.import')}</Button>
          </Upload>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/leads/export/excel', 'leads.xlsx')}>{t('common.export')}</Button>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => navigate('/leads/new')}
            className="shadow-lg shadow-primary/20 font-bold"
          >
            {t('lead.createLead')}
          </Button>
        </Space>
      </div>

      {selectedRowKeys.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-700">{t('common.selected', { count: selectedRowKeys.length })}</span>
          <Space>
            <Button size="small" onClick={() => { assignForm.resetFields(); setAssignModal(true) }}>{t('lead.batchAssign')}</Button>
            <Button size="small" onClick={handleBatchConvert}>{t('lead.batchConvert')}</Button>
            <Button size="small" danger icon={<DeleteOutlined />} onClick={handleBatchDelete}>{t('common.batchDelete')}</Button>
            <Button size="small" onClick={() => setSelectedRowKeys([])}>{t('common.cancelSelect')}</Button>
          </Space>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4">
        <div className="flex gap-3 flex-wrap items-center">
          <Input
            placeholder={t('lead.searchPlaceholder')}
            prefix={<SearchOutlined className="text-slate-400" />}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 220, background: '#f1f5f9', borderColor: 'transparent' }}
            className="rounded-lg"
          />
          <Select
            placeholder={t('lead.status')}
            allowClear
            style={{ width: 140 }}
            value={status}
            onChange={(v) => setStatus(v)}
            options={Object.entries(statusConfig).map(([k, v]) => ({ label: v.label, value: k }))}
          />
          <Select
            placeholder={t('lead.source')}
            allowClear
            style={{ width: 140 }}
            value={source}
            onChange={(v) => setSource(v)}
            options={Object.entries(sourceLabels).map(([k, v]) => ({ label: v, value: k }))}
          />
          <Button onClick={doSearch}>
            <span className="material-symbols-outlined text-sm mr-1">filter_list</span>
            {t('common.filter')}
          </Button>
          <ColumnConfigDropdown allColumnKeys={allColumnKeys} hiddenKeys={hiddenKeys} onChange={setColumnConfig} />
          <SavedViewSelect
            page="leads"
            currentFilters={{ keyword, status, source }}
            onApply={(f) => {
              updateParams({ keyword: f.keyword || undefined, status: f.status || undefined, source: f.source || undefined, page: undefined })
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
          scroll={{ x: 1050 }}
          rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (total) => t('common.totalCount', { count: total }),
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          className="[&_.ant-table-row]:hover:bg-slate-50/80 [&_.ant-table-row]:transition-colors"
        />
      </div>

      <Modal title={t('lead.batchAssign')} open={assignModal} onOk={handleBatchAssign}
        onCancel={() => setAssignModal(false)} okText={t('common.confirm')}>
        <Form form={assignForm} layout="vertical" className="py-2">
          <Form.Item label={t('lead.batchAssignTo')} name="owner_id" rules={[{ required: true, message: t('lead.batchAssignTo') }]}>
            <Select showSearch filterOption={false} placeholder={t('common.searchPlaceholder')}
              loading={userSelect.loading} options={userSelect.options}
              onSearch={userSelect.onSearch} onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
          </Form.Item>
        </Form>
        <p className="text-xs text-slate-400">{t('lead.assignTo', { count: selectedRowKeys.length })}</p>
      </Modal>
    </div>
  )
}
