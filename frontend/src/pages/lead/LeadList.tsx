import { useState, useEffect, useRef } from 'react'
import { Button, Input, Space, Select, Modal, Upload, Form, DatePicker, message } from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import { PlusOutlined, SearchOutlined, DownloadOutlined, UploadOutlined, DeleteOutlined } from '@ant-design/icons'
import { downloadFile } from '@/utils/download'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { leadApi } from '@/api/lead'
import type { Lead } from '@/api/types'
import { sourceLabels } from '@/api/types'
import type { ColumnsType } from 'antd/es/table'
import { leadStatusConfig as statusConfig, leadReviewStatusConfig, customerNewnessLabels } from '@/constants/labels'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useDataDict } from '@/hooks/useDataDict'
import { useListView } from '@/hooks/useListView'
import { usePageSize } from '@/hooks/usePageSize'
import ListToolbar from '@/components/list/ListToolbar'
import DepartmentSelect from '@/components/DepartmentSelect'
import dayjs from 'dayjs'
import { t } from '@/locales'
import { formatRegion } from '@/utils/address'

import Icon from '@/components/Icon'
const { RangePicker } = DatePicker

const categoryLabels: Record<string, string> = { self_reported: '自报', distributed: '分发' }
const countryLabels: Record<string, string> = { domestic: '国内', overseas: '国外' }

/** 简道云风格色块标签 */
function JdyTag({ text, tone }: { text: string; tone: string }) {
  const tones: Record<string, string> = {
    red: 'bg-red-500 text-white',
    amber: 'bg-amber-500 text-white',
    orange: 'bg-orange-500 text-white',
    green: 'bg-emerald-500 text-white',
    teal: 'bg-teal-500 text-white',
    blue: 'bg-blue-500 text-white',
    cyan: 'bg-cyan-500 text-white',
    slate: 'bg-slate-400 text-white',
  }
  return (
    <span className={`inline-flex max-w-full truncate px-2 py-0.5 rounded text-[12px] font-medium ${tones[tone] || tones.slate}`}>
      {text}
    </span>
  )
}

function emptyCell() {
  return <span className="text-slate-300">-</span>
}

function fmtDate(v?: string | null, withTime = false) {
  if (!v) return emptyCell()
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return emptyCell()
  return (
    <span className="text-sm text-slate-600 whitespace-nowrap">
      {withTime ? d.toLocaleString('zh-CN') : d.toLocaleDateString('zh-CN')}
    </span>
  )
}

const CATEGORY_TONE: Record<string, string> = { self_reported: 'red', distributed: 'amber' }
const CONFLICT_TONE: Record<string, string> = { 是: 'red', 否: 'amber' }
const COUNTRY_TONE: Record<string, string> = { domestic: 'red', overseas: 'blue' }
const ACTIVITY_TONE: Record<string, string> = {
  技术交流: 'red', 出方案: 'orange', 报价: 'green', 投标: 'teal', 拟建: 'cyan',
}
const NEWNESS_TONE: Record<string, string> = { new: 'red', old: 'amber' }
const CUSTOMER_TYPE_TONES = ['green', 'blue', 'red', 'orange', 'teal', 'cyan', 'amber'] as const

function customerTypeTone(value: string): string {
  let h = 0
  for (let i = 0; i < value.length; i++) h = (h + value.charCodeAt(i) * (i + 1)) % CUSTOMER_TYPE_TONES.length
  return CUSTOMER_TYPE_TONES[h]
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
  const customerType = searchParams.get('customer_type') || undefined
  const category = searchParams.get('category') || undefined
  const countryType = searchParams.get('country_type') || undefined
  const departmentId = searchParams.get('department_id') || undefined
  const industry = searchParams.get('industry') || undefined
  const companyName = searchParams.get('company_name') || ''
  const startDate = searchParams.get('start_date') || undefined
  const endDate = searchParams.get('end_date') || undefined
  const dateField = searchParams.get('date_field') || 'created_at'
  const [pageSize, setPageSize] = usePageSize('leads')
  const customerTypeDict = useDataDict('customer_type')
  const industryDict = useDataDict('industry')

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
  const setCustomerType = (v: string | undefined) => updateParams({ customer_type: v, page: undefined })
  const setCategory = (v: string | undefined) => updateParams({ category: v, page: undefined })
  const setCountryType = (v: string | undefined) => updateParams({ country_type: v, page: undefined })
  const setDepartmentId = (v: string | undefined) => updateParams({ department_id: v, page: undefined })
  const setIndustry = (v: string | undefined) => updateParams({ industry: v, page: undefined })
  const setCompanyName = (v: string) => updateParams({ company_name: v || undefined })
  const setDateRange = (dr: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null) => updateParams({
    start_date: dr?.[0] ? dr[0].format('YYYY-MM-DD') : undefined,
    end_date: dr?.[1] ? dr[1].format('YYYY-MM-DD') : undefined,
    page: undefined,
  })
  // created_at 是默认维度，不写进 URL 以保持链接干净
  const setDateField = (v: string) => updateParams({ date_field: v === 'created_at' ? undefined : v, page: undefined })
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [assignModal, setAssignModal] = useState(false)
  const [assignForm] = Form.useForm()
  const userSelect = useUserSelect()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

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

  const fetchData = async (page = pageNo) => {
    setLoading(true)
    try {
      const res = await leadApi.list({
        pageNo: page, pageSize,
        keyword: keyword || undefined,
        status, source,
        customer_type: customerType,
        category,
        country_type: countryType,
        department_id: departmentId,
        industry,
        company_name: companyName || undefined,
        start_date: startDate,
        end_date: endDate,
        date_field: dateField === 'created_at' ? undefined : dateField,
        ...view.buildParams(),
      })
      setData(res.data.items)
      setTotal(res.data.total)
    } finally {
      setLoading(false)
    }
  }

  // 仅首次加载 / 分页 / 视图变化时拉取；筛选条件的变更不再自动触发搜索，
  // 需点「筛选」按钮或回车（doSearch），与客户管理等列表保持一致。
  useEffect(() => { fetchData(pageNo) }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // 高级筛选/排序/视图变化后回到第 1 页重新拉取（reload 在 state 更新后再触发，避免读到旧值）
  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload])

  const doSearch = () => { updateParams({ page: undefined }); fetchData(1) }

  // 列顺序对齐简道云「申报信息」数据管理（跳过导入专用列）
  const allColumns: ColumnsType<Lead> = [
    {
      title: '项目编号', dataIndex: 'lead_code', key: 'lead_code', width: 168, fixed: 'left',
      render: (v: string, r) => v
        ? <a onClick={() => navigate(`/leads/${r.id}`)} className="font-mono text-sm text-slate-700 hover:text-primary">{v}</a>
        : emptyCell(),
    },
    {
      title: '来源', dataIndex: 'category', key: 'category', width: 80,
      render: (v: string) => v
        ? <JdyTag text={categoryLabels[v] || v} tone={CATEGORY_TONE[v] || 'slate'} />
        : emptyCell(),
    },
    {
      title: '项目名称', dataIndex: 'title', key: 'title', width: 220,
      render: (v: string, r) => (
        <a onClick={() => navigate(`/leads/${r.id}`)} className="text-sm font-semibold text-slate-900 hover:text-primary line-clamp-2">
          {v || '-'}
        </a>
      ),
    },
    {
      title: '公司名称', dataIndex: 'company_name', key: 'company_name', width: 200,
      render: (v: string) => v
        ? <span className="text-sm text-slate-700 line-clamp-2">{v}</span>
        : emptyCell(),
    },
    {
      title: '客户类型', dataIndex: 'customer_type', key: 'customer_type', width: 150,
      render: (v: string) => {
        if (!v) return emptyCell()
        const label = customerTypeDict.options.find(o => o.value === v)?.label || v
        return <JdyTag text={label} tone={customerTypeTone(v)} />
      },
    },
    {
      title: '项目地址', key: 'address', width: 200,
      render: (_, r) => {
        if (r.country_type === 'overseas') {
          const text = [countryLabels.overseas, r.country_name, r.region].filter(Boolean).join(' · ')
          return text ? <span className="text-sm text-slate-600 line-clamp-2">{text}</span> : emptyCell()
        }
        const loc = [formatRegion(r), r.region].filter(Boolean).join(' ')
        return loc ? <span className="text-sm text-slate-600 line-clamp-2">{loc}</span> : emptyCell()
      },
    },
    {
      title: '是否内部冲突', dataIndex: 'has_internal_conflict', key: 'has_internal_conflict', width: 110,
      render: (v: string) => v
        ? <JdyTag text={v} tone={CONFLICT_TONE[v] || 'slate'} />
        : emptyCell(),
    },
    {
      title: '行业', dataIndex: 'industry', key: 'industry', width: 140,
      render: (v: string) => {
        if (!v) return emptyCell()
        const label = industryDict.options.find(o => o.value === v)?.label || v
        return <span className="text-sm text-slate-600 line-clamp-2">{label}</span>
      },
    },
    {
      title: '中标情况', dataIndex: 'bid_result', key: 'bid_result', width: 100,
      render: (v: string) => v ? <span className="text-sm text-slate-600">{v}</span> : emptyCell(),
    },
    {
      title: '原因', dataIndex: 'bid_fail_reason', key: 'bid_fail_reason', width: 140,
      render: (v: string) => v
        ? <span className="text-sm text-slate-600 line-clamp-2" title={v}>{v}</span>
        : emptyCell(),
    },
    {
      title: '备注：请示部门经理的结果', dataIndex: 'conflict_note', key: 'conflict_note', width: 180,
      render: (v: string) => v
        ? <span className="text-sm text-slate-600 line-clamp-2" title={v}>{v}</span>
        : emptyCell(),
    },
    {
      title: '国别', dataIndex: 'country_type', key: 'country_type', width: 80,
      render: (v: string) => v
        ? <JdyTag text={countryLabels[v] || v} tone={COUNTRY_TONE[v] || 'slate'} />
        : emptyCell(),
    },
    {
      title: '委托状态', dataIndex: 'entrust_status', key: 'entrust_status', width: 90,
      render: (v: string) => v
        ? <JdyTag text={v} tone={v === '已开' ? 'red' : 'slate'} />
        : emptyCell(),
    },
    {
      title: '委托开具日期', dataIndex: 'entrust_issued_at', key: 'entrust_issued_at', width: 120,
      render: (v: string) => fmtDate(v),
    },
    {
      title: '委托期限', dataIndex: 'entrust_term', key: 'entrust_term', width: 100,
      render: (v: string) => v ? <span className="text-sm text-slate-600">{v}</span> : emptyCell(),
    },
    {
      title: '填表人', dataIndex: 'created_by_name', key: 'created_by_name', width: 90,
      render: (v: string) => v
        ? <span className="text-sm text-primary">{v}</span>
        : emptyCell(),
    },
    {
      title: '部门', dataIndex: 'department_name', key: 'department_name', width: 160,
      render: (v: string) => v
        ? <span className="text-sm text-slate-600 line-clamp-2">{v}</span>
        : emptyCell(),
    },
    {
      title: '申报人', dataIndex: 'reporter_name', key: 'reporter_name', width: 90,
      render: (v: string) => v
        ? <span className="text-sm text-primary">{v}</span>
        : emptyCell(),
    },
    {
      title: '申报时间', dataIndex: 'reported_at', key: 'reported_at', width: 120,
      render: (v: string) => fmtDate(v),
    },
    {
      title: '项目动态', dataIndex: 'project_activity', key: 'project_activity', width: 100,
      render: (v: string) => v
        ? <JdyTag text={v} tone={ACTIVITY_TONE[v] || 'blue'} />
        : emptyCell(),
    },
    {
      title: '备注1', dataIndex: 'demand_summary', key: 'demand_summary', width: 160,
      render: (v: string) => v
        ? <span className="text-sm text-slate-600 line-clamp-2" title={v}>{v}</span>
        : emptyCell(),
    },
    {
      title: '项目近况', dataIndex: 'project_recent', key: 'project_recent', width: 120, __optIn: true as any,
      render: (v: string) => v ? <span className="text-sm text-slate-600 line-clamp-2">{v}</span> : emptyCell(),
    } as any,
    {
      title: '跟进进度', dataIndex: 'follow_progress', key: 'follow_progress', width: 120, __optIn: true as any,
      render: (v: string) => v ? <span className="text-sm text-slate-600 line-clamp-2">{v}</span> : emptyCell(),
    } as any,
    {
      title: '实地拜访情况', dataIndex: 'site_visit', key: 'site_visit', width: 120, __optIn: true as any,
      render: (v: string) => v ? <span className="text-sm text-slate-600 line-clamp-2">{v}</span> : emptyCell(),
    } as any,
    {
      title: '项目状态', dataIndex: 'report_project_status', key: 'report_project_status', width: 100, __optIn: true as any,
      render: (v: string) => v ? <span className="text-sm text-slate-600">{v}</span> : emptyCell(),
    } as any,
    {
      title: '客户类型（新/老）', dataIndex: 'customer_newness', key: 'customer_newness', width: 120,
      render: (v: string) => v
        ? <JdyTag text={customerNewnessLabels[v] || v} tone={NEWNESS_TONE[v] || 'slate'} />
        : emptyCell(),
    },
    {
      title: '项目最终状态', dataIndex: 'review_status', key: 'review_status', width: 110,
      render: (v: string) => {
        const rcfg = leadReviewStatusConfig[v || 'pending'] || leadReviewStatusConfig.pending
        const tone =
          v === 'approved' ? 'amber'
            : v === 'rejected' ? 'teal'
              : v === 'attacked' ? 'orange'
                : 'amber'
        return <JdyTag text={rcfg.label} tone={tone} />
      },
    },
    {
      title: '回退原因', dataIndex: 'reject_reason', key: 'reject_reason', width: 140,
      render: (v: string) => v
        ? <span className="text-sm text-slate-600 line-clamp-2" title={v}>{v}</span>
        : emptyCell(),
    },
    {
      title: '备注2', dataIndex: 'assess_remark', key: 'assess_remark', width: 140,
      render: (v: string) => v
        ? <span className="text-sm text-slate-600 line-clamp-2" title={v}>{v}</span>
        : emptyCell(),
    },
    {
      title: '提交时间', dataIndex: 'created_at', key: 'created_at', width: 160,
      render: (v: string) => fmtDate(v, true),
    },
    {
      title: '更新时间', dataIndex: 'updated_at', key: 'updated_at', width: 160,
      render: (v: string) => fmtDate(v, true),
    },
    // CRM 扩展列：默认隐藏，列配置可调出
    ...([
      { title: t('lead.score'), dataIndex: 'score', width: 100,
        render: (v: number) => <span className="text-sm font-bold tabular-nums text-slate-700">{v ?? 0}</span> },
      { title: t('lead.status'), dataIndex: 'status', width: 100,
        render: (v: string) => {
          const cfg = statusConfig[v] || statusConfig.new
          return (
            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[12px] font-bold uppercase border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
              <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
              {cfg.label}
            </span>
          )
        } },
      { title: t('common.owner'), dataIndex: 'owner_name', width: 90 },
      { title: t('lead.contact'), dataIndex: 'contact_name', width: 90 },
      { title: t('lead.source'), dataIndex: 'source', width: 90,
        render: (v: string) => v ? <span className="text-sm text-slate-600">{sourceLabels[v] || v}</span> : emptyCell() },
      { title: '业务日期', dataIndex: 'biz_date', width: 110 },
      { title: '联系电话', dataIndex: 'contact_phone', width: 130 },
      { title: '联系邮箱', dataIndex: 'contact_email', width: 180 },
    ] as ColumnsType<Lead>).map((c) => ({
      ...c,
      __optIn: true,
      render: (c as any).render ?? ((v: unknown) =>
        v ? <span className="text-sm text-slate-600">{String(v)}</span> : emptyCell()),
    })),
    { title: '', key: 'actions', width: 150, fixed: 'right',
      render: (_, record) => (
        <Space size={0}>
          <a onClick={() => navigate(`/leads/${record.id}`)} className="text-primary text-sm font-bold uppercase tracking-widest px-2">{t('common.detail')}</a>
          {record.status !== 'qualified' && record.status !== 'discarded' && (
            <a onClick={() => navigate(`/leads/${record.id}/edit`)} className="text-slate-500 text-sm font-bold uppercase tracking-widest px-2 hover:text-primary">{t('common.edit')}</a>
          )}
          <a className="text-sm font-bold uppercase tracking-widest px-2 text-rose-500 hover:text-rose-600" onClick={() => {
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

  // pageKey 换新版本，避免旧列配置覆盖简道云默认列
  const view = useListView<Lead>('lead', allColumns, { pageKey: 'leads_jdy_v1', entityType: 'lead' })

  return (
    <div>
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 shrink-0">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">{t('lead.title')}</h1>
          <p className="text-sm text-slate-500 mt-0.5">{t('lead.subtitle')}</p>
        </div>
        <Space wrap>
          <Button icon={<DownloadOutlined />} onClick={() => downloadFile('/api/v1/leads/import/template', 'lead_import_template.xlsx')}>
            {t('common.template')}
          </Button>
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
          <Button icon={<DownloadOutlined />} onClick={() => {
            const qs = new URLSearchParams()
            if (keyword) qs.set('keyword', keyword)
            if (status) qs.set('status', status)
            if (companyName) qs.set('company_name', companyName)
            if (startDate) qs.set('start_date', startDate)
            if (endDate) qs.set('end_date', endDate)
            if (dateField !== 'created_at') qs.set('date_field', dateField)
            const q = qs.toString()
            downloadFile(`/api/v1/leads/export/excel${q ? `?${q}` : ''}`, 'leads.xlsx')
          }}>{t('common.export')}</Button>
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
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-3 mb-4 flex items-center justify-between shrink-0">
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
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4 shrink-0">
        <div className="flex gap-3 flex-wrap items-stretch sm:items-center flex-col sm:flex-row">
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
          <Input
            placeholder="公司名称"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            onPressEnter={doSearch}
            allowClear
            style={{ width: 180 }}
          />
          <Space.Compact>
            <Select
              value={dateField}
              onChange={setDateField}
              style={{ width: 110 }}
              options={[
                { value: 'created_at', label: '创建时间' },
                { value: 'biz_date', label: '业务日期' },
              ]}
            />
            <RangePicker
              value={startDate && endDate ? [dayjs(startDate), dayjs(endDate)] : undefined}
              onChange={(dr) => setDateRange(dr as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null)}
              placeholder={['起始', '结束']}
              style={{ width: 230 }}
            />
          </Space.Compact>
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
          <Select
            placeholder="客户类型"
            allowClear
            style={{ width: 180 }}
            value={customerType}
            onChange={setCustomerType}
            options={customerTypeDict.options}
            loading={customerTypeDict.loading}
          />
          <Select
            placeholder="行业"
            allowClear
            showSearch optionFilterProp="label"
            style={{ width: 180 }}
            value={industry}
            onChange={setIndustry}
            options={industryDict.options}
            loading={industryDict.loading}
          />
          <Select
            placeholder="类别"
            allowClear
            style={{ width: 110 }}
            value={category}
            onChange={setCategory}
            options={[{ label: '自报', value: 'self_reported' }, { label: '分发', value: 'distributed' }]}
          />
          <Select
            placeholder="国别"
            allowClear
            style={{ width: 110 }}
            value={countryType}
            onChange={setCountryType}
            options={[{ label: '国内', value: 'domestic' }, { label: '国外', value: 'overseas' }]}
          />
          <div style={{ width: 180 }}>
            <DepartmentSelect value={departmentId} onChange={setDepartmentId} placeholder="部门" />
          </div>
          <Button onClick={doSearch}>
            <Icon name="filter_list" className="text-sm mr-1" />
            {t('common.filter')}
          </Button>
          <ListToolbar resource="lead" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <FillHeightTable
          rowKey="id"
          columns={view.columns}
          dataSource={data}
          loading={loading}
          scroll={{ x: 1050 }}
          rowSelection={{ selectedRowKeys, onChange: setSelectedRowKeys }}
          pagination={{
            current: pageNo, total, pageSize, showTotal: (total) => t('common.totalCount', { count: total }),
            showSizeChanger: true, pageSizeOptions: ['20', '50', '100'],
            onChange: (p) => { setPageNo(p); fetchData(p) },
            onShowSizeChange: (_current, size) => { setPageSize(size); setPageNo(1); fetchData(1) },
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
        <p className="text-sm text-slate-400">{t('lead.assignTo', { count: selectedRowKeys.length })}</p>
      </Modal>
    </div>
  )
}
