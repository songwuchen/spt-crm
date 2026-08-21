/**
 * 技术协议评审列表：对齐方案管理（新增→/fill；查看/编辑→弹窗）。
 */
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import {
  Button, Input, Space, Tag, message, Modal, Select, Popconfirm, Spin, Form, Typography,
} from 'antd'
import {
  PlusOutlined, SearchOutlined, EditOutlined, DeleteOutlined, SendOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import FillHeightTable from '@/components/list/FillHeightTable'
import ListToolbar from '@/components/list/ListToolbar'
import ModalFullscreenTitle, { modalFullscreenProps } from '@/components/ModalFullscreenTitle'
import RecordPrevNextNav from '@/components/RecordPrevNextNav'
import { rememberSiblingNav } from '@/hooks/useSiblingRecordNav'
import { useListView } from '@/hooks/useListView'
import { techAgreementReviewApi, type TechAgreementReview } from '@/api/techAgreementReview'
import { customerApi } from '@/api/customer'
import type { Customer } from '@/api/types'
import { industryLabels } from '@/api/types'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfInstanceDetail } from '@/types/lowcode'
import {
  TECH_AGREEMENT_LIST_COLUMNS,
  TECH_AGREEMENT_STATUS,
  type TarListColumnDef,
} from '@/constants/techAgreementReview'
import TechAgreementFields from '@/components/TechAgreementFields'
import AttachmentPanel from '@/components/AttachmentPanel'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import WfFlowDynamics from '@/components/lowcode/WfFlowDynamics'
import {
  tarBuildPayload, tarRowToFormValues, canEditTarStatus,
} from '@/pages/techAgreementReview/tarFormUtils'
import { loadTechAgreementWf } from '@/pages/techAgreementReview/TechAgreementReviewViewBody'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCustomerSelect } from '@/hooks/useSelectOptions'
import { formatRegion } from '@/utils/address'

const { Text } = Typography
const FILL_PATH = '/tech-agreement-reviews/fill'

const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  TECH_AGREEMENT_STATUS.map((s) => [s.value, s.label]),
)
const STATUS_COLOR: Record<string, string> = {
  draft: 'default', submitted: 'processing', approved: 'success', rejected: 'error',
}

function dash(v: unknown): string {
  if (v == null || v === '') return '—'
  return String(v)
}

function fmtDate(v: string | null | undefined): string {
  if (!v) return '—'
  try {
    return new Date(v).toLocaleString('zh-CN')
  } catch {
    return String(v)
  }
}

function optionTagColor(lab: string): string {
  if (lab === '是' || lab === '有' || lab === '已核价') return 'blue'
  if (lab === '否' || lab === '无' || lab === '未核价') return 'default'
  return 'geekblue'
}

function readColValue(row: TechAgreementReview, col: TarListColumnDef): unknown {
  if (col.kind === 'person' || col.kind === 'dept') {
    return (row as unknown as Record<string, unknown>)[col.nameKey || col.key]
  }
  if (col.source === 'form') {
    return (row.form_json || {})[col.key]
  }
  return (row as unknown as Record<string, unknown>)[col.key]
}

function formatCustomerIndustry(c: Customer): string {
  const levels = [c.industry_l1, c.industry_l2, c.industry_l3].filter(Boolean)
  if (levels.length) return levels.join('/')
  const raw = (c.industry || '').trim()
  if (!raw) return ''
  return industryLabels[raw] || raw
}

function formatCustomerAddress(c: Customer): string {
  const region = formatRegion(c, '')
  const detail = (c.address || '').trim()
  if (region && detail) return `${region}${detail}`
  return region || detail
}

type ViewRec = {
  row: TechAgreementReview
  readonly: boolean
}

export default function TechAgreementReviewList() {
  usePageTitle('技术协议评审')
  const navigate = useNavigate()
  const hasPermission = useAuthStore((s) => s.hasPermission)
  const canCreate = hasPermission('tech_agreement_review:create')
  const canEdit = hasPermission('tech_agreement_review:edit')
  const canDelete = hasPermission('tech_agreement_review:delete')

  const [data, setData] = useState<TechAgreementReview[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20)
  const [keyword, setKeyword] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const kwRef = useRef(keyword)
  kwRef.current = keyword

  const [viewRec, setViewRec] = useState<ViewRec | null>(null)
  const [viewLoading, setViewLoading] = useState(false)
  const [modalFullscreen, setModalFullscreen] = useState(false)
  const [wfDetail, setWfDetail] = useState<WfInstanceDetail | null>(null)
  const [wfCommenting, setWfCommenting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [fillingCustomer, setFillingCustomer] = useState(false)
  const [form] = Form.useForm()
  const customerSelect = useCustomerSelect()

  const openView = async (id: string, startEdit = false) => {
    rememberSiblingNav('tech_agreement_review', {
      ids: data.map((d) => d.id),
      total,
      pageNo: page,
      pageSize,
      listQuery: {
        keyword: kwRef.current || undefined,
        status,
      },
    })
    setViewLoading(true)
    setViewRec(null)
    setWfDetail(null)
    try {
      const res = await techAgreementReviewApi.get(id)
      const row = res.data
      const editable = canEdit && canEditTarStatus(row.status)
      setViewRec({ row, readonly: !(startEdit && editable) })
      form.setFieldsValue(tarRowToFormValues(row))
      if (row.customer_id && row.company_name) {
        customerSelect.setInitialOption({ label: row.company_name, value: row.customer_id })
      }
      setWfDetail(await loadTechAgreementWf(row.id))
    } catch {
      message.error('加载失败')
      setViewRec(null)
    } finally {
      setViewLoading(false)
    }
  }

  const closeView = () => {
    setViewRec(null)
    setWfDetail(null)
    setModalFullscreen(false)
    form.resetFields()
  }

  const refreshView = async () => {
    if (!viewRec) return
    const res = await techAgreementReviewApi.get(viewRec.row.id)
    const keepEdit = !viewRec.readonly && canEditTarStatus(res.data.status)
    setViewRec({ row: res.data, readonly: !keepEdit })
    form.setFieldsValue(tarRowToFormValues(res.data))
    setWfDetail(await loadTechAgreementWf(res.data.id))
    setReload((n) => n + 1)
  }

  const handleWfComment = async (content: string) => {
    if (!wfDetail?.id || !viewRec) return
    setWfCommenting(true)
    try {
      await workflowApi.comment(wfDetail.id, content)
      setWfDetail(await loadTechAgreementWf(viewRec.row.id))
    } finally {
      setWfCommenting(false)
    }
  }

  const enterEdit = () => {
    if (!viewRec || !canEditTarStatus(viewRec.row.status)) {
      message.warning('当前状态不可编辑')
      return
    }
    setViewRec({ ...viewRec, readonly: false })
  }

  const fillFromCustomer = async (customerId: string, fallbackName?: string) => {
    setFillingCustomer(true)
    try {
      const res = await customerApi.get(customerId)
      const c = res.data
      form.setFieldsValue({
        customer_id: customerId,
        company_name: (c.name || fallbackName || '').trim() || undefined,
        industry: formatCustomerIndustry(c) || undefined,
        address: formatCustomerAddress(c) || undefined,
      })
    } catch {
      form.setFieldsValue({
        customer_id: customerId,
        company_name: fallbackName || form.getFieldValue('company_name'),
      })
    } finally {
      setFillingCustomer(false)
    }
  }

  const saveEdit = async (andSubmit: boolean) => {
    if (!viewRec) return
    let values: Record<string, unknown>
    if (andSubmit) {
      try {
        values = await form.validateFields()
      } catch (err: unknown) {
        const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
        message.warning(fields[0]?.errors?.[0] || '请完善必填项后再提交')
        const name = fields[0]?.name
        if (name?.length) form.scrollToField(name, { behavior: 'smooth', block: 'center' })
        return
      }
    } else {
      values = form.getFieldsValue(true) as Record<string, unknown>
    }
    setSaving(true)
    try {
      const payload = tarBuildPayload({ ...form.getFieldsValue(true), ...values })
      await techAgreementReviewApi.update(viewRec.row.id, payload)
      if (andSubmit) {
        await techAgreementReviewApi.submit(viewRec.row.id)
        message.success('已提交审批')
        await refreshView()
        setViewRec((s) => (s ? { ...s, readonly: true } : s))
      } else {
        message.success('已存为草稿')
        await refreshView()
      }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      message.error(msg || (andSubmit ? '提交失败' : '存草稿失败'))
    } finally {
      setSaving(false)
    }
  }

  const submitFromView = async () => {
    if (!viewRec) return
    if (!viewRec.readonly) {
      await saveEdit(true)
      return
    }
    // 只读查看时：先进入编辑校验，或直接 submit 当前已存数据
    setSaving(true)
    try {
      await techAgreementReviewApi.submit(viewRec.row.id)
      message.success('已提交审批')
      await refreshView()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
      if (msg) {
        message.warning(msg)
        enterEdit()
      } else {
        message.error('提交失败')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!viewRec) return
    await techAgreementReviewApi.delete(viewRec.row.id)
    message.success('已删除')
    closeView()
    setReload((n) => n + 1)
  }

  const renderCell = (col: TarListColumnDef, row: TechAgreementReview): ReactNode => {
    const raw = readColValue(row, col)
    const kind = col.kind || 'text'
    if (col.key === 'review_code') {
      return (
        <a className="text-primary font-bold font-mono" onClick={() => void openView(row.id)}>
          {dash(raw)}
        </a>
      )
    }
    if (kind === 'status') {
      const v = String(raw || '')
      return <Tag color={STATUS_COLOR[v] || 'default'}>{STATUS_LABEL[v] || v || '—'}</Tag>
    }
    if (kind === 'tag') {
      if (raw == null || raw === '') return '—'
      const lab = String(raw)
      return <Tag color={optionTagColor(lab)} style={{ marginInlineEnd: 0 }}>{lab}</Tag>
    }
    if (kind === 'date') return fmtDate(raw as string | null)
    if (kind === 'person' || kind === 'dept') {
      return <span className="text-primary">{dash(raw)}</span>
    }
    const s = dash(raw)
    if (s === '—') return s
    return <span className="truncate inline-block max-w-full align-bottom" title={s}>{s}</span>
  }

  const baseColumns: ColumnsType<TechAgreementReview> = useMemo(() => {
    const cols: ColumnsType<TechAgreementReview> = TECH_AGREEMENT_LIST_COLUMNS.map((col) => ({
      key: col.key,
      dataIndex: col.key,
      title: col.title,
      width: col.width,
      ellipsis: true,
      fixed: col.fixed,
      render: (_: unknown, row: TechAgreementReview) => renderCell(col, row),
    }))
    cols.push({
      title: '操作',
      key: 'actions',
      width: 100,
      fixed: 'right',
      render: (_, r) => (
        <a className="text-primary text-sm px-2" onClick={() => void openView(r.id)}>查看</a>
      ),
    })
    return cols
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const view = useListView<TechAgreementReview>('tech_agreement_review', baseColumns, {
    pageKey: 'tech_agreement_reviews_v1',
    entityType: 'tech_agreement_review',
  })

  const fetchData = async (p = page) => {
    setLoading(true)
    try {
      const res = await techAgreementReviewApi.list({
        pageNo: p,
        pageSize,
        keyword: kwRef.current || undefined,
        status,
        ...view.buildParams(),
      })
      setData(res.data.items)
      setTotal(res.data.total)
      return res.data.items as TechAgreementReview[]
    } finally {
      setLoading(false)
    }
  }

  const [navBusy, setNavBusy] = useState(false)
  const viewNavIndex = viewRec ? data.findIndex((r) => r.id === viewRec.row.id) : -1
  const viewNavGlobalIndex = viewNavIndex >= 0 ? (page - 1) * pageSize + viewNavIndex : -1

  const goViewRelative = async (delta: -1 | 1) => {
    if (!viewRec || navBusy) return
    const idx = data.findIndex((r) => r.id === viewRec.row.id)
    if (idx >= 0) {
      const nextIdx = idx + delta
      if (nextIdx >= 0 && nextIdx < data.length) {
        setNavBusy(true)
        try {
          await openView(data[nextIdx].id)
        } finally {
          setNavBusy(false)
        }
        return
      }
    }
    const targetPage = page + delta
    const maxPage = Math.max(1, Math.ceil(total / pageSize) || 1)
    if (targetPage < 1 || targetPage > maxPage) return
    setNavBusy(true)
    try {
      setPage(targetPage)
      const nextItems = (await fetchData(targetPage)) || []
      const pick = delta > 0 ? nextItems[0] : nextItems[nextItems.length - 1]
      if (pick) await openView(pick.id)
    } finally {
      setNavBusy(false)
    }
  }

  useEffect(() => {
    fetchData(1)
    setPage(1)
  }, [status, reload]) // eslint-disable-line react-hooks/exhaustive-deps

  const showFlowPane = !!wfDetail || (
    !!viewRec && ['submitted', 'approved', 'rejected'].includes(viewRec.row.status || '')
  )
  const modalWidth = showFlowPane ? 1100 : 760
  const fsProps = modalFullscreenProps(modalFullscreen, modalWidth)
  const contentMaxH = modalFullscreen ? 'calc(100vh - 200px)' : '70vh'
  const editable = !!viewRec && canEdit && canEditTarStatus(viewRec.row.status)
  const modalOpen = !!viewRec || viewLoading

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-xl font-semibold m-0">技术协议评审</h2>
          <p className="text-sm text-slate-500 mt-0.5 m-0">对齐威猛云销售中心「合同技术协议评审」</p>
        </div>
        {canCreate && (
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate(FILL_PATH)}>
            新增
          </Button>
        )}
      </div>
      <div className="flex flex-wrap gap-2 mb-4 items-center">
        <Input
          allowClear
          placeholder="流水号/公司/项目/业务员"
          prefix={<SearchOutlined />}
          className="w-64"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          onPressEnter={() => { setPage(1); fetchData(1) }}
        />
        <Select
          allowClear
          placeholder="全部状态"
          className="w-36"
          value={status}
          onChange={setStatus}
          options={TECH_AGREEMENT_STATUS.map((s) => ({ value: s.value, label: s.label }))}
        />
        <Button onClick={() => { setPage(1); fetchData(1) }}>查询</Button>
        <ListToolbar resource="tech_agreement_review" view={view} onChange={() => setReload((r) => r + 1)} />
      </div>
      <FillHeightTable
        rowKey="id"
        loading={loading}
        size="small"
        columns={view.columns}
        dataSource={data}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize,
          total,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p) => { setPage(p); fetchData(p) },
        }}
      />

      <Modal
        title={(
          <ModalFullscreenTitle
            title={viewRec && !viewRec.readonly ? '编辑记录' : '查看记录'}
            fullscreen={modalFullscreen}
            onToggle={() => setModalFullscreen((v) => !v)}
          />
        )}
        open={modalOpen}
        width={fsProps.width}
        style={fsProps.style}
        wrapClassName={fsProps.wrapClassName}
        styles={fsProps.styles}
        onCancel={closeView}
        footer={
          viewRec && !viewRec.readonly && editable
            ? [
                <Button key="c" onClick={closeView}>取消</Button>,
                <Button key="s" loading={saving} onClick={() => void saveEdit(false)}>存草稿</Button>,
                <Button key="sub" type="primary" loading={saving} onClick={() => void saveEdit(true)}>提交审批</Button>,
              ]
            : [<Button key="c" onClick={closeView}>关闭</Button>]
        }
        destroyOnClose
      >
        {viewLoading && !viewRec ? (
          <div className="flex justify-center py-16"><Spin /></div>
        ) : viewRec ? (
          <div className={modalFullscreen ? 'flex flex-col flex-1 min-h-0' : undefined}>
            <div
              className="flex items-center gap-1 mb-3 px-1 py-1 border-b border-slate-100 flex-wrap shrink-0"
              style={{ marginTop: -4 }}
            >
              <Tag color={STATUS_COLOR[viewRec.row.status] || 'default'}>
                {STATUS_LABEL[viewRec.row.status] || viewRec.row.status}
              </Tag>
              <span className="font-mono text-sm text-slate-600 mr-2">{viewRec.row.review_code}</span>
              {editable && viewRec.readonly && (
                <Button type="text" icon={<EditOutlined />} onClick={enterEdit}>编辑</Button>
              )}
              {editable && (
                <Button type="text" icon={<SendOutlined />} loading={saving} onClick={() => void submitFromView()}>
                  提交审批
                </Button>
              )}
              {canDelete && (
                <Popconfirm title="确认删除该记录?" onConfirm={() => void handleDelete()}>
                  <Button type="text" danger icon={<DeleteOutlined />}>删除</Button>
                </Popconfirm>
              )}
              <div className="flex-1" />
              <RecordPrevNextNav
                index={viewNavGlobalIndex}
                total={total}
                disabled={navBusy || viewLoading}
                onPrev={() => { void goViewRelative(-1) }}
                onNext={() => { void goViewRelative(1) }}
              />
            </div>
            <div className="flex gap-0 flex-1 min-h-0" style={{ minHeight: modalFullscreen ? undefined : 480 }}>
              <div className="flex-1 overflow-y-auto pr-3" style={{ maxHeight: contentMaxH }}>
                <Form form={form} layout="vertical">
                  <ContractSectionTitle title="关联客户" />
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 mb-4">
                    {viewRec.readonly ? (
                      <Form.Item label="公司名称">
                        <div className="min-h-[32px] py-1 text-[15px] leading-6 text-slate-800 break-words">
                          {(form.getFieldValue('company_name') as string) || '—'}
                        </div>
                      </Form.Item>
                    ) : (
                      <Form.Item name="customer_id" label="选择公司名称">
                        <Select
                          allowClear
                          showSearch
                          filterOption={false}
                          placeholder="从客户库选择"
                          loading={customerSelect.loading || fillingCustomer}
                          options={customerSelect.options}
                          onSearch={customerSelect.onSearch}
                          onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
                          onChange={(v, opt) => {
                            if (!v) {
                              form.setFieldsValue({
                                customer_id: undefined,
                                company_name: undefined,
                                industry: undefined,
                                address: undefined,
                              })
                              return
                            }
                            void fillFromCustomer(String(v), (opt as { label?: string } | undefined)?.label)
                          }}
                        />
                      </Form.Item>
                    )}
                  </div>
                  <TechAgreementFields
                    form={form}
                    readOnly={viewRec.readonly}
                    includeApproverSections={viewRec.readonly || ['submitted', 'approved', 'rejected'].includes(viewRec.row.status)}
                    slots={{
                      approve_files: (
                        <div className="md:col-span-2 mb-4 space-y-3">
                          <AttachmentPanel
                            bizType="tech_agreement_review_drawing"
                            bizId={viewRec.row.id}
                            title="认可图（附件）"
                          />
                          <AttachmentPanel
                            bizType="tech_agreement_review"
                            bizId={viewRec.row.id}
                            title="技术协议（附件）"
                          />
                        </div>
                      ),
                    }}
                  />
                </Form>
              </div>
              {showFlowPane && (
                <div
                  className="w-[300px] shrink-0 overflow-hidden rounded-md border border-slate-200"
                  style={{ maxHeight: contentMaxH, height: modalFullscreen ? contentMaxH : undefined }}
                >
                  {wfDetail ? (
                    <WfFlowDynamics
                      steps={wfDetail.flow_steps || []}
                      comments={wfDetail.comments || []}
                      onSubmitComment={handleWfComment}
                      commenting={wfCommenting}
                    />
                  ) : (
                    <div className="h-full flex items-center justify-center bg-slate-50 px-4">
                      <Text type="secondary" className="text-sm">
                        {viewRec.row.status === 'draft' ? '提交审批后将在此显示流程进度' : '暂无流程动态'}
                      </Text>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </Modal>
    </div>
  )
}
