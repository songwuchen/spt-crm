import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { Tag, Select, Input, Button, Modal, Form, message, Space } from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import { SearchOutlined, PlusOutlined, DownloadOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import { contractApi } from '@/api/contract'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import type { ContractItem } from '@/api/types'
import { contractDisplayStatusLabels, contractDisplayStatusColors, resolveContractDisplayStatus, isContractDraftDeletable } from '@/constants/labels'
import { formatChangeType } from '@/constants/contractRegistration'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'
import { useListView } from '@/hooks/useListView'
import { useCustomerSelect } from '@/hooks/useSelectOptions'
import { rememberSiblingNav } from '@/hooks/useSiblingRecordNav'
import ListToolbar from '@/components/list/ListToolbar'
import { fmtMoney } from '@/utils/mask'
import CustomFieldsPanel, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import ContractRegistrationFields from '@/components/ContractRegistrationFields'
import ContractAttachmentSlots, { flushPendingAttachments, type PendingAttachments } from '@/components/ContractAttachmentSlots'
import { PaymentTermsEditor, LineItemsEditor, ContractSubtableTitle } from '@/components/ContractTerms'
import { LINE_ITEMS_FIELD_ID, PAYMENT_TERMS_FIELD_ID } from '@/constants/contractDetailTables'
import dayjs from 'dayjs'
import { formatFormDate, isValidFormDate } from '@/utils/formDate'
import { downloadFile } from '@/utils/download'

/** 登记 JSON 字段（列表纯文本展示） */
function regText(r: ContractItem, key: string): string {
  const v = (r.registration_json as Record<string, unknown> | undefined)?.[key]
  if (v == null || v === '') return '-'
  if (Array.isArray(v)) return v.map(String).filter(Boolean).join('、') || '-'
  return String(v)
}

export default function ContractList() {
  usePageTitle('合同登记')
  const navigate = useNavigate()
  const [data, setData] = useState<ContractItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterCustomerName, setFilterCustomerName] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  const { hasPermission } = usePermission()
  const canCreate = hasPermission('contract:create')
  const canDelete = hasPermission('contract:delete')

  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm()
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)
  const [createLines, setCreateLines] = useState<Record<string, unknown>[]>([{}])
  const [createPay, setCreatePay] = useState<Record<string, unknown>[]>([{}])
  const [pendingAtts, setPendingAtts] = useState<PendingAttachments>({})
  const customerSelect = useCustomerSelect()
  /** 选客户后回填客户编号 / 部门 / 业务员（对齐客户管理主数据） */
  const fillFromCustomer = async (customerId?: string) => {
    if (!customerId) return
    try {
      const c = (await customerApi.get(customerId)).data
      if (!c) return
      const reg = { ...(createForm.getFieldValue('registration_json') || {}) } as Record<string, unknown>
      if (c.customer_code) reg.customer_code = c.customer_code
      const patch: Record<string, unknown> = { registration_json: reg }
      if (c.department_id) patch.department_id = c.department_id
      if (c.department_name) patch.department_name = c.department_name
      if (c.owner_id) {
        patch.assignee_id = c.owner_id
        if (c.owner_name) patch.assignee_name = c.owner_name
      }
      createForm.setFieldsValue(patch)
    } catch { /* ignore */ }
  }
  /** 对齐简道云选关联后带出：商机 → 客户/客户编号/业务人员/部门/项目名称 */
  const fillFromProject = async (projectId?: string) => {
    if (!projectId) return
    try {
      const r = await projectApi.get(projectId)
      const p = r.data
      if (!p) return
      const reg = { ...(createForm.getFieldValue('registration_json') || {}) } as Record<string, unknown>
      if (p.name) reg.project_name = p.name
      const patch: Record<string, unknown> = {
        registration_json: reg,
        ...(p.owner_id ? { assignee_id: p.owner_id } : {}),
        ...(p.owner_name ? { assignee_name: p.owner_name } : {}),
      }
      if (p.customer_id) {
        patch.customer_id = p.customer_id
        try {
          const c = (await customerApi.get(p.customer_id)).data
          if (c?.name) customerSelect.setInitialOption({ label: c.name, value: p.customer_id })
          if (c?.customer_code) reg.customer_code = c.customer_code
          if (c?.department_id) patch.department_id = c.department_id
          if (c?.department_name) patch.department_name = c.department_name
          if (c?.owner_id && !patch.assignee_id) {
            patch.assignee_id = c.owner_id
            if (c.owner_name) patch.assignee_name = c.owner_name
          }
          patch.registration_json = { ...reg }
        } catch { /* ignore */ }
      }
      createForm.setFieldsValue(patch)
    } catch { /* ignore */ }
  }
  const syncAmountFromLines = (total: number) => {
    createForm.setFieldsValue({ amount_total: total || undefined })
  }
  const openCreate = () => {
    createForm.resetFields()
    createForm.setFieldsValue({
      change_type: 'new',
      registration_json: {},
    })
    setCustomFields({})
    setCreateLines([{}])
    setCreatePay([{}])
    setPendingAtts({})
    setCreateOpen(true)
    contractApi.peekSerialNo().then((r: { data?: { serial_no?: string } }) => {
      if (r.data?.serial_no) createForm.setFieldsValue({ serial_no: r.data.serial_no })
    }).catch(() => { /* 预览失败不阻塞 */ })
  }
  const handleCreate = async (andSubmit: boolean) => {
    let v: Record<string, unknown>
    if (andSubmit) {
      try {
        v = await createForm.validateFields()
      } catch (err: unknown) {
        const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
        const first = fields[0]?.errors?.[0]
        message.warning(first || '请完善必填项后再提交')
        const name = fields[0]?.name
        if (name?.length) {
          createForm.scrollToField(name, { behavior: 'smooth', block: 'center' })
        }
        return
      }
      const cfError = customFieldsRef.current?.validate()
      if (cfError) {
        message.error(cfError)
        return
      }
    } else {
      // 存草稿：不跑 validateFields；清掉上次点「提交」留下的红字提示
      const stale = createForm.getFieldsError().filter((f) => f.errors?.length)
      if (stale.length) {
        createForm.setFields(stale.map((f) => ({ name: f.name, errors: [] })))
      }
      v = createForm.getFieldsValue(true) as Record<string, unknown>
    }
    const drawingNo = String(v.drawing_no || '').trim()
    // 合同号来自对应表「合同号」字段（选图纸号时已回填）
    const contractNo = String(v.contract_no || '').trim() || drawingNo
    if (andSubmit && !drawingNo) {
      message.warning('请从合同图纸对应表选择图纸编号')
      createForm.setFields([{ name: 'drawing_no', errors: ['请从合同图纸对应表选择图纸编号'] }])
      createForm.scrollToField('drawing_no', { behavior: 'smooth', block: 'center' })
      return
    }
    const nativeDates: { name: string; label: string; value: unknown }[] = [
      { name: 'card_date', label: '下卡日期', value: v.card_date },
      { name: 'order_date', label: '订货日期', value: v.order_date },
      { name: 'delivery_date', label: '合同交货期', value: v.delivery_date },
      { name: 'end_date', label: '到期日期', value: v.end_date },
    ]
    const badNative = nativeDates.filter((d) => !isValidFormDate(d.value))
    if (badNative.length) {
      createForm.setFields(badNative.map((d) => ({
        name: d.name,
        errors: [`请选择或输入有效的${d.label}`],
      })))
      message.warning(`请修正日期：${badNative.map((d) => d.label).join('、')}`)
      createForm.scrollToField(badNative[0].name, { behavior: 'smooth', block: 'center' })
      return
    }
    setCreating(true)
    try {
      const regRaw = { ...(v.registration_json || {}) } as Record<string, unknown>
      delete regRaw.number_lookup
      const numberAttr = String(regRaw.number_attr || 'WMGF').trim().toUpperCase()
      regRaw.number_attr = numberAttr === 'SY' ? 'SY' : 'WMGF'
      for (const [k, val] of Object.entries(regRaw)) {
        if (val && typeof val === 'object' && dayjs.isDayjs(val)) {
          if (!val.isValid()) {
            message.warning('登记信息中存在无效日期，请重新选择')
            return
          }
          regRaw[k] = val.format('YYYY-MM-DD')
        }
      }
      const endDate = formatFormDate(v.end_date)
      const deliveryDate = formatFormDate(v.delivery_date)
      const orderDate = formatFormDate(v.order_date)
      const cardDate = formatFormDate(v.card_date)
      const lines = createLines.filter((r) => Object.values(r).some((x) => x != null && x !== ''))
      const pays = createPay.filter((r) => Object.values(r).some((x) => x != null && x !== ''))
      const projectId = typeof v.project_id === 'string' ? v.project_id : null
      const res = await contractApi.create(projectId, {
        title: v.title || 'V1',
        as_draft: !andSubmit,
        ...(v.project_id ? { project_id: v.project_id } : {}),
        ...(v.amount_total != null ? { amount_total: v.amount_total } : {}),
        ...(endDate ? { end_date: endDate } : {}),
        ...(deliveryDate ? { delivery_date: deliveryDate } : {}),
        ...(orderDate ? { order_date: orderDate } : {}),
        ...(cardDate ? { card_date: cardDate } : {}),
        ...(contractNo ? { contract_no: contractNo } : {}),
        ...(drawingNo ? { drawing_no: drawingNo } : {}),
        ...(v.peer_contract_no ? { peer_contract_no: v.peer_contract_no } : {}),
        ...(v.acquire_method ? { acquire_method: v.acquire_method } : {}),
        ...(v.change_type ? { change_type: v.change_type } : {}),
        ...(v.assignee_id ? { assignee_id: v.assignee_id } : {}),
        ...(v.assignee_name ? { assignee_name: v.assignee_name } : {}),
        ...(v.department_id ? { department_id: v.department_id } : {}),
        ...(v.department_name ? { department_name: v.department_name } : {}),
        ...(v.customer_id ? { customer_id: v.customer_id } : {}),
        registration_json: Object.keys(regRaw).length ? regRaw : undefined,
        ...(lines.length ? { key_clauses_json: lines } : {}),
        ...(pays.length ? { payment_terms_json: pays } : {}),
        ...(v.content && !lines.length ? { key_clauses_json: [{ item: '合同内容', content: v.content }] } : {}),
        custom_fields_json: customFields,
      }) as any
      const cid = res?.data?.contract?.id as string | undefined
      const vid = res?.data?.version?.id as string | undefined
      if (cid) {
        const pendingCount = Object.values(pendingAtts).reduce((n, arr) => n + (arr?.length || 0), 0)
        if (pendingCount > 0) {
          const { ok, fail } = await flushPendingAttachments(cid, pendingAtts)
          if (fail) message.warning(`附件上传完成：成功 ${ok}，失败 ${fail}`)
          else if (ok) message.success(`已上传 ${ok} 个附件`)
        }
      }
      if (andSubmit) {
        if (!vid) {
          message.error('未获取到合同版本，无法提交审批')
          if (cid) navigate(`/contracts/${cid}`)
          return
        }
        try {
          await contractApi.submitVersion(vid)
          message.success('已提交审批，请在「审批中心」处理待办')
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          message.warning(msg || '合同已保存，但提交审批失败，请到详情页重新提交')
          if (cid) navigate(`/contracts/${cid}`)
          setCreateOpen(false)
          setCustomFields({})
          setPendingAtts({})
          return
        }
      } else {
        message.success('已存为草稿')
      }
      setCreateOpen(false)
      setCustomFields({})
      setPendingAtts({})
      if (cid) navigate(`/contracts/${cid}`)
      else fetchData()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : ''
      if (msg) {
        if (msg.includes('合同号') || /图纸编号/.test(msg)) {
          message.warning(msg)
          const field = /图纸编号/.test(msg) ? 'drawing_no' : 'contract_no'
          createForm.setFields([{ name: field, errors: [msg] }])
          createForm.scrollToField(field, { behavior: 'smooth', block: 'center' })
        } else {
          message.warning(msg)
        }
      }
    } finally { setCreating(false) }
  }

  const fetchData = async (
    page = pageNo,
    kw = keyword,
    st = filterStatus,
    cust = filterCustomerName,
  ) => {
    setLoading(true)
    try {
      const r = await contractApi.list({
        pageNo: page,
        pageSize: 20,
        keyword: kw || undefined,
        customer_name: cust || undefined,
        status: st,
        ...view.buildParams(),
      }) as any
      setData(r.data?.items || [])
      setTotal(r.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload])

  const handleDelete = useCallback((row: ContractItem) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定删除合同「${row.contract_no}」？仅草稿可删除，删除后不可恢复。`,
      okType: 'danger',
      okText: '删除',
      onOk: async () => {
        await contractApi.delete(row.id)
        message.success('已删除')
        fetchData()
      },
    })
  }, [])

  const openDetail = useCallback((rid: string) => {
    rememberSiblingNav('contracts', {
      ids: data.map((d) => d.id),
      total,
      pageNo,
      pageSize: 20,
      listQuery: {
        keyword: keyword || undefined,
        customer_name: filterCustomerName || undefined,
        status: filterStatus,
      },
    })
    navigate(`/contracts/${rid}`)
  }, [data, total, pageNo, keyword, filterCustomerName, filterStatus, navigate])

  const columns: ColumnsType<ContractItem> = useMemo(() => {
    const cols: ColumnsType<ContractItem> = [
      // —— 对齐简道云合同登记列表（纯文本）——
      {
        title: '流水号', dataIndex: 'serial_no', width: 168, fixed: 'left',
        render: (v: string, r: ContractItem) => (
          <a className="font-mono text-xs" onClick={() => openDetail(r.id)}>{v || '—'}</a>
        ),
      },
      { title: '提交人', dataIndex: 'created_by_name', width: 90, ellipsis: true, render: (v: string) => v || '-' },
      { title: '下卡日期', dataIndex: 'card_date', width: 108, render: (v: string) => v || '-' },
      { title: '客户编号', width: 120, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'customer_code') },
      { title: '单位名称', dataIndex: 'customer_name', width: 180, ellipsis: true, render: (v: string) => v || '-' },
      {
        title: '关联商机', dataIndex: 'project_name', width: 180, ellipsis: true,
        render: (v: string, r: ContractItem) => {
          if (!r.project_id && !v) return '-'
          const label = v || r.project_id || '-'
          if (!r.project_id) return label
          return (
            <a
              className="text-primary"
              onClick={(e) => { e.stopPropagation(); navigate(`/opportunities/${r.project_id}`) }}
            >
              {label}
            </a>
          )
        },
      },
      { title: '部门', dataIndex: 'department_name', width: 160, ellipsis: true, render: (v: string) => v || '-' },
      { title: '业务人员', dataIndex: 'assignee_name', width: 90, render: (v: string) => v || '-' },
      { title: '合同状态', dataIndex: 'change_type', width: 80, render: (v: string) => formatChangeType(v) },
      { title: '变动原因', width: 160, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'change_reason') },
      { title: '合同获取信息方式', dataIndex: 'acquire_method', width: 130, ellipsis: true, render: (v: string) => v || '-' },
      { title: '合同号', dataIndex: 'contract_no', width: 110,
        render: (v: string, r: ContractItem) => (
          <a className="font-mono" onClick={() => openDetail(r.id)}>{v}</a>
        ),
      },
      { title: '合同/项目评审流水号', width: 150, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'review_sn') },
      { title: '小萌合同评审流水号', width: 150, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'review_sn_xm') },
      { title: '出厂编号', width: 100, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'factory_no') },
      { title: '订货日期', dataIndex: 'order_date', width: 108, render: (v: string) => v || '-' },
      { title: '合同类型', width: 90, render: (_: unknown, r: ContractItem) => regText(r, 'contract_type') },
      { title: '图纸编号', dataIndex: 'drawing_no', width: 130, ellipsis: true, render: (v: string) => v || '-' },
      { title: '项目名称', width: 140, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'project_name') },
      { title: '对方合同号', dataIndex: 'peer_contract_no', width: 130, ellipsis: true, render: (v: string) => v || '-' },
      { title: '是否含税', width: 80, render: (_: unknown, r: ContractItem) => regText(r, 'tax_included') },
      { title: '设备是否出口', width: 100, render: (_: unknown, r: ContractItem) => regText(r, 'is_export') },
      { title: '是否需要安装', width: 110, render: (_: unknown, r: ContractItem) => regText(r, 'need_install') },
      { title: '信息是否齐全', width: 110, render: (_: unknown, r: ContractItem) => regText(r, 'info_complete') },
      { title: '缺少项', width: 120, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'missing_items') },
      { title: '信息不齐全备注', width: 140, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'info_incomplete_note') },
      { title: '出口类型', width: 100, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'export_type') },
      { title: '合同形式', width: 130, ellipsis: true, render: (_: unknown, r: ContractItem) => regText(r, 'contract_form') },
      { title: '是否标准交付', width: 110, render: (_: unknown, r: ContractItem) => regText(r, 'standard_delivery') },
      { title: '方式', width: 90, render: (_: unknown, r: ContractItem) => regText(r, 'delivery_mode') },
      { title: '是否为旋振筛', width: 100, render: (_: unknown, r: ContractItem) => regText(r, 'is_rotary_sieve') },
      // CRM 补充（简道云列表无对应列）
      {
        title: '状态', dataIndex: 'status', width: 90,
        render: (_: string, r: ContractItem) => {
          const ds = resolveContractDisplayStatus(r.status, r.current_version_status)
          return <Tag color={contractDisplayStatusColors[ds] || 'default'}>{contractDisplayStatusLabels[ds] || ds}</Tag>
        },
      },
      { title: '金额', dataIndex: 'amount_total', width: 110, align: 'right',
        render: (v: number | string) => fmtMoney(v) },
    ]
    if (canDelete) {
      cols.push({
        title: '操作',
        key: 'actions',
        width: 100,
        fixed: 'right',
        render: (_: unknown, r: ContractItem) => (
          <Space size={0}>
            <a className="text-primary text-sm px-2" onClick={() => openDetail(r.id)}>详情</a>
            {isContractDraftDeletable(r.status, r.current_version_status) && (
              <a className="text-rose-500 text-sm px-2" onClick={() => handleDelete(r)}>删除</a>
            )}
          </Space>
        ),
      })
    }
    return cols
  }, [canDelete, handleDelete, openDetail, navigate])

  const view = useListView<ContractItem>('contract', columns, { pageKey: 'contracts', entityType: 'contract' })

  return (
    <div>
      <div className="flex items-center justify-between mb-6 shrink-0">
        <div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">合同登记</h1>
          <p className="text-sm text-slate-500 mt-0.5">对齐简道云数据中心「合同登记表」：明细、收款计划、质保、行业与验收等</p>
        </div>
        {canCreate && <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增登记</Button>}
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 mb-4 shrink-0">
        <div className="flex gap-3 flex-wrap items-center">
          <Input prefix={<SearchOutlined className="text-slate-400" />} placeholder="搜索合同号 / 图纸号 / 对方合同号"
            value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus, filterCustomerName) }}
            allowClear style={{ width: 280 }} />
          <Input placeholder="客户名称" value={filterCustomerName}
            onChange={(e) => setFilterCustomerName(e.target.value)}
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus, filterCustomerName) }}
            allowClear style={{ width: 160 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v, filterCustomerName) }}
            options={Object.entries(contractDisplayStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <Button icon={<DownloadOutlined />} onClick={() => {
            const qs = new URLSearchParams()
            if (keyword) qs.set('keyword', keyword)
            if (filterCustomerName) qs.set('customer_name', filterCustomerName)
            if (filterStatus) qs.set('status', filterStatus)
            const extra = view.buildParams()
            if (extra.filter) qs.set('filter', String(extra.filter))
            if (extra.sort_by) qs.set('sort_by', String(extra.sort_by))
            if (extra.sort_order) qs.set('sort_order', String(extra.sort_order))
            const q = qs.toString()
            void downloadFile(`/api/v1/contracts/export/excel${q ? `?${q}` : ''}`, 'contracts.xlsx').catch((e: Error) => {
              message.error(e.message || '导出失败')
            })
          }}>导出</Button>
          <ListToolbar resource="contract" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <FillHeightTable rowKey="id" dataSource={data} loading={loading} size="small"
          scroll={{ x: 3780 }}
          pagination={{
            current: pageNo, total, pageSize: 20, showTotal: (t) => `共 ${t} 条`,
            onChange: (p) => { setPageNo(p); fetchData(p) },
          }}
          columns={view.columns}
        />
      </div>

      <Modal
        title="新增合同登记"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        width={920}
        destroyOnClose
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}
        footer={[
          <Button key="cancel" htmlType="button" onClick={() => setCreateOpen(false)}>取消</Button>,
          <Button key="draft" htmlType="button" loading={creating} onClick={() => void handleCreate(false)}>存草稿</Button>,
          <Button key="submit" type="primary" htmlType="button" loading={creating} onClick={() => void handleCreate(true)}>提交</Button>,
        ]}
      >
       <FieldPolicyProvider entityType="contract" form={createForm} customFieldValues={customFields} formMode="create">
        <Form form={createForm} layout="vertical" className="mt-3" scrollToFirstError>
          <Form.Item name="title" label="合同标题"><Input placeholder="如：设备采购合同（默认 V1）" /></Form.Item>
          <ContractRegistrationFields
            form={createForm}
            mode="create"
            customerSelect={customerSelect}
            onCustomerChange={fillFromCustomer}
            onProjectChange={fillFromProject}
            slots={{
              line_items: (
                <div>
                  <ContractSubtableTitle fieldId={LINE_ITEMS_FIELD_ID} fallback="合同明细" />
                  <LineItemsEditor
                    value={createLines}
                    onChange={setCreateLines}
                    onTotalChange={syncAmountFromLines}
                  />
                </div>
              ),
              payment_terms: (
                <div>
                  <ContractSubtableTitle fieldId={PAYMENT_TERMS_FIELD_ID} fallback="收款计划" />
                  <Form.Item noStyle shouldUpdate={(prev, cur) => prev.amount_total !== cur.amount_total}>
                    {() => (
                      <PaymentTermsEditor
                        value={createPay}
                        onChange={setCreatePay}
                        contractTotal={Number(createForm.getFieldValue('amount_total')) || 0}
                        hideFinanceFields
                      />
                    )}
                  </Form.Item>
                </div>
              ),
              contract_files: (
                <ContractAttachmentSlots
                  slot="contract_files"
                  pending={pendingAtts}
                  onPendingChange={setPendingAtts}
                />
              ),
              accept_files: (
                <ContractAttachmentSlots
                  slot="accept_files"
                  pending={pendingAtts}
                  onPendingChange={setPendingAtts}
                />
              ),
            }}
          />
          <CustomFieldsPanel ref={customFieldsRef} entityType="contract"
            value={customFields} onChange={setCustomFields} />
          <div className="text-[12px] text-slate-400">
            「提交」会直接发起审批并校验必填；「存草稿」仅保存当前已填内容，可稍后在详情页补全再提交。
          </div>
        </Form>
       </FieldPolicyProvider>
      </Modal>
    </div>
  )
}
