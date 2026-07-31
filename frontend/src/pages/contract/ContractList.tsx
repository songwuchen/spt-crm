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
import { contractStatusLabels, contractStatusColors } from '@/constants/labels'
import { formatChangeType } from '@/constants/contractRegistration'
import { usePageTitle } from '@/hooks/usePageTitle'
import { usePermission } from '@/hooks/usePermission'
import { useListView } from '@/hooks/useListView'
import ListToolbar from '@/components/list/ListToolbar'
import { fmtMoney } from '@/utils/mask'
import CustomFieldsPanel, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import ContractRegistrationFields from '@/components/ContractRegistrationFields'
import ContractAttachmentSlots, { flushPendingAttachments, type PendingAttachments } from '@/components/ContractAttachmentSlots'
import { PaymentTermsEditor, LineItemsEditor, ContractSubtableTitle } from '@/components/ContractTerms'
import { LINE_ITEMS_FIELD_ID, PAYMENT_TERMS_FIELD_ID } from '@/constants/contractDetailTables'
import dayjs from 'dayjs'


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
  const searchProjects = async (kw?: string) => {
    setProjLoading(true)
    try {
      const r = await projectApi.list({ pageNo: 1, pageSize: 20, keyword: kw || undefined })
      setProjOpts((r.data.items || []).map((p) => ({ label: `${p.name}（${p.project_code}）`, value: p.id })))
    } catch { /* ignore */ } finally { setProjLoading(false) }
  }
  /** 对齐简道云选关联后带出：商机 → 客户编号/业务人员/部门/项目名称 */
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
        try {
          const c = (await customerApi.get(p.customer_id)).data
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
  const handleCreate = async () => {
    let v
    try {
      v = await createForm.validateFields()
    } catch (err: unknown) {
      const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
      const first = fields[0]?.errors?.[0]
      message.warning(first || '请完善必填项后再提交')
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
    setCreating(true)
    try {
      const regRaw = { ...(v.registration_json || {}) } as Record<string, unknown>
      for (const [k, val] of Object.entries(regRaw)) {
        if (val && typeof val === 'object' && dayjs.isDayjs(val)) {
          regRaw[k] = val.format('YYYY-MM-DD')
        }
      }
      const fmt = (d: unknown) => (d && dayjs.isDayjs(d) ? d.format('YYYY-MM-DD') : undefined)
      const lines = createLines.filter((r) => Object.values(r).some((x) => x != null && x !== ''))
      const pays = createPay.filter((r) => Object.values(r).some((x) => x != null && x !== ''))
      const res = await contractApi.create(v.project_id, {
        title: v.title || 'V1',
        ...(v.amount_total != null ? { amount_total: v.amount_total } : {}),
        ...(fmt(v.end_date) ? { end_date: fmt(v.end_date) } : {}),
        ...(fmt(v.delivery_date) ? { delivery_date: fmt(v.delivery_date) } : {}),
        ...(fmt(v.order_date) ? { order_date: fmt(v.order_date) } : {}),
        ...(fmt(v.card_date) ? { card_date: fmt(v.card_date) } : {}),
        ...(v.drawing_no ? { drawing_no: v.drawing_no } : {}),
        ...(v.peer_contract_no ? { peer_contract_no: v.peer_contract_no } : {}),
        ...(v.acquire_method ? { acquire_method: v.acquire_method } : {}),
        ...(v.change_type ? { change_type: v.change_type } : {}),
        ...(v.assignee_id ? { assignee_id: v.assignee_id } : {}),
        ...(v.assignee_name ? { assignee_name: v.assignee_name } : {}),
        ...(v.department_id ? { department_id: v.department_id } : {}),
        ...(v.department_name ? { department_name: v.department_name } : {}),
        registration_json: Object.keys(regRaw).length ? regRaw : undefined,
        ...(lines.length ? { key_clauses_json: lines } : {}),
        ...(pays.length ? { payment_terms_json: pays } : {}),
        ...(v.content && !lines.length ? { key_clauses_json: [{ item: '合同内容', content: v.content }] } : {}),
        custom_fields_json: customFields,
      }) as any
      message.success('合同登记已创建')
      const cid = res?.data?.contract?.id
      if (cid) {
        const pendingCount = Object.values(pendingAtts).reduce((n, arr) => n + (arr?.length || 0), 0)
        if (pendingCount > 0) {
          const { ok, fail } = await flushPendingAttachments(cid, pendingAtts)
          if (fail) message.warning(`附件上传完成：成功 ${ok}，失败 ${fail}`)
          else if (ok) message.success(`已上传 ${ok} 个附件`)
        }
      }
      setCreateOpen(false)
      setCustomFields({})
      setPendingAtts({})
      if (cid) navigate(`/opportunities/${v.project_id}/contracts/${cid}`)
      else fetchData()
    } catch { message.error('创建失败') } finally { setCreating(false) }
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
        <a className="font-mono font-bold text-primary" onClick={() => navigate(
          r.project_id ? `/opportunities/${r.project_id}/contracts/${r.id}` : `/contracts/${r.id}`
        )}>{v}</a>
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
      render: (v: string) => <Tag color={contractStatusColors[v] || 'default'}>{contractStatusLabels[v] || v}</Tag>,
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
          <Select placeholder="签署状态" allowClear style={{ width: 130 }} value={filterStatus}
            onChange={(v) => { setFilterStatus(v); setPageNo(1); fetchData(1, keyword, v) }}
            options={Object.entries(contractStatusLabels).map(([k, v]) => ({ value: k, label: v }))} />
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

      <Modal title="新增合同登记" open={createOpen} onOk={handleCreate} confirmLoading={creating}
        onCancel={() => setCreateOpen(false)} okText="创建并完善" width={920} destroyOnClose
        styles={{ body: { maxHeight: '70vh', overflowY: 'auto' } }}>
       <FieldPolicyProvider entityType="contract" form={createForm} customFieldValues={customFields}>
        <Form form={createForm} layout="vertical" className="mt-3" scrollToFirstError>
          <Form.Item name="project_id" label="关联商机" rules={[{ required: true, message: '请选择关联商机' }]}>
            <Select showSearch filterOption={false} placeholder="搜索商机名称 / 编号"
              options={projOpts} loading={projLoading} onSearch={searchProjects}
              onChange={(id) => { void fillFromProject(id) }}
              onDropdownVisibleChange={(o) => { if (o && projOpts.length === 0) searchProjects() }} />
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
          <div className="text-[12px] text-slate-400">合同编号将自动生成；表单内选择的附件会在创建成功后自动上传。</div>
        </Form>
       </FieldPolicyProvider>
      </Modal>
    </div>
  )
}
