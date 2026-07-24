import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Select, DatePicker, message } from 'antd'
import dayjs from 'dayjs'
import { leadApi } from '@/api/lead'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useDataDict } from '@/hooks/useDataDict'
import { useUserSelect } from '@/hooks/useSelectOptions'
import DepartmentSelect from '@/components/DepartmentSelect'
import EntityCustomFields, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import { MField, MoreFields, reportFirstFormError } from './MobilePolicyField'
import { useAuthStore } from '@/stores/useAuthStore'

const defaultSources = [
  { value: 'website', label: '官网' }, { value: 'referral', label: '转介绍' },
  { value: 'exhibition', label: '展会' }, { value: 'cold_call', label: '陌拜' },
  { value: 'advertising', label: '广告' }, { value: 'other', label: '其他' },
]
const categoryOptions = [
  { label: '自报', value: 'self_reported' },
  { label: '分发', value: 'distributed' },
]
const countryOptions = [
  { label: '国内', value: 'domestic' },
  { label: '国外', value: 'overseas' },
]


export default function MobileLeadForm() {
  usePageTitle('新建线索')
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)

  const sourceDict = useDataDict('lead_source', defaultSources)
  const industryDict = useDataDict('industry')
  const customerTypeDict = useDataDict('customer_type')
  const budgetDict = useDataDict('budget_range')
  const countryType = Form.useWatch('country_type', form)
  const reporterSelect = useUserSelect()
  const ownerSelect = useUserSelect()
  const currentUser = useAuthStore((s) => s.user)

  useEffect(() => {
    if (!currentUser) return
    const label = currentUser.real_name || currentUser.username
    form.setFieldsValue({ reporter_id: currentUser.id, reported_at: dayjs() })
    reporterSelect.setInitialOption({ label, value: currentUser.id })
  }, [currentUser])

  const handleSubmit = async () => {
    let values: Record<string, unknown>
    // 折叠区用 display:none 隐藏，错误若落在收起的字段上，用户只会看到「保存没反应」
    try { values = await form.validateFields() } catch (e) { reportFirstFormError(e, message.error); return }
    // 扩展字段不在 antd Form 状态里，validateFields 覆盖不到；后端也会二次校验
    const cfError = customFieldsRef.current?.validate()
    if (cfError) { message.error(cfError); return }
    setLoading(true)
    try {
      await leadApi.create({
        ...values,
        biz_date: values.biz_date ? (values.biz_date as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        reported_at: values.reported_at ? (values.reported_at as dayjs.Dayjs).toISOString() : undefined,
        custom_fields_json: customFields,
      } as any)
      message.success('线索已创建')
      navigate(-1)
    } catch { message.error('创建失败') }
    finally { setLoading(false) }
  }

  const inputCls = 'w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm'

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="text-primary font-bold text-sm">取消</button>
        <h1 className="text-base font-bold text-slate-900">新建线索</h1>
        <button onClick={handleSubmit} disabled={loading}
          className="text-primary font-bold text-sm disabled:opacity-50">
          {loading ? '提交中...' : '保存'}
        </button>
      </div>

      <FieldPolicyProvider entityType="lead" form={form} customFieldValues={customFields}>
        <Form form={form} layout="vertical" className="p-4 space-y-4 mobile-policy-form"
          initialValues={{ source: 'website' }}>
          <MField name="title" label="线索标题">
            <Input placeholder="输入线索标题" className={inputCls} />
          </MField>
          <MField name="company_name" label="公司名称">
            <Input placeholder="输入公司名称" className={inputCls} />
          </MField>
          <div className="grid grid-cols-2 gap-3">
            <MField name="contact_name" label="联系人">
              <Input placeholder="姓名" className={inputCls} />
            </MField>
            <MField name="contact_phone" label="电话">
              <Input placeholder="电话号码" className={inputCls} />
            </MField>
          </div>
          <MField name="source" label="来源">
            <Select options={sourceDict.options} loading={sourceDict.loading} className="w-full" />
          </MField>
          <MField name="reporter_id" label="报备人">
            <Select placeholder="请选择报备人" allowClear showSearch filterOption={false}
              className="w-full" loading={reporterSelect.loading} options={reporterSelect.options}
              onSearch={reporterSelect.onSearch}
              onDropdownVisibleChange={reporterSelect.onDropdownVisibleChange} />
          </MField>
          <MField name="reported_at" label="报备时间">
            <DatePicker showTime className="w-full" placeholder="请选择报备时间"
              format="YYYY-MM-DD HH:mm" />
          </MField>
          <MField name="owner_id" label="负责人">
            <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
              className="w-full" loading={ownerSelect.loading} options={ownerSelect.options}
              onSearch={ownerSelect.onSearch}
              onDropdownVisibleChange={ownerSelect.onDropdownVisibleChange} />
          </MField>
          <MField name="department_id" label="部门">
            <DepartmentSelect />
          </MField>
          <MField name="remark" label="备注">
            <Input.TextArea placeholder="其他信息" rows={3} className={inputCls} />
          </MField>

          {/* 桌面端可填而移动端此前缺失的字段。缺了它们，租户一旦把其中任一项配成必填，
              移动端就再也建不了线索 —— 后端 create 是按全部必填字段校验的。 */}
          <MoreFields>
            <MField name="customer_type" label="客户类型">
              <Select placeholder="请选择" allowClear options={customerTypeDict.options}
                loading={customerTypeDict.loading} className="w-full" />
            </MField>
            <MField name="industry" label="行业">
              <Select placeholder="请选择" allowClear options={industryDict.options}
                loading={industryDict.loading} className="w-full" />
            </MField>
            <MField name="category" label="类别">
              <Select placeholder="请选择" allowClear options={categoryOptions} className="w-full" />
            </MField>
            <MField name="budget_range" label="预算范围">
              <Select placeholder="请选择" allowClear options={budgetDict.options}
                loading={budgetDict.loading} className="w-full" />
            </MField>
            <MField name="biz_date" label="业务日期">
              <DatePicker className="w-full" placeholder="请选择日期" />
            </MField>
            <MField name="country_type" label="国别">
              <Select placeholder="请选择" allowClear options={countryOptions} className="w-full" />
            </MField>
            {countryType === 'overseas' && (
              <MField name="country_name" label="国家">
                <Input placeholder="输入国家名称" className={inputCls} />
              </MField>
            )}
            <MField name="region" label="详细地址">
              <Input placeholder="可补充详细地址" className={inputCls} />
            </MField>
            <MField name="contact_email" label="联系邮箱">
              <Input placeholder="邮箱" className={inputCls} />
            </MField>
            <MField name="demand_summary" label="需求摘要">
              <Input.TextArea placeholder="客户需求" rows={2} className={inputCls} />
            </MField>
          </MoreFields>

          <EntityCustomFields ref={customFieldsRef} entityType="lead"
            value={customFields} onChange={setCustomFields} />
        </Form>
      </FieldPolicyProvider>
    </div>
  )
}
