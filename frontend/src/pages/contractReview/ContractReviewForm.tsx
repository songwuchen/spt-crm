import { useEffect, useRef, useState } from 'react'
import { Button, Form, Input, Space, Table, message, Select } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import dayjs from 'dayjs'
import { contractReviewApi } from '@/api/contractReview'
import { customerApi } from '@/api/customer'
import type { Customer } from '@/api/types'
import { industryLabels } from '@/api/types'
import ContractReviewFields from '@/components/ContractReviewFields'
import AttachmentPanel from '@/components/AttachmentPanel'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import EntityCustomFields, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import { CONTRACT_REVIEW_STATUS, REVIEW_NATIVE_KEYS } from '@/constants/contractReview'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useAuthStore } from '@/stores/useAuthStore'
import { useCustomerSelect } from '@/hooks/useSelectOptions'

/** 对齐简道云「选择公司名称」linkDataMaps：从客户主数据带出行业文案 */
function formatCustomerIndustry(c: Customer): string {
  const levels = [c.industry_l1, c.industry_l2, c.industry_l3].filter(Boolean)
  if (levels.length) return levels.join('/')
  const raw = (c.industry || '').trim()
  if (!raw) return ''
  return industryLabels[raw] || raw
}

function yesNoText(v: boolean | null | undefined): string | undefined {
  if (v === true) return '是'
  if (v === false) return '否'
  return undefined
}

type ContactRow = {
  key: string
  contact_name?: string
  superior?: string
  mobile?: string
  title?: string
  email_or_ask?: string
  email?: string
  ask?: string
  address?: string
}

function newContact(): ContactRow {
  return { key: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }
}

const EMAIL_OR_ASK_OPTS = [
  { value: '邮箱', label: '邮箱' },
  { value: '请示', label: '请示' },
]

type LocState = { scrollToField?: (string | number)[] }

export default function ContractReviewForm() {
  const { id } = useParams<{ id: string }>()
  const isEdit = !!id && id !== 'new'
  const navigate = useNavigate()
  const location = useLocation()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [contacts, setContacts] = useState<ContactRow[]>([newContact()])
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)
  const [reviewId, setReviewId] = useState<string | undefined>(isEdit ? id : undefined)
  const [fillingCustomer, setFillingCustomer] = useState(false)
  const customerSelect = useCustomerSelect()
  const currentUser = useAuthStore((s) => s.user)
  usePageTitle(isEdit ? '编辑合同评审' : '新建合同评审')

  const patchContact = (key: string, patch: Partial<ContactRow>) => {
    setContacts((rows) => rows.map((x) => (x.key === key ? { ...x, ...patch } : x)))
  }

  /** 对齐简道云选「公司名称」后 linkDataMaps 回填客户信息区字段 */
  const fillFromCustomer = async (customerId?: string, fallbackName?: string) => {
    if (!customerId) {
      const rj = { ...(form.getFieldValue('review_json') || {}) } as Record<string, unknown>
      for (const k of [
        'is_foreign_trade', 'company_nature', 'industry', 'scale_fund',
        'customer_relation', 'holding_desc', 'salary_insurance',
      ]) {
        rj[k] = undefined
      }
      form.setFieldsValue({ customer_id: undefined, company_name: undefined, review_json: rj })
      return
    }
    setFillingCustomer(true)
    try {
      const c = (await customerApi.get(customerId)).data
      const rj = { ...(form.getFieldValue('review_json') || {}) } as Record<string, unknown>
      rj.is_foreign_trade = yesNoText(c.is_foreign_trade) ?? rj.is_foreign_trade
      if (c.customer_nature) rj.company_nature = c.customer_nature
      const industry = formatCustomerIndustry(c)
      if (industry) rj.industry = industry
      if (c.paid_in_capital != null && c.paid_in_capital !== undefined) {
        rj.scale_fund = Number(c.paid_in_capital)
      }
      if (c.customer_relation) rj.customer_relation = c.customer_relation
      if (c.parent_company_note) rj.holding_desc = c.parent_company_note
      if (c.wage_insurance_status) rj.salary_insurance = c.wage_insurance_status
      form.setFieldsValue({
        customer_id: customerId,
        company_name: (c.name || fallbackName || '').trim() || undefined,
        review_json: rj,
      })
    } catch {
      form.setFieldsValue({
        customer_id: customerId,
        company_name: fallbackName || form.getFieldValue('company_name'),
      })
      message.warning('客户详情加载失败，客户信息未自动带出，可手动填写')
    } finally {
      setFillingCustomer(false)
    }
  }

  useEffect(() => {
    if (!isEdit) {
      form.setFieldsValue({
        status: 'draft',
        review_type: '合同评审',
        owner_id: currentUser?.id,
        owner_name: currentUser?.real_name || currentUser?.username,
        review_json: {},
      })
      setCustomFields({})
      return
    }
    setLoading(true)
    contractReviewApi.get(id!).then((res) => {
      const d = res.data
      if (d.status !== 'draft' && d.status !== 'rejected') {
        message.warning('审批中或已提交的单据不可编辑，驳回后可由发起人修改再提交')
        navigate(`/contract-reviews/${id}`, { replace: true })
        return
      }
      setReviewId(d.id)
      const rj = d.review_json || {}
      const contactList = Array.isArray(rj.contacts) ? rj.contacts as ContactRow[] : []
      setContacts(contactList.length
        ? contactList.map((c, i) => ({ ...c, key: c.key || `c-${i}` }))
        : [newContact()])
      setCustomFields(d.custom_fields_json || {})
      // 兼容历史：feedback_members 曾存纯文本
      let feedbackMembers = rj.feedback_members as unknown
      if (typeof feedbackMembers === 'string' && feedbackMembers.trim()) {
        feedbackMembers = feedbackMembers.split(/[,，\s]+/).filter(Boolean)
      }
      form.setFieldsValue({
        ...d,
        reported_at: d.reported_at ? dayjs(d.reported_at) : undefined,
        review_json: { ...rj, contacts: undefined, feedback_members: feedbackMembers },
      })
      if (d.customer_id && d.company_name) {
        customerSelect.setInitialOption({ label: d.company_name, value: d.customer_id })
      }
      // 从详情「提交审批」跳转过来时，滚到第一个缺填项
      const scrollTo = (location.state as LocState | null)?.scrollToField
      if (scrollTo?.length) {
        setTimeout(() => {
          form.scrollToField(scrollTo, { behavior: 'smooth', block: 'center' })
          form.validateFields([scrollTo]).catch(() => { /* 标红即可 */ })
        }, 200)
      }
    }).catch(() => message.error('加载失败')).finally(() => setLoading(false))
  }, [id, isEdit]) // eslint-disable-line react-hooks/exhaustive-deps

  const buildPayload = (values: Record<string, unknown>) => {
    // validateFields 只含已注册 Form.Item；companion 姓名靠 hidden 项 + getFieldsValue(true)
    const all = form.getFieldsValue(true) as Record<string, unknown>
    const merged = { ...all, ...values }
    const review_json = {
      ...((merged.review_json as Record<string, unknown>) || {}),
      contacts: contacts.map(({ key: _k, ...rest }) => rest),
    }
    const payload: Record<string, unknown> = {
      review_json,
      custom_fields_json: customFields,
    }
    for (const k of REVIEW_NATIVE_KEYS) {
      if (k === 'review_json') continue
      if (merged[k] !== undefined) payload[k] = merged[k]
    }
    if (merged.reported_at) {
      payload.reported_at = (merged.reported_at as dayjs.Dayjs).toISOString?.()
        || merged.reported_at
    }
    return payload
  }

  const onFinish = async (values: Record<string, unknown>, andSubmit: boolean) => {
    setSaving(true)
    try {
      const payload = buildPayload(values)
      let rid = isEdit ? id! : ''
      if (isEdit) {
        await contractReviewApi.update(id!, payload)
      } else {
        const res = await contractReviewApi.create(payload)
        rid = res.data.id
      }
      if (andSubmit) {
        try {
          await contractReviewApi.submit(rid)
          message.success('已提交审批，请在「审批中心」处理待办')
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
          message.warning(msg || '已保存，但提交审批失败，请到详情页重新提交')
          navigate(`/contract-reviews/${rid}`)
          return
        }
      } else {
        message.success('已存为草稿')
      }
      navigate(`/contract-reviews/${rid}`)
    } catch {
      message.error('保存失败')
    } finally {
      setSaving(false)
    }
  }

  /** 与合同管理新建一致：校验失败时提示并滚到第一个必填项 */
  const handleSave = async (andSubmit: boolean) => {
    let values: Record<string, unknown>
    try {
      values = await form.validateFields()
    } catch (err: unknown) {
      const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
      const first = fields[0]?.errors?.[0]
      message.warning(first || (andSubmit ? '请完善必填项后再提交' : '请完善必填项后再存草稿'))
      const name = fields[0]?.name
      if (name?.length) {
        form.scrollToField(name, { behavior: 'smooth', block: 'center' })
      }
      return
    }
    const cfErr = customFieldsRef.current?.validate()
    if (cfErr) {
      message.warning(cfErr)
      return
    }
    await onFinish(values, andSubmit)
  }

  if (loading) return <div className="p-8 text-slate-400">加载中…</div>

  return (
    <div className="max-w-5xl mx-auto pb-8">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold m-0">{isEdit ? '编辑合同评审' : '新建合同评审'}</h2>
        <Space>
          <Button onClick={() => navigate(isEdit ? `/contract-reviews/${id}` : '/contract-reviews')}>取消</Button>
          <Button loading={saving} onClick={() => void handleSave(false)}>存草稿</Button>
          <Button type="primary" loading={saving} onClick={() => void handleSave(true)}>提交</Button>
        </Space>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 mb-4">
        <FieldPolicyProvider entityType="contract_review" form={form} customFieldValues={customFields}>
          <Form
            form={form}
            layout="vertical"
            scrollToFirstError={{ behavior: 'smooth', block: 'center' }}
            initialValues={{ review_json: {} }}
          >
            {/* companion 姓名：须注册为 Form.Item，否则 validateFields 不会带回 */}
            <Form.Item name="owner_name" hidden><Input /></Form.Item>
            <Form.Item name="region_manager_name" hidden><Input /></Form.Item>
            <Form.Item name="department_name" hidden><Input /></Form.Item>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 mb-4">
              <Form.Item name="status" label="状态">
                <Select options={[...CONTRACT_REVIEW_STATUS]} />
              </Form.Item>
              <Form.Item name="customer_id" label="关联客户">
                <Select
                  allowClear showSearch filterOption={false}
                  placeholder="搜索客户（选中后回填公司名称、客户信息等）"
                  options={customerSelect.options}
                  loading={customerSelect.loading || fillingCustomer}
                  onSearch={customerSelect.onSearch}
                  onDropdownVisibleChange={customerSelect.onDropdownVisibleChange}
                  onChange={(v, opt) => {
                    const o = opt as { label?: string } | undefined
                    void fillFromCustomer(v ? String(v) : undefined, o?.label)
                  }}
                />
              </Form.Item>
            </div>

            <ContractReviewFields
              form={form}
              mode={isEdit ? 'edit' : 'create'}
              slots={{
                contacts: (
                  <div>
                    <ContractSectionTitle title="联系信息" />
                    <Table
                      size="small"
                      pagination={false}
                      rowKey="key"
                      dataSource={contacts}
                      scroll={{ x: 1100 }}
                      columns={[
                        {
                          title: '联系人', dataIndex: 'contact_name', width: 120,
                          render: (v, r) => (
                            <Input value={v} onChange={(e) => patchContact(r.key, { contact_name: e.target.value })} />
                          ),
                        },
                        {
                          title: '上级领导', dataIndex: 'superior', width: 110,
                          render: (v, r) => (
                            <Input value={v} onChange={(e) => patchContact(r.key, { superior: e.target.value })} />
                          ),
                        },
                        {
                          title: '手机', dataIndex: 'mobile', width: 130,
                          render: (v, r) => (
                            <Input value={v} onChange={(e) => patchContact(r.key, { mobile: e.target.value })} />
                          ),
                        },
                        {
                          title: '职务', dataIndex: 'title', width: 100,
                          render: (v, r) => (
                            <Input value={v} onChange={(e) => patchContact(r.key, { title: e.target.value })} />
                          ),
                        },
                        {
                          title: '邮箱or请示', dataIndex: 'email_or_ask', width: 120,
                          render: (v, r) => (
                            <Select
                              allowClear
                              className="w-full"
                              options={EMAIL_OR_ASK_OPTS}
                              value={v || undefined}
                              onChange={(val) => patchContact(r.key, { email_or_ask: val })}
                            />
                          ),
                        },
                        {
                          title: '邮箱', dataIndex: 'email', width: 160,
                          render: (v, r) => (
                            <Input value={v} onChange={(e) => patchContact(r.key, { email: e.target.value })} />
                          ),
                        },
                        {
                          title: '请示', dataIndex: 'ask', width: 140,
                          render: (v, r) => (
                            <Input value={v} onChange={(e) => patchContact(r.key, { ask: e.target.value })} />
                          ),
                        },
                        {
                          title: '地址', dataIndex: 'address', width: 180,
                          render: (v, r) => (
                            <Input value={v} onChange={(e) => patchContact(r.key, { address: e.target.value })} />
                          ),
                        },
                        {
                          title: '', key: 'op', width: 48, fixed: 'right',
                          render: (_, r) => (
                            <Button type="text" danger icon={<DeleteOutlined />}
                              onClick={() => setContacts((rows) => rows.filter((x) => x.key !== r.key))} />
                          ),
                        },
                      ]}
                    />
                    <Button type="dashed" block className="mt-2" icon={<PlusOutlined />}
                      onClick={() => setContacts((rows) => [...rows, newContact()])}>
                      添加联系人
                    </Button>
                  </div>
                ),
                pricing_files: reviewId ? (
                  <AttachmentPanel bizType="contract_review_cost" bizId={reviewId} title="成本附件" />
                ) : (
                  <div className="text-sm text-slate-400">保存后可上传成本附件</div>
                ),
                review_files: reviewId ? (
                  <div className="space-y-3">
                    <AttachmentPanel bizType="contract_review" bizId={reviewId} title="附件" />
                    <AttachmentPanel bizType="contract_review_image" bizId={reviewId} title="图片" accept="image/*" />
                  </div>
                ) : (
                  <div className="text-sm text-slate-400">保存后可上传附件/图片</div>
                ),
                feedback_files: reviewId ? (
                  <div className="space-y-3">
                    <AttachmentPanel bizType="contract_review_feedback" bizId={reviewId} title="反馈附件" />
                    <AttachmentPanel bizType="contract_review_feedback_image" bizId={reviewId} title="反馈图片" accept="image/*" />
                  </div>
                ) : (
                  <div className="text-sm text-slate-400">保存后可上传反馈附件</div>
                ),
              }}
            />

            <EntityCustomFields
              ref={customFieldsRef}
              entityType="contract_review"
              value={customFields}
              onChange={setCustomFields}
            />
          </Form>
        </FieldPolicyProvider>
      </div>

      <div className="flex justify-end gap-2 mt-2 mb-6">
        <Button onClick={() => navigate(isEdit ? `/contract-reviews/${id}` : '/contract-reviews')}>取消</Button>
        <Button loading={saving} onClick={() => void handleSave(false)}>存草稿</Button>
        <Button type="primary" loading={saving} onClick={() => void handleSave(true)}>提交</Button>
      </div>
      <div className="text-center text-[12px] text-slate-400 mb-4">
        「提交」会直接发起审批；「存草稿」仅保存，可稍后在详情页再提交审批。
      </div>
    </div>
  )
}
