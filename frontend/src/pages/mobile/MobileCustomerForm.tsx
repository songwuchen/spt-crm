import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, InputNumber, Select, DatePicker, Checkbox, message } from 'antd'
import dayjs from 'dayjs'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import RegionCascader from '@/components/RegionCascader'
import type { RegionValue } from '@/components/RegionCascader'
import EntityCustomFields, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useAuthStore } from '@/stores/useAuthStore'
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
} from '@/constants/customerForm'
import { MField, MoreFields, reportFirstFormError } from './MobilePolicyField'

export default function MobileCustomerForm() {
  usePageTitle('新建客户')
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [region, setRegion] = useState<RegionValue>({})
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)
  const currentUser = useAuthStore((s) => s.user)
  const userSelect = useUserSelect()

  const handleSubmit = async (andSubmit: boolean) => {
    let values: Record<string, any>
    try {
      if (andSubmit) values = await form.validateFields()
      else {
        await form.validateFields(['name'])
        values = form.getFieldsValue(true)
      }
    } catch (e) { reportFirstFormError(e, message.error); return }
    if (andSubmit) {
      const cfError = customFieldsRef.current?.validate()
      if (cfError) { message.error(cfError); return }
    }
    setLoading(true)
    try {
      const payload = {
        ...values,
        name: (values.name || '').trim(),
        expected_purchase_date: values.expected_purchase_date
          ? (values.expected_purchase_date as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        province: region.province || undefined,
        city: region.city || undefined,
        district: region.district || undefined,
        region_code: region.regionCode || undefined,
        custom_fields_json: customFields,
      }
      const res = andSubmit
        ? await customerApi.create(payload)
        : await customerApi.create({ ...payload, as_draft: true })
      message.success(andSubmit
        ? (res?.data?.review_status === 'pending' ? '已提交审批' : '客户已创建')
        : '已存为草稿')
      navigate(res?.data?.id ? `/m/customers/${res.data.id}` : '/m/customers')
    } catch { message.error('创建失败') } finally { setLoading(false) }
  }

  const inputCls = 'w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm'

  return (
    <div>
      <h1 className="text-xl font-extrabold text-slate-900 mb-4">新建客户</h1>

      <FieldPolicyProvider entityType="customer" form={form} customFieldValues={customFields}>
        <Form
          form={form}
          layout="vertical"
          className="space-y-3"
          initialValues={{
            level: 'C',
            is_foreign_trade: false,
            is_smart_filing: false,
            need_info_distribute: false,
            owner_id: currentUser?.id,
          }}
        >
          <MField name="name" label="客户名称">
            <Input placeholder="请输入客户名称" className={inputCls} />
          </MField>
          <MField name="customer_code" label="客户编号">
            <Input placeholder="自动生成可不填" className={inputCls} />
          </MField>
          <div className="grid grid-cols-2 gap-3">
            <MField name="is_smart_filing" label="智能化备案">
              <Select className="w-full" options={YES_NO} />
            </MField>
            <MField name="is_foreign_trade" label="外贸客户">
              <Select className="w-full" options={YES_NO} />
            </MField>
          </div>
          <MField name="need_info_distribute" label="信息分发-客户">
            <Select className="w-full" options={YES_NO} />
          </MField>
          <MField name="short_name" label="简称">
            <Input placeholder="简称" className={inputCls} />
          </MField>
          <MField name="industry" label="行业">
            <Select placeholder="请选择" allowClear className="w-full" options={DEFAULT_INDUSTRIES} />
          </MField>
          <div>
            <label className="text-sm font-bold text-slate-500 mb-1 block">地区</label>
            <RegionCascader value={region} onChange={setRegion} placeholder="选择省/市/区县" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <MField name="source" label="来源">
              <Select placeholder="请选择" allowClear className="w-full" options={DEFAULT_SOURCES} />
            </MField>
            <MField name="level" label="客户类型">
              <Select className="w-full" options={DEFAULT_LEVELS} />
            </MField>
          </div>
          <MField name="owner_id" label="业务员">
            <Select
              placeholder="选择业务员"
              allowClear
              showSearch
              filterOption={false}
              className="w-full"
              loading={userSelect.loading}
              options={userSelect.options}
              onSearch={userSelect.onSearch}
              onDropdownVisibleChange={userSelect.onDropdownVisibleChange}
            />
          </MField>

          {/* 目录其余字段收在折叠区，避免移动端首屏过重；必填时 MoreFields 会强制展开 */}
          <MoreFields>
            <MField name="address" label="详细地址">
              <Input placeholder="街道 / 门牌" className={inputCls} />
            </MField>
            <MField name="registered_capital" label="注册资金（万元）">
              <InputNumber className="w-full" min={0} placeholder="万元" />
            </MField>
            <MField name="paid_in_capital" label="实缴资本（万元）">
              <InputNumber className="w-full" min={0} placeholder="万元" />
            </MField>
            <MField name="founded_year" label="成立年份">
              <InputNumber className="w-full" min={1800} max={2100} placeholder="年份" />
            </MField>
            <MField name="parent_company_note" label="母公司/控股说明">
              <Input.TextArea rows={2} className={inputCls} />
            </MField>
            <MField name="customer_nature" label="客户性质">
              <Select allowClear className="w-full" options={CUSTOMER_NATURE_OPTIONS} />
            </MField>
            <MField name="customer_relation" label="客户关系">
              <Select allowClear className="w-full" options={CUSTOMER_RELATION_OPTIONS} />
            </MField>
            <MField name="primary_contact_title" label="主联系人职位">
              <Select allowClear className="w-full" options={CONTACT_TITLE_LEVEL_OPTIONS} />
            </MField>
            <MField name="wage_insurance_status" label="工资及保险">
              <Select allowClear className="w-full" options={WAGE_INSURANCE_OPTIONS} />
            </MField>
            <MField name="scale_level" label="企业规模">
              <Select allowClear className="w-full" options={DEFAULT_SCALES} />
            </MField>
            <MField name="region" label="国家/地区">
              <Input className={inputCls} />
            </MField>
            <MField name="country" label="国别">
              <Input className={inputCls} />
            </MField>
            <MField name="foreign_customer_code" label="客户代码">
              <Input className={inputCls} />
            </MField>
            <MField name="foreign_customer_type" label="外贸客户类型">
              <Select allowClear className="w-full" options={FOREIGN_CUSTOMER_TYPE_OPTIONS} />
            </MField>
            <MField name="focus_product" label="关注产品">
              <Select allowClear showSearch className="w-full" options={FOCUS_PRODUCT_OPTIONS} />
            </MField>
            <MField name="customer_email" label="邮箱">
              <Input className={inputCls} />
            </MField>
            <MField name="website" label="主页">
              <Input placeholder="https://" className={inputCls} />
            </MField>
            <MField name="main_products_json" label="主营产品">
              <Checkbox.Group options={MAIN_PRODUCT_OPTIONS} className="flex flex-wrap gap-x-3 gap-y-1" />
            </MField>
            <MField name="legal_person" label="企业法人">
              <Input className={inputCls} />
            </MField>
            <MField name="smart_industry_category" label="所属行业分类">
              <Input className={inputCls} />
            </MField>
            <MField name="annual_run_days" label="年运行天数">
              <Input className={inputCls} />
            </MField>
            <MField name="floor_area" label="占地面积">
              <Input className={inputCls} />
            </MField>
            <MField name="annual_power_usage" label="年用电量">
              <Input className={inputCls} />
            </MField>
            <MField name="daily_operate_hours" label="日运营小时数">
              <Input className={inputCls} />
            </MField>
            <MField name="financial_status" label="企业财务状况">
              <Input.TextArea rows={2} className={inputCls} />
            </MField>
            <MField name="business_status" label="企业经营状况">
              <Input.TextArea rows={2} className={inputCls} />
            </MField>
            <MField name="taxpayer_id" label="纳税人识别号">
              <Input className={inputCls} />
            </MField>
            <MField name="bank_account" label="开户行帐号">
              <Input className={inputCls} />
            </MField>
            <MField name="invoice_address_phone" label="开票地址电话">
              <Input className={inputCls} />
            </MField>
            <MField name="is_company_customer" label="是否公司客户">
              <Select allowClear className="w-full" options={YES_NO} />
            </MField>
            <MField name="budget_amount" label="预算金额">
              <InputNumber className="w-full" min={0} placeholder="预算" />
            </MField>
            <MField name="expected_purchase_date" label="预计采购日期">
              <DatePicker className="w-full" placeholder="请选择日期" />
            </MField>
            <MField name="headcount" label="人数规模">
              <InputNumber className="w-full" min={0} placeholder="人数" />
            </MField>
            <MField name="postal_code" label="邮编">
              <Input placeholder="邮编" className={inputCls} />
            </MField>
            <MField name="demand" label="需求描述">
              <Input.TextArea rows={2} placeholder="客户需求" className={inputCls} />
            </MField>
            <MField name="remark" label="备注">
              <Input.TextArea rows={2} placeholder="其他信息" className={inputCls} />
            </MField>
          </MoreFields>

          <EntityCustomFields ref={customFieldsRef} entityType="customer"
            value={customFields} onChange={setCustomFields} />
        </Form>
      </FieldPolicyProvider>

      <div className="mt-6 flex gap-3">
        <button onClick={() => navigate(-1)}
          className="flex-1 py-2.5 border border-slate-200 rounded-lg text-sm font-bold text-slate-600 bg-white">
          取消
        </button>
        <button onClick={() => void handleSubmit(false)} disabled={loading}
          className="flex-1 py-2.5 border border-slate-200 rounded-lg text-sm font-bold text-slate-700 bg-white disabled:opacity-50">
          {loading ? '保存中...' : '存草稿'}
        </button>
        <button onClick={() => void handleSubmit(true)} disabled={loading}
          className="flex-1 py-2.5 rounded-lg text-sm font-bold text-white bg-primary disabled:opacity-50">
          {loading ? '提交中...' : '提交审批'}
        </button>
      </div>
    </div>
  )
}
