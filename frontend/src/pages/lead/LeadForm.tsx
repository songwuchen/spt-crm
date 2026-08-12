import {
  useEffect, useRef, useState, cloneElement, isValidElement,
  type ReactElement, type ReactNode,
} from 'react'
import { Form, Input, Select, Button, DatePicker, Radio, message } from 'antd'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { leadApi } from '@/api/lead'
import EntityCustomFields, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider, PolicyItem, useFieldPolicy } from '@/components/lowcode/FieldPolicy'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useDataDict } from '@/hooks/useDataDict'
import RegionCascader from '@/components/RegionCascader'
import DepartmentSelect from '@/components/DepartmentSelect'
import AttachmentPanel, { flushPendingAttachments } from '@/components/AttachmentPanel'
import { useAuthStore } from '@/stores/useAuthStore'
import {
  YES_NO,
  CATEGORY_OPTIONS,
  COUNTRY_OPTIONS,
  CUSTOMER_TYPE_OPTIONS,
  INDUSTRY_OPTIONS,
  BID_RESULT_OPTIONS,
  BID_FAIL_REASON_OPTIONS,
  ENTRUST_STATUS_OPTIONS,
  PROJECT_ACTIVITY_OPTIONS,
  REPORT_PROJECT_STATUS_OPTIONS,
  DEFAULT_LEAD_SOURCES,
  FEEDBACK_FIELD_IDS,
} from '@/constants/leadForm'

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
  // 字典优先：客户类型/行业等存的是 dict_code，目录静态 options 多为中文展示
  if (dictOptions?.length) {
    opts = dictOptions
  } else if (fd?.options?.length) {
    opts = fd.options.map((o) => ({ label: String(o.label ?? o.value), value: String(o.value) }))
  }
  const child = children(opts)
  if (isValidElement(child)) {
    return cloneElement(child, controlProps)
  }
  return child
}

export default function LeadForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const [pendingFiles, setPendingFiles] = useState<File[]>([])
  const [reviewStatus, setReviewStatus] = useState<string | undefined>()
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)
  const isEdit = !!id
  const canSubmitApproval = !isEdit || reviewStatus === 'draft' || reviewStatus === 'rejected'
  usePageTitle(isEdit ? '编辑线索' : '新建线索')

  const sourceDict = useDataDict('lead_source', DEFAULT_LEAD_SOURCES)
  const industryDict = useDataDict('industry', INDUSTRY_OPTIONS)
  const customerTypeDict = useDataDict('customer_type', CUSTOMER_TYPE_OPTIONS)

  const reporterSelect = useUserSelect()
  const ownerSelect = useUserSelect()
  const currentUser = useAuthStore((s) => s.user)
  const countryType = Form.useWatch('country_type', form)

  useEffect(() => {
    if (id) {
      leadApi.get(id).then(async (res) => {
        const d = res.data as Record<string, unknown>
        if (d.status === 'qualified' || d.status === 'discarded') {
          message.warning(d.status === 'qualified' ? '已转化的线索不可编辑' : '已废弃的线索不可编辑')
          navigate(`/leads/${id}`, { replace: true })
          return
        }
        if (d.review_status === 'pending') {
          try {
            const { workflowApi } = await import('@/api/lowcodeWorkflow')
            const wf = await workflowApi.byBiz({ biz_type: 'lead', biz_id: id! })
            if (wf.data?.status === 'running') {
              message.warning('审核中的线索不可编辑，驳回后可由发起人修改再提交')
              navigate(`/leads/${id}`, { replace: true })
              return
            }
          } catch { /* 无流程则允许编辑 */ }
        }
        form.setFieldsValue({
          ...d,
          biz_date: d.biz_date ? dayjs(d.biz_date as string) : undefined,
          reported_at: d.reported_at ? dayjs(d.reported_at as string) : undefined,
          entrust_issued_at: d.entrust_issued_at ? dayjs(d.entrust_issued_at as string) : undefined,
        })
        setReviewStatus(d.review_status as string | undefined)
        setCustomFields((d.custom_fields_json as Record<string, unknown>) || {})
        if (d.reporter_id && d.reporter_name) {
          reporterSelect.setInitialOption({ label: String(d.reporter_name), value: String(d.reporter_id) })
        }
        if (d.owner_id && d.owner_name) {
          ownerSelect.setInitialOption({ label: String(d.owner_name), value: String(d.owner_id) })
        }
      }).catch(() => message.error('加载线索数据失败'))
    } else {
      form.setFieldsValue({
        reported_at: dayjs(),
        has_internal_conflict: '否',
        country_type: 'domestic',
        category: 'self_reported',
      })
      if (currentUser) {
        const label = currentUser.real_name || currentUser.username
        form.setFieldsValue({ reporter_id: currentUser.id })
        reporterSelect.setInitialOption({ label, value: currentUser.id })
      }
    }
  }, [id, currentUser])

  const onFinish = async (values: Record<string, unknown>, andSubmit: boolean) => {
    const cfError = customFieldsRef.current?.validate()
    if (cfError) {
      message.error(cfError)
      return
    }
    setLoading(true)
    try {
      const payload = {
        ...values,
        biz_date: values.biz_date ? (values.biz_date as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        reported_at: values.reported_at ? (values.reported_at as dayjs.Dayjs).toISOString() : undefined,
        entrust_issued_at: values.entrust_issued_at
          ? (values.entrust_issued_at as dayjs.Dayjs).toISOString()
          : undefined,
        custom_fields_json: customFields,
      }
      let leadId = id
      if (isEdit) {
        await leadApi.update(id!, payload)
        if (andSubmit && canSubmitApproval) {
          try {
            await leadApi.submitReview(id!)
            message.success('已提交审批，请在详情页查看流程动态')
          } catch (err: unknown) {
            const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
            message.warning(msg || '已保存，但提交审批失败，请到详情页重新提交')
            navigate(`/leads/${id}`)
            return
          }
        } else {
          message.success(canSubmitApproval ? '已存为草稿' : '线索已更新')
        }
      } else if (andSubmit) {
        const res = await leadApi.create(payload)
        leadId = res?.data?.id
        message.success(res?.data?.review_status === 'pending'
          ? '已提交审批，等待信息情报部审核'
          : '线索已创建')
      } else {
        const res = await leadApi.create({ ...payload, as_draft: true })
        leadId = res?.data?.id
        message.success('已存为草稿')
      }
      if (leadId && pendingFiles.length > 0) {
        await flushPendingAttachments('lead', leadId, pendingFiles)
      }
      navigate(leadId ? `/leads/${leadId}` : '/leads')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

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
    await onFinish(values, andSubmit)
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          {isEdit ? '编辑线索' : '新建线索'}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {isEdit
            ? '编辑申报信息与跟进反馈；评估结论请在情报审批中填写'
            : '填写申报信息后可存草稿，或直接提交审批由信息情报部填写评估结论'}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
        <FieldPolicyProvider entityType="lead" form={form} customFieldValues={customFields}>
          <Form
            form={form}
            layout="vertical"
            size="middle"
            className="w-full [&_.ant-form-item]:mb-3"
          >
            <JdySectionTitle title="申报信息（创建时填写）" />
            <p className="mb-3 -mt-2 text-xs text-slate-400">
              对应简道云「发起流程」：来源、项目、公司、地址、冲突、行业、人员、项目动态、备注1 等
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-x-4">
              <PolicyItem name="category" label="来源" rules={[{ required: true, message: '请选择来源' }]}>
                <ChoiceOptionsBridge fieldId="category" fallback={CATEGORY_OPTIONS}>
                  {(opts) => <Radio.Group options={opts} />}
                </ChoiceOptionsBridge>
              </PolicyItem>
              <PolicyItem name="title" label="项目名称" className="sm:col-span-2 xl:col-span-3" rules={[{ required: true, message: '请填写项目名称' }]}>
                <Input placeholder="请输入项目名称" />
              </PolicyItem>

              <PolicyItem name="company_name" label="公司名称" rules={[{ required: true, message: '请填写公司名称' }]}>
                <Input placeholder="请输入公司名称" />
              </PolicyItem>
              <PolicyItem name="customer_type" label="客户类型" rules={[{ required: true, message: '请选择客户类型' }]}>
                <ChoiceOptionsBridge fieldId="customer_type" fallback={CUSTOMER_TYPE_OPTIONS} dictOptions={customerTypeDict.options}>
                  {(opts) => (
                    <Select placeholder="请选择客户类型" allowClear showSearch optionFilterProp="label"
                      options={opts} loading={customerTypeDict.loading} />
                  )}
                </ChoiceOptionsBridge>
              </PolicyItem>

              <PolicyItem name="country_type" label="国别" rules={[{ required: true, message: '请选择国别' }]}>
                <ChoiceOptionsBridge fieldId="country_type" fallback={COUNTRY_OPTIONS}>
                  {(opts) => <Radio.Group options={opts} />}
                </ChoiceOptionsBridge>
              </PolicyItem>
              {countryType === 'overseas' ? (
                <PolicyItem name="country_name" label="国家"
                  rules={[{ required: true, message: '请填写国家' }]}>
                  <Input placeholder="请输入国家名称" />
                </PolicyItem>
              ) : (
                <Form.Item label="项目地址（省/市/区县）" required className="sm:col-span-1">
                  <Form.Item
                    noStyle
                    shouldUpdate={(prev, curr) =>
                      prev.province !== curr.province || prev.city !== curr.city || prev.district !== curr.district
                    }
                  >
                    {({ getFieldValue, setFieldsValue }) => (
                      <RegionCascader
                        value={{
                          province: getFieldValue('province'),
                          city: getFieldValue('city'),
                          district: getFieldValue('district'),
                        }}
                        onChange={(v) => setFieldsValue({
                          province: v.province, city: v.city, district: v.district, region_code: v.regionCode,
                        })}
                      />
                    )}
                  </Form.Item>
                </Form.Item>
              )}
              {/* 国内：项目地址必填（对齐简道云 allowBlank=false） */}
              <Form.Item
                name="province"
                hidden
                rules={countryType === 'overseas' ? [] : [{ required: true, message: '请选择项目地址（省/市/区县）' }]}
              >
                <Input />
              </Form.Item>
              <Form.Item name="city" hidden><Input /></Form.Item>
              <Form.Item name="district" hidden><Input /></Form.Item>
              <Form.Item name="region_code" hidden><Input /></Form.Item>
              <PolicyItem name="region" label="详细地址" className="sm:col-span-2 xl:col-span-4">
                <Input placeholder="可补充详细地址，如厂区、街道等" />
              </PolicyItem>

              <PolicyItem name="has_internal_conflict" label="是否内部冲突" rules={[{ required: true, message: '请选择' }]}>
                <ChoiceOptionsBridge fieldId="has_internal_conflict" fallback={YES_NO}>
                  {(opts) => <Radio.Group options={opts} optionType="button" buttonStyle="solid" />}
                </ChoiceOptionsBridge>
              </PolicyItem>
              <PolicyItem name="industry" label="行业" rules={[{ required: true, message: '请选择行业' }]}>
                <ChoiceOptionsBridge fieldId="industry" fallback={INDUSTRY_OPTIONS} dictOptions={industryDict.options}>
                  {(opts) => (
                    <Select placeholder="请选择行业" allowClear showSearch optionFilterProp="label"
                      options={opts} loading={industryDict.loading} />
                  )}
                </ChoiceOptionsBridge>
              </PolicyItem>
              <PolicyItem name="bid_result" label="中标情况">
                <ChoiceOptionsBridge fieldId="bid_result" fallback={BID_RESULT_OPTIONS}>
                  {(opts) => <Select placeholder="请选择" allowClear options={opts} />}
                </ChoiceOptionsBridge>
              </PolicyItem>
              {/* 显隐由 SYSTEM_RULES：落标/流标/未参与 时显示「原因」 */}
              <PolicyItem name="bid_fail_reason" label="原因">
                <ChoiceOptionsBridge fieldId="bid_fail_reason" fallback={BID_FAIL_REASON_OPTIONS}>
                  {(opts) => (
                    <Select placeholder="请选择原因" allowClear options={opts} showSearch optionFilterProp="label" />
                  )}
                </ChoiceOptionsBridge>
              </PolicyItem>
              {/* 显隐+必填由 SYSTEM_RULES：内部冲突=是 时显示并必填 */}
              <PolicyItem name="conflict_note" label="备注：请示部门经理的结果"
                className="sm:col-span-2 xl:col-span-4">
                <Input.TextArea rows={2} placeholder="请示部门经理的结果" />
              </PolicyItem>

              <PolicyItem name="entrust_status" label="委托状态">
                <ChoiceOptionsBridge fieldId="entrust_status" fallback={ENTRUST_STATUS_OPTIONS}>
                  {(opts) => <Radio.Group options={opts} />}
                </ChoiceOptionsBridge>
              </PolicyItem>
              <PolicyItem name="entrust_issued_at" label="委托开具日期">
                <DatePicker showTime className="w-full" format="YYYY-MM-DD HH:mm" />
              </PolicyItem>
              <PolicyItem name="entrust_term" label="委托期限">
                <Input placeholder="委托期限" />
              </PolicyItem>

              <Form.Item label="填表人">
                <Input disabled value={
                  isEdit
                    ? (form.getFieldValue('created_by_name') || '-')
                    : (currentUser?.real_name || currentUser?.username || '-')
                } />
              </Form.Item>
              <PolicyItem name="department_id" label="部门" rules={[{ required: true, message: '请选择部门' }]}>
                <DepartmentSelect />
              </PolicyItem>
              <PolicyItem name="reporter_id" label="申报人">
                <Select placeholder="请选择申报人" allowClear showSearch filterOption={false}
                  loading={reporterSelect.loading}
                  options={reporterSelect.options}
                  onSearch={reporterSelect.onSearch}
                  onDropdownVisibleChange={reporterSelect.onDropdownVisibleChange} />
              </PolicyItem>
              <PolicyItem name="reported_at" label="申报时间">
                <DatePicker showTime className="w-full" placeholder="请选择申报时间" format="YYYY-MM-DD HH:mm" />
              </PolicyItem>

              <PolicyItem name="owner_id" label="负责人">
                <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
                  loading={ownerSelect.loading}
                  options={ownerSelect.options}
                  onSearch={ownerSelect.onSearch}
                  onDropdownVisibleChange={ownerSelect.onDropdownVisibleChange} />
              </PolicyItem>
              <PolicyItem name="project_activity" label="项目动态" className="sm:col-span-2 xl:col-span-3" rules={[{ required: true, message: '请选择项目动态' }]}>
                <ChoiceOptionsBridge fieldId="project_activity" fallback={PROJECT_ACTIVITY_OPTIONS}>
                  {(opts) => <Radio.Group options={opts} />}
                </ChoiceOptionsBridge>
              </PolicyItem>
              <PolicyItem name="demand_summary" label="备注1（线索内容）" className="sm:col-span-2 xl:col-span-4">
                <Input.TextArea rows={3} placeholder="填写线索内容 / 备注" />
              </PolicyItem>
            </div>

            <div className="mb-4 mt-2">
              <AttachmentPanel
                bizType="lead"
                bizId={id}
                title="附件"
                pendingFiles={pendingFiles}
                onPendingChange={setPendingFiles}
              />
            </div>

            {/* 业务反馈：非发起必填，编辑/跟进时填写；审批结论不在此表单 */}
            {isEdit && (
              <PolicySection title="业务反馈项目详情（跟进时填写）" fieldIds={FEEDBACK_FIELD_IDS}>
                <p className="mb-3 -mt-2 text-xs text-slate-400">
                  项目近况 / 跟进进度 / 实地拜访 / 项目状态，由业务后续维护
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-x-4">
                  <PolicyItem name="project_recent" label="项目近况" className="sm:col-span-2 xl:col-span-4">
                    <Input placeholder="项目近况" />
                  </PolicyItem>
                  <PolicyItem name="follow_progress" label="跟进进度" className="sm:col-span-2 xl:col-span-4">
                    <Input placeholder="跟进进度" />
                  </PolicyItem>
                  <PolicyItem name="site_visit" label="实地拜访情况" className="sm:col-span-2 xl:col-span-4">
                    <Input placeholder="实地拜访情况" />
                  </PolicyItem>
                  <PolicyItem name="report_project_status" label="项目状态" className="sm:col-span-2 xl:col-span-4">
                    <ChoiceOptionsBridge fieldId="report_project_status" fallback={REPORT_PROJECT_STATUS_OPTIONS}>
                      {(opts) => <Radio.Group options={opts} />}
                    </ChoiceOptionsBridge>
                  </PolicyItem>
                </div>
              </PolicySection>
            )}

            <div className="mt-4 mb-2 rounded-lg border border-amber-100 bg-amber-50/80 px-3 py-2 text-xs text-amber-800">
              <span className="font-semibold">审批时填写（请勿在此页填写）：</span>
              客户类型（新/老）、项目最终状态（待审/收录/回退/袭击）、回退原因、备注2 —
              由信息情报部在审批待办中完成。
            </div>

            <JdySectionTitle title="其他（可选）" />
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-x-4">
              <PolicyItem name="contact_name" label="联系人">
                <Input placeholder="联系人姓名" />
              </PolicyItem>
              <PolicyItem name="contact_phone" label="联系电话"
                rules={[{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号' }]}>
                <Input placeholder="联系电话" />
              </PolicyItem>
              <PolicyItem name="contact_email" label="联系邮箱"
                rules={[{ type: 'email', message: '请输入正确的邮箱地址' }]}>
                <Input placeholder="联系邮箱" />
              </PolicyItem>
              <PolicyItem name="source" label="线索来源">
                <ChoiceOptionsBridge fieldId="source" fallback={DEFAULT_LEAD_SOURCES} dictOptions={sourceDict.options}>
                  {(opts) => <Select placeholder="渠道来源" allowClear options={opts} loading={sourceDict.loading} />}
                </ChoiceOptionsBridge>
              </PolicyItem>
              <PolicyItem name="biz_date" label="业务日期">
                <DatePicker className="w-full" placeholder="请选择日期" />
              </PolicyItem>
              <PolicyItem name="remark" label="备注" className="sm:col-span-2 xl:col-span-3">
                <Input.TextArea rows={2} placeholder="补充备注" />
              </PolicyItem>
            </div>

            <EntityCustomFields ref={customFieldsRef} entityType="lead" value={customFields}
              onChange={setCustomFields} />

            <div className="flex flex-wrap items-center gap-3 pt-4 border-t border-slate-100">
              {canSubmitApproval ? (
                <>
                  <Button loading={loading} onClick={() => void handleSave(false)}>存草稿</Button>
                  <Button type="primary" loading={loading} onClick={() => void handleSave(true)} className="font-bold">
                    提交审批
                  </Button>
                </>
              ) : (
                <Button type="primary" loading={loading} onClick={() => void handleSave(false)} className="font-bold">
                  保存
                </Button>
              )}
              <Button onClick={() => navigate('/leads')}>取消</Button>
              {canSubmitApproval && (
                <span className="text-xs text-slate-400">
                  「提交审批」会发起情报审核流程；「存草稿」仅保存，可稍后在详情页再提交。
                </span>
              )}
            </div>
          </Form>
        </FieldPolicyProvider>
      </div>
    </div>
  )
}
