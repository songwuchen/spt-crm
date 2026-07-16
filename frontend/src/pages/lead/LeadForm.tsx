import { useEffect, useState } from 'react'
import { Form, Input, Select, Button, DatePicker, InputNumber, message } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import dayjs from 'dayjs'
import { leadApi } from '@/api/lead'
import EntityCustomFields from '@/components/lowcode/EntityCustomFields'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useDataDict } from '@/hooks/useDataDict'
import RegionCascader from '@/components/RegionCascader'
import DepartmentSelect from '@/components/DepartmentSelect'

const defaultSources = [
  { label: '展会', value: 'expo' }, { label: '转介绍', value: 'referral' },
  { label: '广告', value: 'ad' }, { label: '官网/入站', value: 'inbound' },
  { label: '合作伙伴', value: 'partner' }, { label: '电话', value: 'call' },
]
const defaultBudgets = ['10万以下', '10-50万', '50-100万', '100-500万', '500万以上'].map(b => ({ label: b, value: b }))
const categoryOptions = [
  { label: '自报', value: 'self_reported' },
  { label: '分发', value: 'distributed' },
]
const countryOptions = [
  { label: '国内', value: 'domestic' },
  { label: '国外', value: 'overseas' },
]

export default function LeadForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑线索' : '新建线索')

  const sourceDict = useDataDict('lead_source', defaultSources)
  const industryDict = useDataDict('industry')
  const customerTypeDict = useDataDict('customer_type')
  const budgetDict = useDataDict('budget_range', defaultBudgets)

  const userSelect = useUserSelect()
  const [countryType, setCountryType] = useState<string | undefined>(undefined)

  useEffect(() => {
    if (id) {
      leadApi.get(id).then((res) => {
        const d = res.data as any
        form.setFieldsValue({
          ...d,
          biz_date: d.biz_date ? dayjs(d.biz_date) : undefined,
          products: d.products || [],
        })
        setCountryType(res.data.country_type)
        setCustomFields(d.custom_fields_json || {})
        // Seed owner option so the Select shows the name, not the raw owner_id code
        if (res.data.owner_id && res.data.owner_name) {
          userSelect.setInitialOption({ label: res.data.owner_name, value: res.data.owner_id })
        }
      }).catch(() => message.error('加载线索数据失败'))
    }
  }, [id])

  const onFinish = async (values: Record<string, unknown>) => {
    setLoading(true)
    try {
      // 丢弃完全空白的产品明细行；业务日期 dayjs → 字符串
      const rawProducts = (Array.isArray(values.products) ? values.products : []) as Record<string, unknown>[]
      const products = rawProducts.filter((p) =>
        p && (p.product_name || p.product_spec || p.quantity != null || p.remark))
      const payload = {
        ...values,
        biz_date: values.biz_date ? (values.biz_date as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        products,
        custom_fields_json: customFields,
      }
      if (isEdit) {
        await leadApi.update(id!, payload)
        message.success('线索已更新')
      } else {
        const res = await leadApi.create(payload)
        message.success(res?.data?.review_status === 'pending'
          ? '线索已提交，等待信息情报部内勤审核'
          : '线索已创建')
      }
      navigate('/leads')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          {isEdit ? '编辑线索' : '新建线索'}
        </h1>
        <p className="text-sm text-slate-500 mt-0.5">
          {isEdit ? '修改线索的基本信息' : '填写线索信息以创建新的销售线索'}
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6">
        <Form form={form} layout="vertical" onFinish={onFinish} className="max-w-3xl">
          {/* Basic Info */}
          <div className="mb-6">
            <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-400 mb-4">基本信息</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Form.Item name="title" label="线索标题" rules={[{ required: true, message: '请输入线索标题' }]} className="col-span-2">
                <Input placeholder="请输入线索标题" />
              </Form.Item>
              <Form.Item name="company_name" label="公司名称" rules={[{ required: true, message: '请输入公司名称' }]}>
                <Input placeholder="请输入公司名称" />
              </Form.Item>
              <Form.Item name="customer_type" label="客户类型">
                <Select placeholder="请选择客户类型" allowClear showSearch optionFilterProp="label"
                  options={customerTypeDict.options} loading={customerTypeDict.loading} />
              </Form.Item>
              <Form.Item name="industry" label="行业">
                <Select placeholder="请选择行业" allowClear showSearch optionFilterProp="label"
                  options={industryDict.options} loading={industryDict.loading} />
              </Form.Item>
              <Form.Item name="source" label="线索来源">
                <Select placeholder="请选择来源" allowClear options={sourceDict.options} loading={sourceDict.loading} />
              </Form.Item>
              <Form.Item name="category" label="类别" tooltip="自报=自行开发；分发=领导指派">
                <Select placeholder="请选择类别" allowClear options={categoryOptions} />
              </Form.Item>
              <Form.Item name="department_id" label="部门">
                <DepartmentSelect />
              </Form.Item>
              <Form.Item name="budget_range" label="预算范围">
                <Select placeholder="请选择预算范围" allowClear options={budgetDict.options} loading={budgetDict.loading} />
              </Form.Item>
              <Form.Item name="owner_id" label="负责人">
                <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
                  loading={userSelect.loading}
                  options={userSelect.options}
                  onSearch={userSelect.onSearch}
                  onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
              </Form.Item>
              <Form.Item name="biz_date" label="日期" tooltip="业务日期，可自行编辑，用于标识不同时间的线索">
                <DatePicker className="w-full" placeholder="请选择日期" />
              </Form.Item>
            </div>
          </div>

          {/* Location */}
          <div className="mb-6">
            <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-400 mb-4">项目地址</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Form.Item name="country_type" label="国别">
                <Select placeholder="请选择国别" allowClear options={countryOptions} onChange={(v) => setCountryType(v)} />
              </Form.Item>
              {countryType === 'overseas' ? (
                <Form.Item name="country_name" label="国家">
                  <Input placeholder="请输入国家名称" />
                </Form.Item>
              ) : (
                <Form.Item
                  label="省/市/区县"
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
                      onChange={(v) => setFieldsValue({ province: v.province, city: v.city, district: v.district, region_code: v.regionCode })}
                    />
                  )}
                </Form.Item>
              )}
              {/* Hidden inputs so Form collects province/city/district/region_code on submit */}
              <Form.Item name="province" hidden><Input /></Form.Item>
              <Form.Item name="city" hidden><Input /></Form.Item>
              <Form.Item name="district" hidden><Input /></Form.Item>
              <Form.Item name="region_code" hidden><Input /></Form.Item>
              <Form.Item name="region" label="详细地址/备注地点" className="col-span-2">
                <Input placeholder="可补充详细地址，如厂区、街道等" />
              </Form.Item>
            </div>
          </div>

          {/* Contact Info */}
          <div className="mb-6">
            <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-400 mb-4">联系人信息</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
              <Form.Item name="contact_name" label="联系人姓名">
                <Input placeholder="请输入联系人姓名" />
              </Form.Item>
              <Form.Item name="contact_phone" label="联系电话"
                rules={[{ pattern: /^1[3-9]\d{9}$/, message: '请输入正确的手机号' }]}>
                <Input placeholder="请输入联系电话" />
              </Form.Item>
              <Form.Item name="contact_email" label="联系邮箱" className="col-span-2"
                rules={[{ type: 'email', message: '请输入正确的邮箱地址' }]}>
                <Input placeholder="请输入联系邮箱" />
              </Form.Item>
            </div>
          </div>

          {/* Product Info sub-table (issue #84) */}
          <div className="mb-6">
            <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-400 mb-4">产品信息</h3>
            <Form.List name="products">
              {(fields, { add, remove }) => (
                <>
                  {fields.length > 0 && (
                    <div className="hidden sm:flex items-center gap-2 px-1 mb-1 text-[13px] font-semibold text-slate-400">
                      <span className="flex-1">产品名称</span>
                      <span className="flex-1">产品规格</span>
                      <span className="w-28">数量</span>
                      <span className="flex-1">备注</span>
                      <span className="w-8" />
                    </div>
                  )}
                  {fields.map(({ key, name }) => (
                    <div key={key} className="flex flex-col sm:flex-row items-stretch sm:items-start gap-2 mb-2">
                      <Form.Item name={[name, 'product_name']} className="!mb-0 flex-1">
                        <Input placeholder="产品名称" />
                      </Form.Item>
                      <Form.Item name={[name, 'product_spec']} className="!mb-0 flex-1">
                        <Input placeholder="产品规格" />
                      </Form.Item>
                      <Form.Item name={[name, 'quantity']} className="!mb-0 w-full sm:w-28">
                        <InputNumber className="w-full" min={0} placeholder="数量" />
                      </Form.Item>
                      <Form.Item name={[name, 'remark']} className="!mb-0 flex-1">
                        <Input placeholder="备注" />
                      </Form.Item>
                      <Button type="text" danger icon={<DeleteOutlined />} onClick={() => remove(name)} className="shrink-0" />
                    </div>
                  ))}
                  <Button type="dashed" icon={<PlusOutlined />} onClick={() => add({})} block>
                    添加产品
                  </Button>
                </>
              )}
            </Form.List>
          </div>

          {/* Extra Info */}
          <div className="mb-6">
            <h3 className="text-[12px] font-bold uppercase tracking-widest text-slate-400 mb-4">补充信息</h3>
            <Form.Item name="demand_summary" label="需求摘要">
              <Input.TextArea rows={3} placeholder="请描述客户需求" />
            </Form.Item>
            <Form.Item name="remark" label="备注">
              <Input.TextArea rows={3} placeholder="备注信息" />
            </Form.Item>
          </div>

          <EntityCustomFields entityType="lead" value={customFields} onChange={setCustomFields} />

          <div className="flex gap-3 pt-4 border-t border-slate-100">
            <Button type="primary" htmlType="submit" loading={loading} className="font-bold">
              保存
            </Button>
            <Button onClick={() => navigate('/leads')}>取消</Button>
          </div>
        </Form>
      </div>
    </div>
  )
}
