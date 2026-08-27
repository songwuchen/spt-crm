import {
  useEffect, useState, useRef, useCallback, cloneElement, isValidElement,
  type ComponentProps, type ReactElement, type ReactNode,
} from 'react'
import {
  Form, Input, Select, Button, Card, Alert, DatePicker, InputNumber,
  Radio, Checkbox, message,
} from 'antd'
import dayjs from 'dayjs'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { contactApi } from '@/api/contact'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useDataDict } from '@/hooks/useDataDict'
import { useAutoSave } from '@/hooks/useAutoSave'
import { useAuthStore } from '@/stores/useAuthStore'
import CustomFieldsPanel, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider, PolicyItem, useFieldPolicy } from '@/components/lowcode/FieldPolicy'
import RegionCascader from '@/components/RegionCascader'
import AttachmentPanel, { flushPendingAttachments } from '@/components/AttachmentPanel'
import ContactDetailEditor, {
  emptyContactRow, hasContactContent, type ContactDraftRow,
} from '@/components/ContactDetailEditor'
import {
  YES_NO,
  DEFAULT_INDUSTRIES,
  DEFAULT_LEVELS,
  DEFAULT_SCALES,
  DEFAULT_SOURCES,
  CUSTOMER_NATURE_OPTIONS,
  CUSTOMER_RELATION_OPTIONS,
  CONTACT_TITLE_LEVEL_OPTIONS,
  WAGE_INSURANCE_OPTIONS,
  FOREIGN_CUSTOMER_TYPE_OPTIONS,
  FOCUS_PRODUCT_OPTIONS,
  MAIN_PRODUCT_OPTIONS,
  INTENT_OPTIONS,
  MATCH_OPTIONS,
  CURRENCY_OPTIONS,
} from '@/constants/customerForm'

/** 简道云风格分区条 */
function JdySectionTitle({ title }: { title: string }) {
  return (
    <div className="relative mb-4 mt-6 flex items-center overflow-hidden rounded-sm bg-teal-600 px-4 py-2.5 text-white">
      <span className="relative z-10 text-[14px] font-semibold tracking-wide">{title}</span>
      <div className="pointer-events-none absolute inset-y-0 right-0 flex">
        {[0, 1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="h-full w-5 origin-bottom-right -skew-x-[28deg] bg-white/15"
            style={{ marginLeft: i === 0 ? 8 : 6 }}
          />
        ))}
      </div>
    </div>
  )
}

/** 分区标题：区内字段全部被规则隐藏时整区不渲染 */
function PolicySection({ title, fieldIds, children }: {
  title: string
  fieldIds: string[]
  children: ReactNode
}) {
  const policy = useFieldPolicy()
  if (policy.loaded && !policy.failed) {
    const anyVisible = fieldIds.some((id) => {
      const st = policy.states[id]
      return st ? st.visible : false
    })
    if (!anyVisible) return null
  }
  return (
    <>
      <JdySectionTitle title={title} />
      {children}
    </>
  )
}

function PolicySectionVisibleHint({ fieldIds, children }: { fieldIds: string[]; children: ReactNode }) {
  const policy = useFieldPolicy()
  if (policy.loaded && !policy.failed) {
    const anyVisible = fieldIds.some((id) => policy.states[id]?.visible)
    if (!anyVisible) return null
  }
  return <>{children}</>
}

const SMART_FIELD_IDS = [
  'legal_person', 'headcount', 'smart_industry_category',
  'annual_run_days', 'floor_area', 'financial_status', 'business_status',
  'annual_power_usage', 'daily_operate_hours',
]
const INVOICE_FIELD_IDS = [
  'taxpayer_id', 'invoice_address_phone', 'bank_account', 'is_company_customer',
]
const FOREIGN_FIELD_IDS = [
  'region', 'country', 'short_name', 'foreign_customer_code', 'foreign_customer_type',
  'focus_product', 'customer_email', 'main_products_json', 'website', 'source',
]
const DOMESTIC_ARCHIVE_IDS = [
  'registered_capital', 'paid_in_capital', 'founded_year', 'parent_company_note',
  'customer_nature', 'customer_relation', 'level', 'primary_contact_title',
  'wage_insurance_status',
]

function OwnerSelect({ userSelect, ...controlProps }: {
  userSelect: ReturnType<typeof useUserSelect>
} & ComponentProps<typeof Select>) {
  return (
    <Select
      {...controlProps}
      placeholder="选择业务员"
      allowClear
      showSearch
      filterOption={false}
      loading={userSelect.loading}
      options={userSelect.options}
      onSearch={userSelect.onSearch}
      onDropdownVisibleChange={userSelect.onDropdownVisibleChange}
    />
  )
}

/** 业务页下拉：优先已发布目录/设计器 options，其次数据字典，最后常量兜底（须在 FieldPolicyProvider 内）。
 * 必须把 Form.Item 注入的 value/onChange 透传给真实控件，否则单选看起来选中了表单仍为空。 */
function ChoiceOptionsBridge({
  fieldId, fallback, dictOptions, children, ...controlProps
}: {
  fieldId: string
  fallback: { label: string; value: string }[]
  dictOptions?: { label: string; value: string }[]
  children: (opts: { label: string; value: string }[]) => ReactElement
} & Record<string, unknown>) {
  const policy = useFieldPolicy()
  const fd = policy.nativeFields.find((f) => f.id === fieldId)
  let opts = fallback
  if (fd?.options?.length) {
    opts = fd.options.map((o) => ({ label: String(o.label ?? o.value), value: String(o.value) }))
  } else if (dictOptions?.length) {
    opts = dictOptions
  }
  const child = children(opts)
  if (isValidElement(child)) {
    return cloneElement(child, controlProps)
  }
  return child
}

export default function CustomerForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const toPool = searchParams.get('pool') === '1'
  const reviseTaskId = searchParams.get('task')
  const reviseWfId = searchParams.get('wf')
  const isWfRevise = !!(reviseTaskId && reviseWfId)
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑客户' : toPool ? '新建公海客户' : '新建客户')

  const industryDict = useDataDict('industry', DEFAULT_INDUSTRIES)
  const industryMap = Object.fromEntries(industryDict.options.map((o) => [o.value, o.label]))
  const levelDict = useDataDict('customer_level', DEFAULT_LEVELS)
  const scaleDict = useDataDict('scale_level', DEFAULT_SCALES)
  const sourceDict = useDataDict('customer_source', DEFAULT_SOURCES)

  const currentUser = useAuthStore((s) => s.user)
  const userSelect = useUserSelect()
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)
  const [createdAtDisplay, setCreatedAtDisplay] = useState(dayjs().format('YYYY-MM-DD'))
  const [contactRows, setContactRows] = useState<ContactDraftRow[]>([emptyContactRow()])
  const [initialContactIds, setInitialContactIds] = useState<string[]>([])
  const [orgChartPending, setOrgChartPending] = useState<File[]>([])

  const [similarCustomers, setSimilarCustomers] = useState<{
    id: string; name: string; short_name?: string; industry?: string
    owner_name?: string; match_type?: string; match_phone?: string; match_contact?: string
  }[]>([])
  const dupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [reviewStatus, setReviewStatus] = useState<string | undefined>()

  const isForeignTrade = Form.useWatch('is_foreign_trade', form)
  const canSubmitApproval = !toPool && (!isEdit || reviewStatus === 'draft' || reviewStatus === 'rejected')
  const editLocked = false

  const checkDuplicates = useCallback((name?: string, phone?: string) => {
    if (dupTimerRef.current) clearTimeout(dupTimerRef.current)
    if ((!name || name.length < 2) && (!phone || phone.length < 4)) { setSimilarCustomers([]); return }
    dupTimerRef.current = setTimeout(async () => {
      try {
        const res = await customerApi.checkSimilar({
          name: name && name.length >= 2 ? name : undefined,
          phone: phone && phone.length >= 4 ? phone : undefined,
          exclude_id: id,
        })
        setSimilarCustomers(res.data || [])
      } catch { /* ignore */ }
    }, 500)
  }, [id])

  const { restoreDraft, clearDraft, markDirty } = useAutoSave(`customer_form_${id || 'new'}`, form)

  useEffect(() => {
    if (id) {
      customerApi.get(id).then(async (res) => {
        const d: Record<string, unknown> = { ...res.data }
        const rs = res.data.review_status as string | undefined
        if (rs === 'pending') {
          try {
            const { workflowApi } = await import('@/api/lowcodeWorkflow')
            const wf = await workflowApi.byBiz({ biz_type: 'customer', biz_id: id! })
            if (wf.data?.status === 'running') {
              message.warning('审批中的客户不可编辑')
              navigate(`/customers/${id}`, { replace: true })
              return
            }
          } catch { /* 无流程则允许编辑 */ }
        }
        if (d.expected_purchase_date) d.expected_purchase_date = dayjs(d.expected_purchase_date as string)
        form.setFieldsValue(d)
        setCustomFields((res.data.custom_fields_json as Record<string, unknown>) || {})
        setReviewStatus(rs)
        if (res.data.created_at) {
          setCreatedAtDisplay(dayjs(res.data.created_at as string).format('YYYY-MM-DD'))
        }
        if (res.data.owner_id && res.data.owner_name) {
          userSelect.setInitialOption({ label: res.data.owner_name, value: res.data.owner_id })
        }
      }).catch(() => message.error('加载客户数据失败'))
      contactApi.list(id).then((res) => {
        const list = res.data || []
        if (!list.length) return
        setContactRows(list.map((c) => ({
          _key: c.id,
          id: c.id,
          name: c.name,
          department: c.department || '',
          title: c.title || '',
          phone: c.phone || c.mobile || '',
        })))
        setInitialContactIds(list.map((c) => c.id))
      }).catch(() => { /* ignore */ })
    } else {
      const restored = restoreDraft()
      if (restored) {
        message.info('已恢复上次未保存的草稿')
        const epd = form.getFieldValue('expected_purchase_date')
        if (epd && typeof epd === 'string') form.setFieldValue('expected_purchase_date', dayjs(epd))
      } else if (currentUser && !toPool) {
        form.setFieldsValue({ owner_id: currentUser.id })
        userSelect.setInitialOption({
          label: currentUser.real_name || currentUser.username,
          value: currentUser.id,
        })
      }
    }
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const syncContacts = async (customerId: string) => {
    const filled = contactRows.filter((r) => (r.name || '').trim())
    const keepIds = new Set(filled.filter((r) => r.id).map((r) => r.id!))
    for (const cid of initialContactIds) {
      if (!keepIds.has(cid)) {
        try { await contactApi.delete(customerId, cid) } catch { /* ignore */ }
      }
    }
    for (const row of filled) {
      const body = {
        name: (row.name || '').trim(),
        department: row.department || undefined,
        title: row.title || undefined,
        phone: row.phone || undefined,
      }
      try {
        if (row.id) await contactApi.update(customerId, row.id, body)
        else await contactApi.create(customerId, body)
      } catch { /* ignore single row */ }
    }
  }

  const onFinish = async (values: Record<string, unknown>, andSubmit: boolean) => {
    if (andSubmit) {
      const cfError = customFieldsRef.current?.validate()
      if (cfError) {
        message.error(cfError)
        return
      }
    }
    setLoading(true)
    try {
      const payload = {
        ...values,
        owner_id: toPool ? null : (values.owner_id || null),
        custom_fields_json: customFields,
      } as Record<string, unknown>
      if (payload.expected_purchase_date) {
        payload.expected_purchase_date = dayjs(payload.expected_purchase_date as dayjs.Dayjs).format('YYYY-MM-DD')
      }
      let customerId = id
      if (isEdit) {
        await customerApi.update(id!, payload)
        if (andSubmit && (canSubmitApproval || isWfRevise)) {
          try {
            if (isWfRevise && reviseTaskId) {
              const { workflowApi } = await import('@/api/lowcodeWorkflow')
              await workflowApi.act(reviseTaskId, { action: 'resubmit', opinion: '修改后重新提交' })
              message.success('已重新提交审批，请在详情页查看流程动态')
            } else {
              await customerApi.submitReview(id!)
              message.success('已提交审批，请在详情页查看流程动态')
            }
          } catch (err: unknown) {
            const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
            message.warning(msg || '已保存，但提交审批失败，请到详情页重新提交')
            navigate(`/customers/${id}`)
            return
          }
        } else {
          message.success(canSubmitApproval ? '已存为草稿' : '客户已更新')
        }
      } else if (toPool) {
        const res = await customerApi.create(payload, true)
        customerId = res.data.id
        message.success('已新建到公海')
      } else if (andSubmit) {
        const res = await customerApi.create(payload)
        customerId = res.data.id
        message.success(res?.data?.review_status === 'pending'
          ? '已提交审批，等待审核'
          : '客户已创建')
      } else {
        const res = await customerApi.create({ ...payload, as_draft: true })
        customerId = res.data.id
        message.success('已存为草稿')
      }
      if (customerId && (hasContactContent(contactRows) || initialContactIds.length)) {
        await syncContacts(customerId)
      }
      if (customerId && orgChartPending.length) {
        const { ok, fail } = await flushPendingAttachments(customerId, [
          { bizType: 'customer_org_chart', files: orgChartPending },
        ])
        if (fail) message.warning(`客户已保存，组织架构图上传失败 ${fail} 个`)
        else if (ok) setOrgChartPending([])
      }
      clearDraft()
      navigate(toPool ? '/customers/pool' : (customerId ? `/customers/${customerId}` : '/customers'))
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async (andSubmit: boolean) => {
    if (editLocked) {
      message.warning('审批中不可编辑，请到详情页查看流程')
      return
    }
    let values: Record<string, unknown>
    try {
      if (andSubmit || !canSubmitApproval) {
        values = await form.validateFields()
      } else {
        await form.validateFields(['name'])
        values = form.getFieldsValue(true)
      }
    } catch (err: unknown) {
      const fields = (err as { errorFields?: { name: (string | number)[]; errors: string[] }[] })?.errorFields || []
      const first = fields[0]?.errors?.[0]
      message.warning(first || (andSubmit ? '请完善必填项后再提交' : '请填写客户名称后再存草稿'))
      const name = fields[0]?.name
      if (name?.length) form.scrollToField(name)
      return
    }
    await onFinish(values, andSubmit)
  }

  const ownerField = !toPool ? (
    <PolicyItem name="owner_id" label="业务员" rules={[{ required: true, message: '请选择业务员' }]}>
      <OwnerSelect userSelect={userSelect} />
    </PolicyItem>
  ) : null

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">{isEdit ? '编辑客户' : '新建客户'}</h2>
      {!toPool && !isEdit && (
        <p className="text-sm text-slate-500 mb-3">可先存草稿，完善后提交客户信息审批；驳回后不可再提交。</p>
      )}
      <Card>
        <FieldPolicyProvider entityType="customer" form={form} customFieldValues={customFields}>
          <Form
            form={form}
            layout="vertical"
            onValuesChange={markDirty}
            className="max-w-6xl"
            initialValues={{ is_foreign_trade: false, is_smart_filing: false, need_info_distribute: false }}
            disabled={editLocked}
          >
            {/* 顶栏：编号 | 日期 | 智能化 | 外贸 | 信息分发 */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-x-4">
              <PolicyItem name="customer_code" label="客户编号">
                <Input placeholder="自动生成无需填写" disabled={!isEdit} readOnly={!isEdit} />
              </PolicyItem>
              <Form.Item label="日期时间">
                <Input value={createdAtDisplay} disabled readOnly />
              </Form.Item>
              <PolicyItem name="is_smart_filing" label="是否智能化客户信息备案" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={YES_NO} />
              </PolicyItem>
              <PolicyItem name="is_foreign_trade" label="是否外贸客户" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={YES_NO} />
              </PolicyItem>
              <PolicyItem name="need_info_distribute" label="信息分发-客户" rules={[{ required: true, message: '请选择' }]}>
                <Radio.Group options={YES_NO} />
              </PolicyItem>
            </div>

            <PolicyItem name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
              <Input placeholder="请输入客户全称" onChange={(e) => checkDuplicates(e.target.value)} />
            </PolicyItem>
            {similarCustomers.length > 0 && (
              <Alert
                type="warning"
                showIcon
                className="mb-4"
                message={`发现 ${similarCustomers.length} 个疑似重复客户`}
                description={(
                  <div className="mt-1 space-y-1">
                    {similarCustomers.map((c) => (
                      <div key={c.id} className="flex items-center gap-2 text-sm">
                        <a onClick={() => navigate(`/customers/${c.id}`)} className="text-primary font-bold hover:underline">{c.name}</a>
                        {c.match_type === 'phone' && (
                          <span className="text-orange-500 text-sm bg-orange-50 px-1.5 py-0.5 rounded">
                            电话匹配: {c.match_contact} {c.match_phone}
                          </span>
                        )}
                        {c.match_type === 'name' && (
                          <span className="text-blue-500 text-sm bg-blue-50 px-1.5 py-0.5 rounded">名称匹配</span>
                        )}
                        {c.industry && <span className="text-slate-400 text-sm">{industryMap[c.industry] || c.industry}</span>}
                        {c.owner_name && <span className="text-slate-400 text-sm">负责人: {c.owner_name}</span>}
                      </div>
                    ))}
                  </div>
                )}
              />
            )}

            {/* 内贸：注册资金 | 实缴资本 | 成立年份（3 列） */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-4">
              <PolicyItem name="registered_capital" label="注册资金（万元）">
                <InputNumber className="w-full" min={0} placeholder="万元" controls={false} />
              </PolicyItem>
              <PolicyItem name="paid_in_capital" label="实缴资本（万元）">
                <InputNumber className="w-full" min={0} placeholder="万元" controls={false} />
              </PolicyItem>
              <PolicyItem
                name="founded_year"
                label="成立年份"
                getValueFromEvent={(d: dayjs.Dayjs | null) => (d ? d.year() : undefined)}
                getValueProps={(y: number | undefined) => ({
                  value: y ? dayjs(String(y), 'YYYY') : undefined,
                })}
              >
                <DatePicker picker="year" className="w-full" placeholder="选择年份" />
              </PolicyItem>
            </div>

            <Form.Item
              label="地址"
              required
              className="mb-1"
            >
              <Form.Item
                noStyle
                shouldUpdate={(prev, curr) =>
                  prev.province !== curr.province
                  || prev.city !== curr.city
                  || prev.district !== curr.district
                  || prev.is_foreign_trade !== curr.is_foreign_trade
                }
              >
                {({ getFieldValue, setFieldsValue }) => (
                  <RegionCascader
                    value={{
                      province: getFieldValue('province'),
                      city: getFieldValue('city'),
                      district: getFieldValue('district'),
                    }}
                    placeholder={
                      isForeignTrade
                        ? '海外客户请选：海外 / 其它 / 其它（也可选台湾/香港/澳门）'
                        : '选择省/市/区县'
                    }
                    onChange={(v) => {
                      setFieldsValue({
                        province: v.province, city: v.city, district: v.district, region_code: v.regionCode,
                      })
                      markDirty()
                    }}
                  />
                )}
              </Form.Item>
            </Form.Item>
            <Form.Item name="province" rules={[{ required: true, message: '请选择省/市/区县' }]} hidden><Input /></Form.Item>
            <Form.Item name="city" hidden><Input /></Form.Item>
            <Form.Item name="district" hidden><Input /></Form.Item>
            <Form.Item name="region_code" hidden><Input /></Form.Item>
            <PolicyItem name="address" rules={[{ required: true, message: '请填写详细地址' }]}>
              <Input.TextArea rows={2} placeholder="请填写详细地址" />
            </PolicyItem>

            <PolicyItem name="parent_company_note" label="母公司或者控股公司情况及性质说明">
              <Input.TextArea rows={2} placeholder="母公司/控股情况说明" />
            </PolicyItem>

            {/* 内贸分类：通栏单选（对齐简道云字段顺序） */}
            <PolicyItem name="industry" label="所属行业" rules={[{ required: true, message: '请选择所属行业' }]}>
              <ChoiceOptionsBridge fieldId="industry" fallback={DEFAULT_INDUSTRIES} dictOptions={industryDict.options}>
                {(opts) => <Radio.Group options={opts} />}
              </ChoiceOptionsBridge>
            </PolicyItem>
            <PolicyItem name="customer_nature" label="客户性质">
              <ChoiceOptionsBridge fieldId="customer_nature" fallback={CUSTOMER_NATURE_OPTIONS}>
                {(opts) => <Radio.Group options={opts} />}
              </ChoiceOptionsBridge>
            </PolicyItem>
            <PolicyItem name="customer_relation" label="客户关系">
              <ChoiceOptionsBridge fieldId="customer_relation" fallback={CUSTOMER_RELATION_OPTIONS}>
                {(opts) => <Radio.Group options={opts} />}
              </ChoiceOptionsBridge>
            </PolicyItem>
            <PolicyItem name="level" label="客户类型" tooltip="价值等级 A/B/C/D">
              <ChoiceOptionsBridge fieldId="level" fallback={DEFAULT_LEVELS} dictOptions={levelDict.options}>
                {(opts) => <Radio.Group options={opts} />}
              </ChoiceOptionsBridge>
            </PolicyItem>
            <PolicyItem name="primary_contact_title" label="主联系人职位">
              <ChoiceOptionsBridge fieldId="primary_contact_title" fallback={CONTACT_TITLE_LEVEL_OPTIONS}>
                {(opts) => <Radio.Group options={opts} />}
              </ChoiceOptionsBridge>
            </PolicyItem>
            <PolicyItem name="wage_insurance_status" label="客户工资及保险情况">
              <ChoiceOptionsBridge fieldId="wage_insurance_status" fallback={WAGE_INSURANCE_OPTIONS}>
                {(opts) => <Radio.Group options={opts} />}
              </ChoiceOptionsBridge>
            </PolicyItem>

            {isForeignTrade !== true && ownerField}

            <PolicySectionVisibleHint fieldIds={DOMESTIC_ARCHIVE_IDS}>
              <ContactDetailEditor value={contactRows} onChange={setContactRows} />
            </PolicySectionVisibleHint>

            {/* 国外客户信息：4 列 */}
            <PolicySection title="国外客户信息" fieldIds={FOREIGN_FIELD_IDS}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-4">
                <PolicyItem name="region" label="国家/地区">
                  <Input placeholder="如：北美" />
                </PolicyItem>
                {isForeignTrade === true && ownerField}
                <PolicyItem name="short_name" label="客户简称">
                  <Input placeholder="外贸客户简称" />
                </PolicyItem>
                <PolicyItem name="foreign_customer_code" label="客户代码">
                  <Input placeholder="外贸客户代码" />
                </PolicyItem>
                <PolicyItem name="country" label="国别">
                  <Input placeholder="如：美国" />
                </PolicyItem>
                <PolicyItem name="foreign_customer_type" label="客户类型">
                  <ChoiceOptionsBridge fieldId="foreign_customer_type" fallback={FOREIGN_CUSTOMER_TYPE_OPTIONS}>
                    {(opts) => <Select placeholder="请选择" allowClear options={opts} />}
                  </ChoiceOptionsBridge>
                </PolicyItem>
                <PolicyItem name="focus_product" label="关注产品">
                  <ChoiceOptionsBridge fieldId="focus_product" fallback={FOCUS_PRODUCT_OPTIONS}>
                    {(opts) => <Select placeholder="请选择" allowClear options={opts} showSearch />}
                  </ChoiceOptionsBridge>
                </PolicyItem>
                <PolicyItem name="source" label="客户来源">
                  <ChoiceOptionsBridge fieldId="source" fallback={DEFAULT_SOURCES} dictOptions={sourceDict.options}>
                    {(opts) => (
                      <Select placeholder="请选择来源" allowClear options={opts} loading={sourceDict.loading} />
                    )}
                  </ChoiceOptionsBridge>
                </PolicyItem>
                <PolicyItem name="customer_email" label="邮箱" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
                  <Input placeholder="客户邮箱" />
                </PolicyItem>
                <PolicyItem name="website" label="主页" className="sm:col-span-2" rules={[{ type: 'url', message: '请输入正确的网址' }]}>
                  <Input placeholder="https://" />
                </PolicyItem>
              </div>
              <PolicyItem name="main_products_json" label="主营产品">
                <ChoiceOptionsBridge fieldId="main_products_json" fallback={MAIN_PRODUCT_OPTIONS}>
                  {(opts) => <Checkbox.Group options={opts} className="flex flex-wrap gap-x-4 gap-y-2" />}
                </ChoiceOptionsBridge>
              </PolicyItem>
            </PolicySection>

            <PolicySection title="智能化项目客户信息备案" fieldIds={SMART_FIELD_IDS}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-4">
                <PolicyItem name="legal_person" label="企业法人"><Input /></PolicyItem>
                <PolicyItem name="headcount" label="企业员工人数">
                  <InputNumber className="w-full" min={0} placeholder="人数" />
                </PolicyItem>
                <PolicyItem name="smart_industry_category" label="所属行业分类">
                  <Input placeholder="行业分类说明" />
                </PolicyItem>
                <PolicyItem name="annual_run_days" label="年运行天数"><Input /></PolicyItem>
                <PolicyItem name="floor_area" label="占地面积"><Input /></PolicyItem>
                <PolicyItem name="annual_power_usage" label="年用电量"><Input /></PolicyItem>
                <PolicyItem name="daily_operate_hours" label="日运营小时数"><Input /></PolicyItem>
              </div>
              <PolicyItem name="financial_status" label="企业财务状况">
                <Input.TextArea rows={2} />
              </PolicyItem>
              <PolicyItem name="business_status" label="企业经营状况">
                <Input.TextArea rows={2} />
              </PolicyItem>
              <div className="mb-4">
                <AttachmentPanel
                  bizType="customer_org_chart"
                  bizId={id}
                  title="企业组织架构图"
                  accept="image/*"
                  pendingFiles={orgChartPending}
                  onPendingChange={setOrgChartPending}
                />
              </div>
            </PolicySection>

            <PolicySection title="开票信息" fieldIds={INVOICE_FIELD_IDS}>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-4">
                <PolicyItem name="taxpayer_id" label="纳税人识别号">
                  <Input placeholder="统一社会信用代码 / 税号" />
                </PolicyItem>
                <PolicyItem name="bank_account" label="开户行帐号">
                  <Input placeholder="开户行及账号" />
                </PolicyItem>
                <PolicyItem name="invoice_address_phone" label="地址电话" className="sm:col-span-2">
                  <Input placeholder="开票地址及电话" />
                </PolicyItem>
                <PolicyItem name="is_company_customer" label="是否公司客户">
                  <Radio.Group options={YES_NO} />
                </PolicyItem>
              </div>
            </PolicySection>

            <JdySectionTitle title="其他" />
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-4">
              <PolicyItem name="expected_purchase_date" label="预计采购时间">
                <DatePicker className="w-full" placeholder="选择预计采购日期" />
              </PolicyItem>
              <Form.Item name="intent_level" label="采购意向类别" tooltip="留空则由预计采购时间自动推算">
                <Select placeholder="留空自动推算" allowClear options={INTENT_OPTIONS} />
              </Form.Item>
              <PolicyItem name="budget_amount" label="客户预算(元)">
                <InputNumber<number>
                  className="w-full"
                  min={0}
                  step={1000}
                  placeholder="预算金额"
                  controls={false}
                  formatter={(v) => (v === undefined || v === null ? '' : `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ','))}
                  parser={(v) => {
                    const s = String(v ?? '').replace(/,/g, '')
                    return (s === '' ? undefined : Number(s)) as unknown as number
                  }}
                />
              </PolicyItem>
              <Form.Item name="need_match_level" label="需求匹配程度">
                <Select placeholder="选择匹配程度" allowClear options={MATCH_OPTIONS} />
              </Form.Item>
              <PolicyItem name="postal_code" label="邮政编码"><Input placeholder="邮编" /></PolicyItem>
              <Form.Item name="currency" label="币种">
                <Select placeholder="默认人民币 CNY" allowClear options={CURRENCY_OPTIONS} />
              </Form.Item>
              <PolicyItem name="scale_level" label="企业规模">
                <ChoiceOptionsBridge fieldId="scale_level" fallback={DEFAULT_SCALES} dictOptions={scaleDict.options}>
                  {(opts) => (
                    <Select placeholder="请选择" allowClear options={opts} loading={scaleDict.loading} />
                  )}
                </ChoiceOptionsBridge>
              </PolicyItem>
              {isEdit && (
                <Form.Item name="status" label="状态">
                  <Select options={[
                    { label: '活跃', value: 'active' },
                    { label: '不活跃', value: 'inactive' },
                  ]}
                  />
                </Form.Item>
              )}
            </div>
            <PolicyItem name="demand" label="核心需求">
              <Input.TextArea rows={2} placeholder="客户的核心需求" />
            </PolicyItem>
            <Form.Item name="tags_json" label="标签">
              <Select mode="tags" placeholder="输入标签后回车添加" tokenSeparators={[',']} />
            </Form.Item>
            <PolicyItem name="remark" label="备注">
              <Input.TextArea rows={3} placeholder="备注信息" />
            </PolicyItem>

            {toPool && (
              <Alert
                type="info"
                showIcon
                className="mb-4"
                message="新建到公海"
                description="该客户将进入公海池（无负责人），后续可由销售员领取或由管理员分配。"
              />
            )}

            <div className="mb-4">
              <CustomFieldsPanel ref={customFieldsRef} entityType="customer" values={customFields} onChange={setCustomFields} />
            </div>
            <Form.Item>
              {toPool ? (
                <Button type="primary" loading={loading} onClick={() => void handleSave(false)}>保存到公海</Button>
              ) : canSubmitApproval ? (
                <>
                  <Button type="primary" loading={loading} onClick={() => void handleSave(true)}>提交审批</Button>
                  <Button className="ml-2" loading={loading} onClick={() => void handleSave(false)}>存草稿</Button>
                </>
              ) : (
                <Button type="primary" loading={loading} disabled={editLocked} onClick={() => void handleSave(false)}>保存</Button>
              )}
              <Button className="ml-2" onClick={() => navigate(toPool ? '/customers/pool' : '/customers')}>取消</Button>
            </Form.Item>
          </Form>
        </FieldPolicyProvider>
      </Card>
    </div>
  )
}
