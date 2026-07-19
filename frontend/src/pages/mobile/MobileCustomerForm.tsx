import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, InputNumber, Select, DatePicker, message } from 'antd'
import dayjs from 'dayjs'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import RegionCascader from '@/components/RegionCascader'
import type { RegionValue } from '@/components/RegionCascader'
import EntityCustomFields, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import { MField, MoreFields } from './MobilePolicyField'

const industries = ['电子制造', '汽车零部件', '机械装备', '航空航天', '医疗器械', '半导体', '新能源', '其他']
const sources = ['referral', 'website', 'exhibition', 'cold_call', 'ad', 'other']

// 收在「更多字段」里的次要字段；租户把其中任一项配成必填时该区自动展开
const MORE_FIELD_IDS = [
  'address', 'website', 'budget_amount', 'demand',
  'expected_purchase_date', 'headcount', 'postal_code', 'remark',
]

export default function MobileCustomerForm() {
  usePageTitle('新建客户')
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [region, setRegion] = useState<RegionValue>({})
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)

  const handleSubmit = async () => {
    let values: Record<string, any>
    try { values = await form.validateFields() } catch { return }
    // 扩展字段不在 antd Form 状态里，validateFields 覆盖不到；后端也会二次校验
    const cfError = customFieldsRef.current?.validate()
    if (cfError) { message.error(cfError); return }
    setLoading(true)
    try {
      await customerApi.create({
        ...values,
        name: (values.name || '').trim(),
        expected_purchase_date: values.expected_purchase_date
          ? (values.expected_purchase_date as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        province: region.province || undefined,
        city: region.city || undefined,
        district: region.district || undefined,
        region_code: region.regionCode || undefined,
        custom_fields_json: customFields,
      })
      message.success('客户创建成功')
      navigate('/m/customers')
    } catch { message.error('创建失败') } finally { setLoading(false) }
  }

  const inputCls = 'w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm'

  return (
    <div>
      <h1 className="text-xl font-extrabold text-slate-900 mb-4">新建客户</h1>

      <FieldPolicyProvider entityType="customer" form={form} customFieldValues={customFields}>
        <Form form={form} layout="vertical" className="space-y-3" initialValues={{ level: 'C' }}>
          <MField name="name" label="客户名称">
            <Input placeholder="请输入客户名称" className={inputCls} />
          </MField>
          {/* 简称 / 来源 / 级别 不在原生字段目录里，保持普通 Form.Item */}
          <Form.Item name="short_name" label={<span className="text-sm font-bold text-slate-500">简称</span>}>
            <Input placeholder="简称" className={inputCls} />
          </Form.Item>
          <Form.Item name="industry" label={<span className="text-sm font-bold text-slate-500">行业</span>}>
            <Select placeholder="请选择" allowClear className="w-full"
              options={industries.map((i) => ({ value: i, label: i }))} />
          </Form.Item>
          <div>
            <label className="text-sm font-bold text-slate-500 mb-1 block">地区</label>
            <RegionCascader value={region} onChange={setRegion} placeholder="选择省/市/区县" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Form.Item name="source" label={<span className="text-sm font-bold text-slate-500">来源</span>}>
              <Select placeholder="请选择" allowClear className="w-full"
                options={sources.map((s) => ({ value: s, label: s }))} />
            </Form.Item>
            <Form.Item name="level" label={<span className="text-sm font-bold text-slate-500">级别</span>}>
              <Select className="w-full" options={['A', 'B', 'C', 'D'].map((l) => ({ value: l, label: l }))} />
            </Form.Item>
          </div>

          {/* 桌面端可填而移动端此前缺失的字段。缺了它们，租户一旦把其中任一项配成必填，
              移动端就再也建不了客户 —— 后端 create 是按全部必填字段校验的。 */}
          <MoreFields fieldIds={MORE_FIELD_IDS}>
            <MField name="address" label="详细地址">
              <Input placeholder="街道 / 门牌" className={inputCls} />
            </MField>
            <MField name="website" label="网址">
              <Input placeholder="https://" className={inputCls} />
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
        <button onClick={handleSubmit} disabled={loading}
          className="flex-1 py-2.5 rounded-lg text-sm font-bold text-white bg-primary disabled:opacity-50">
          {loading ? '保存中...' : '创建'}
        </button>
      </div>
    </div>
  )
}
