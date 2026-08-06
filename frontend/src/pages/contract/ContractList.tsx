import { useState, useEffect, useRef } from 'react'
import { Tag, Select, Input, Button, Modal, Form, message } from 'antd'
import FillHeightTable from '@/components/list/FillHeightTable'
import { SearchOutlined, PlusOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import type { ColumnsType } from 'antd/es/table'
import { contractApi } from '@/api/contract'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import type { ContractItem } from '@/api/types'
import { contractDisplayStatusLabels, contractDisplayStatusColors, resolveContractDisplayStatus } from '@/constants/labels'
import { formatChangeType } from '@/constants/contractRegistration'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'
import { useListView } from '@/hooks/useListView'
import { useCustomerSelect } from '@/hooks/useSelectOptions'
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


export default function ContractList() {
  usePageTitle('合同登记')
  const navigate = useNavigate()
  const [data, setData] = useState<ContractItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [pageNo, setPageNo] = useState(1)
  const [keyword, setKeyword] = useState('')
  const [filterStatus, setFilterStatus] = useState<string | undefined>()
  const [reload, setReload] = useState(0)
  const didMount = useRef(false)

  const { hasPermission } = usePermission()
  const canCreate = hasPermission('contract:create')

  const [createOpen, setCreateOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [createForm] = Form.useForm()
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)
  const [createLines, setCreateLines] = useState<Record<string, unknown>[]>([{}])
  const [createPay, setCreatePay] = useState<Record<string, unknown>[]>([{}])
  const [pendingAtts, setPendingAtts] = useState<PendingAttachments>({})
  const [projOpts, setProjOpts] = useState<{ label: string; value: string }[]>([])
  const [projLoading, setProjLoading] = useState(false)
  const customerSelect = useCustomerSelect()
  const searchProjects = async (kw?: string) => {
    setProjLoading(true)
    try {
      const r = await projectApi.list({ pageNo: 1, pageSize: 20, keyword: kw || undefined })
      setProjOpts((r.data.items || []).map((p) => ({ label: `${p.name}（${p.project_code}）`, value: p.id })))
    } catch { /* ignore */ } finally { setProjLoading(false) }
  }
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
  const fillFromProject = async (projectId: string) => {
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
    createForm.setFieldsValue({ change_type: 'new', registration_json: {} })
    setCustomFields({})
    setCreateLines([{}])
    setCreatePay([{}])
    setPendingAtts({})
    setProjOpts([])
    searchProjects()
    setCreateOpen(true)
  }
  const handleCreate = async (andSubmit: boolean) => {
    let v
    try {
      v = await createForm.validateFields()
    } catch (err: unknown) {
      const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
      const first = fields[0]?.errors?.[0]
      message.warning(first || (andSubmit ? '请完善必填项后再提交' : '请完善必填项后再存草稿'))
      // 滚到第一个报错项（Modal body 可滚动）
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
    const contractNo = String(v.contract_no || '').trim()
    // 拦截 DatePicker 手输产生的 invalid dayjs，避免打成 "Invalid Date" 触发后端 422
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
      delete regRaw.number_attr
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
      const res = await contractApi.create(v.project_id || null, {
        title: v.title || 'V1',
        ...(v.project_id ? { project_id: v.project_id } : {}),
        ...(v.amount_total != null ? { amount_total: v.amount_total } : {}),
        ...(endDate ? { end_date: endDate } : {}),
        ...(deliveryDate ? { delivery_date: deliveryDate } : {}),
        ...(orderDate ? { order_date: orderDate } : {}),
        ...(cardDate ? { card_date: cardDate } : {}),
        contract_no: contractNo,
        // 图纸编号由后端按编号属性规则自动生成，不传 drawing_no
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
    } catch {
      // 业务错误（如合同号已存在）已由 api client 拦截器提示，不再盖「创建失败」
    } finally { setCreating(false) }
  }

  const fetchData = async (page = pageNo, kw = keyword, st = filterStatus) => {
    setLoading(true)
    try {
      const r = await contractApi.list({ pageNo: page, pageSize: 20, keyword: kw || undefined, status: st, ...view.buildParams() }) as any
      setData(r.data?.items || [])
      setTotal(r.data?.total || 0)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  useEffect(() => {
    if (!didMount.current) { didMount.current = true; return }
    fetchData(1)
  }, [reload])

  const columns: ColumnsType<ContractItem> = [
    { title: '合同编号', dataIndex: 'contract_no', width: 160,
      render: (v: string, r: ContractItem) => (
        <a className="font-mono font-bold text-primary" onClick={() => navigate(`/contracts/${r.id}`)}>{v}</a>
      ),
    },
    { title: '图纸编号', dataIndex: 'drawing_no', width: 140, ellipsis: true, render: (v: string) => v || '-' },
    { title: '对方合同号', dataIndex: 'peer_contract_no', width: 120, ellipsis: true, render: (v: string) => v || '-' },
    { title: '客户名称', dataIndex: 'customer_name', width: 160, ellipsis: true, render: (v: string) => v || '-' },
    { title: '商机名称', dataIndex: 'project_name', width: 160, ellipsis: true, render: (v: string) => v || '-' },
    {
      title: '项目名称', width: 140, ellipsis: true,
      render: (_: unknown, r: ContractItem) => (r.registration_json as any)?.project_name || '-',
    },
    { title: '登记类型', dataIndex: 'change_type', width: 90,
      render: (v: string) => formatChangeType(v) },
    {
      title: '合同类型', width: 100, ellipsis: true,
      render: (_: unknown, r: ContractItem) => (r.registration_json as any)?.contract_type || '-',
    },
    {
      title: '行业', width: 90, ellipsis: true,
      render: (_: unknown, r: ContractItem) => (r.registration_json as any)?.industry || '-',
    },
    { title: '状态', dataIndex: 'status', width: 90,
      render: (_: string, r: ContractItem) => {
        const ds = resolveContractDisplayStatus(r.status, r.current_version_status)
        return <Tag color={contractDisplayStatusColors[ds] || 'default'}>{contractDisplayStatusLabels[ds] || ds}</Tag>
      },
    },
    { title: '金额', dataIndex: 'amount_total', width: 120, align: 'right',
      render: (v: number | string) => <span className="font-bold">{fmtMoney(v)}</span> },
    { title: '订货日期', dataIndex: 'order_date', width: 110, render: (v: string) => v || '-' },
    { title: '交货期', dataIndex: 'delivery_date', width: 110, render: (v: string) => v || '-' },
    { title: '获取方式', dataIndex: 'acquire_method', width: 110, ellipsis: true, render: (v: string) => v || '-' },
    { title: '负责人', dataIndex: 'assignee_name', width: 90, render: (v: string) => v || '-' },
    { title: '创建时间', dataIndex: 'created_at', width: 110,
      render: (v: string) => v ? new Date(v).toLocaleDateString('zh-CN') : '-' },
  ]

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
            onPressEnter={() => { setPageNo(1); fetchData(1, keyword, filterStatus) }}
            allowClear style={{ width: 280 }} />
          <Select placeholder="状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(contractDisplayStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
          <ListToolbar resource="contract" view={view} onChange={() => setReload((r) => r + 1)} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <FillHeightTable rowKey="id" dataSource={data} loading={loading} size="small"
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
          <Button key="cancel" onClick={() => setCreateOpen(false)}>取消</Button>,
          <Button key="draft" loading={creating} onClick={() => void handleCreate(false)}>存草稿</Button>,
          <Button key="submit" type="primary" loading={creating} onClick={() => void handleCreate(true)}>提交</Button>,
        ]}
      >
       <FieldPolicyProvider entityType="contract" form={createForm} customFieldValues={customFields}>
        <Form form={createForm} layout="vertical" className="mt-3" scrollToFirstError>
          <Form.Item name="project_id" label="关联商机">
            <Select allowClear showSearch filterOption={false} placeholder="可选：搜索商机名称 / 编号"
              options={projOpts} loading={projLoading} onSearch={searchProjects}
              onChange={(id) => { if (id) void fillFromProject(id) }}
              onDropdownVisibleChange={(o) => { if (o && projOpts.length === 0) searchProjects() }} />
          </Form.Item>
          <Form.Item name="customer_id" label="关联客户">
            <Select
              allowClear showSearch filterOption={false}
              placeholder="搜索客户管理中的客户"
              options={customerSelect.options}
              loading={customerSelect.loading}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
              onChange={(id) => { void fillFromCustomer(id) }}
            />
          </Form.Item>
          <Form.Item name="title" label="合同标题"><Input placeholder="如：设备采购合同（默认 V1）" /></Form.Item>
          <ContractRegistrationFields
            form={createForm}
            mode="create"
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
                  <PaymentTermsEditor value={createPay} onChange={setCreatePay} />
                </div>
              ),
              contract_files: (
                <ContractAttachmentSlots
                  slot="contract_files"
                  pending={pendingAtts}
                  onPendingChange={setPendingAtts}
                />
              ),
              addr_mismatch_files: (
                <ContractAttachmentSlots
                  slot="addr_mismatch_files"
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
            「提交」会直接发起审批；「存草稿」仅保存，可稍后在详情页再提交审批。合同编号将自动生成。
          </div>
        </Form>
       </FieldPolicyProvider>
      </Modal>
    </div>
  )
}
