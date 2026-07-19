import { useEffect, useState, useRef, useCallback } from 'react'
import { Form, Input, Select, Button, Card, Alert, DatePicker, InputNumber, message } from 'antd'
import dayjs from 'dayjs'
import { useParams, useNavigate, useSearchParams } from 'react-router-dom'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import { useDataDict } from '@/hooks/useDataDict'
import { useAutoSave } from '@/hooks/useAutoSave'
import { useAuthStore } from '@/stores/useAuthStore'
import CustomFieldsPanel, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider, PolicyItem } from '@/components/lowcode/FieldPolicy'
import RegionCascader from '@/components/RegionCascader'

const defaultIndustries = ['电子制造', '汽车零部件', '机械装备', '航空航天', '医疗器械', '半导体', '新能源', '其他'].map(i => ({ label: i, value: i }))
const defaultLevels = ['A', 'B', 'C', 'D'].map(l => ({ label: l, value: l }))
const defaultScales = ['微型', '小型', '中型', '大型', '特大型'].map(s => ({ label: s, value: s }))
const defaultSources = [
  { label: '展会', value: 'expo' }, { label: '转介绍', value: 'referral' },
  { label: '广告', value: 'ad' }, { label: '官网/入站', value: 'inbound' },
  { label: '合作伙伴', value: 'partner' }, { label: '电话', value: 'call' },
]
const intentOptions = [
  { label: 'A · 3个月内会订购', value: 'A' }, { label: 'B · 半年内', value: 'B' },
  { label: 'C · 一年内', value: 'C' }, { label: 'D · 一年以上/暂无', value: 'D' },
]
const matchOptions = [
  { label: '有需求有预算', value: 'has_need_budget' },
  { label: '有需求与需求负责人', value: 'has_need_owner' },
  { label: '仅有需求', value: 'need_only' },
  { label: '需求不明确', value: 'unclear' },
]
const currencyOptions = [
  { label: '人民币 CNY', value: 'CNY' }, { label: '美元 USD', value: 'USD' },
  { label: '欧元 EUR', value: 'EUR' }, { label: '日元 JPY', value: 'JPY' },
]

export default function CustomerForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const toPool = searchParams.get('pool') === '1'
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑客户' : toPool ? '新建公海客户' : '新建客户')

  const industryDict = useDataDict('industry', defaultIndustries)
  const industryMap = Object.fromEntries(industryDict.options.map((o) => [o.value, o.label]))
  const levelDict = useDataDict('customer_level', defaultLevels)
  const scaleDict = useDataDict('scale_level', defaultScales)
  const sourceDict = useDataDict('customer_source', defaultSources)

  const currentUser = useAuthStore((s) => s.user)
  const userSelect = useUserSelect()
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)

  const [similarCustomers, setSimilarCustomers] = useState<{ id: string; name: string; short_name?: string; industry?: string; owner_name?: string; match_type?: string; match_phone?: string; match_contact?: string }[]>([])
  const dupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

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
      customerApi.get(id).then((res) => {
        const d: Record<string, unknown> = { ...res.data }
        // DatePicker 需要 dayjs 对象，后端返回的是 'YYYY-MM-DD' 字符串
        if (d.expected_purchase_date) d.expected_purchase_date = dayjs(d.expected_purchase_date as string)
        form.setFieldsValue(d)
        setCustomFields((res.data.custom_fields_json as Record<string, unknown>) || {})
        // Seed owner option so Select shows name instead of raw ID
        if (res.data.owner_id && res.data.owner_name) {
          userSelect.setInitialOption({ label: res.data.owner_name, value: res.data.owner_id })
        }
      }).catch(() => message.error('加载客户数据失败'))
    } else {
      const restored = restoreDraft()
      if (restored) {
        message.info('已恢复上次未保存的草稿')
        // 草稿序列化后日期可能是字符串，转回 dayjs 供 DatePicker 使用
        const epd = form.getFieldValue('expected_purchase_date')
        if (epd && typeof epd === 'string') form.setFieldValue('expected_purchase_date', dayjs(epd))
      }
      // Pre-fill current user as owner for normal customers; pool customers stay unassigned.
      if (currentUser && !toPool) {
        form.setFieldsValue({ owner_id: currentUser.id })
        userSelect.setInitialOption({ label: currentUser.real_name || currentUser.username, value: currentUser.id })
      }
    }
    return () => { if (dupTimerRef.current) clearTimeout(dupTimerRef.current) }
  }, [id])

  const onFinish = async (values: Record<string, unknown>) => {
    // 扩展字段不在 antd Form 状态里，其必填(含条件必填)需单独校验；后端也会二次校验
    const cfError = customFieldsRef.current?.validate()
    if (cfError) {
      message.error(cfError)
      return
    }
    setLoading(true)
    try {
      const payload = { ...values, owner_id: toPool ? null : (values.owner_id || null), custom_fields_json: customFields } as any
      // DatePicker 值为 dayjs 对象，提交为 'YYYY-MM-DD' 字符串
      if (payload.expected_purchase_date) payload.expected_purchase_date = dayjs(payload.expected_purchase_date).format('YYYY-MM-DD')
      if (isEdit) {
        await customerApi.update(id!, payload)
        message.success('客户已更新')
      } else {
        await customerApi.create(payload, toPool)
        message.success(toPool ? '已新建到公海' : '客户已创建')
      }
      clearDraft()
      navigate(toPool ? '/customers/pool' : '/customers')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">{isEdit ? '编辑客户' : '新建客户'}</h2>
      <Card>
       <FieldPolicyProvider entityType="customer" form={form} customFieldValues={customFields}>
        <Form form={form} layout="vertical" onFinish={onFinish} onValuesChange={markDirty} className="max-w-2xl">
          <PolicyItem name="name" label="客户名称" rules={[{ required: true, message: '请输入客户名称' }]}>
            <Input placeholder="请输入客户全称" onChange={(e) => checkDuplicates(e.target.value, form.getFieldValue('phone'))} />
          </PolicyItem>
          {similarCustomers.length > 0 && (
            <Alert type="warning" showIcon className="mb-4"
              message={`发现 ${similarCustomers.length} 个疑似重复客户`}
              description={
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
                      {!isEdit && (
                        <a onClick={() => navigate(`/customers/${c.id}`)} className="text-sm text-emerald-600 hover:underline">查看并合并</a>
                      )}
                    </div>
                  ))}
                </div>
              }
            />
          )}
          <Form.Item name="short_name" label="简称">
            <Input placeholder="请输入简称" />
          </Form.Item>
          <Form.Item name="customer_code" label="客户编码">
            <Input placeholder="请输入客户编码（选填，系统可自动生成）" />
          </Form.Item>
          <Form.Item name="industry" label="行业">
            <Select placeholder="请选择行业" allowClear options={industryDict.options} loading={industryDict.loading} />
          </Form.Item>
          <Form.Item name="scale_level" label="企业规模">
            <Select placeholder="请选择企业规模" allowClear options={scaleDict.options} loading={scaleDict.loading} />
          </Form.Item>
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
                onChange={(v) => {
                  setFieldsValue({ province: v.province, city: v.city, district: v.district, region_code: v.regionCode })
                  markDirty()
                }}
              />
            )}
          </Form.Item>
          {/* 隐藏字段：提交时随表单一起收集 省/市/区县/编码 */}
          <Form.Item name="province" hidden><Input /></Form.Item>
          <Form.Item name="city" hidden><Input /></Form.Item>
          <Form.Item name="district" hidden><Input /></Form.Item>
          <Form.Item name="region_code" hidden><Input /></Form.Item>
          <PolicyItem name="address" label="详细地址">
            <Input placeholder="请输入详细地址（门牌/街道等）" />
          </PolicyItem>
          <PolicyItem name="website" label="网站"
            rules={[{ type: 'url', message: '请输入正确的网址' }]}>
            <Input placeholder="请输入公司网站地址" />
          </PolicyItem>
          <Form.Item name="source" label="客户来源">
            <Select placeholder="请选择来源" allowClear options={sourceDict.options} loading={sourceDict.loading} />
          </Form.Item>
          <Form.Item name="level" label="客户级别" tooltip="价值等级：客户对我方的重要程度（与「采购意向类别」是两个维度）">
            <Select placeholder="请选择级别" allowClear options={levelDict.options} loading={levelDict.loading} />
          </Form.Item>

          {/* ===== 商机要素 · 采购意向（BANT 快照）===== */}
          <div className="text-sm font-semibold text-slate-500 mt-6 mb-3 pb-1 border-b border-slate-100">商机要素 · 采购意向</div>
          <div className="grid grid-cols-2 gap-x-4">
            <PolicyItem name="expected_purchase_date" label="预计采购时间">
              <DatePicker className="w-full" placeholder="选择预计采购日期" />
            </PolicyItem>
            <Form.Item name="intent_level" label="采购意向类别"
              tooltip="留空则由预计采购时间自动推算：3个月内=A、半年内=B、一年内=C、更久/已过期=D">
              <Select placeholder="留空自动推算" allowClear options={intentOptions} />
            </Form.Item>
            <PolicyItem name="budget_amount" label="客户预算(元)">
              <InputNumber<number> className="w-full" min={0} step={1000} placeholder="预算金额" controls={false}
                formatter={(v) => (v === undefined || v === null ? '' : `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ','))}
                parser={(v) => {
                  const s = String(v ?? '').replace(/,/g, '')
                  // 清空时返回 undefined(而非 0)，允许把预算置空，不被强制写成 0
                  return (s === '' ? undefined : Number(s)) as unknown as number
                }} />
            </PolicyItem>
            <Form.Item name="need_match_level" label="需求匹配程度">
              <Select placeholder="选择匹配程度" allowClear options={matchOptions} />
            </Form.Item>
          </div>
          <PolicyItem name="demand" label="核心需求">
            <Input.TextArea rows={2} placeholder="客户的核心需求（如：除铁设备）" />
          </PolicyItem>

          {/* ===== 公司档案 ===== */}
          <div className="text-sm font-semibold text-slate-500 mt-6 mb-3 pb-1 border-b border-slate-100">公司档案</div>
          <div className="grid grid-cols-3 gap-x-4">
            <Form.Item name="industry_l1" label="一级行业"><Input placeholder="一级" /></Form.Item>
            <Form.Item name="industry_l2" label="二级行业"><Input placeholder="二级" /></Form.Item>
            <Form.Item name="industry_l3" label="三级行业"><Input placeholder="三级" /></Form.Item>
          </div>
          <div className="grid grid-cols-3 gap-x-4">
            <Form.Item name="country" label="国家"><Input placeholder="如：中国" /></Form.Item>
            <PolicyItem name="postal_code" label="邮政编码"><Input placeholder="邮编" /></PolicyItem>
            <PolicyItem name="headcount" label="公司总人数"><InputNumber className="w-full" min={0} placeholder="人数" /></PolicyItem>
          </div>
          <Form.Item name="currency" label="币种">
            <Select placeholder="默认人民币 CNY" allowClear style={{ maxWidth: 220 }} options={currencyOptions} />
          </Form.Item>

          {!toPool && (
            <Form.Item name="owner_id" label="负责人">
              <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
                loading={userSelect.loading}
                options={userSelect.options}
                onSearch={userSelect.onSearch}
                onDropdownVisibleChange={userSelect.onDropdownVisibleChange} />
            </Form.Item>
          )}
          {toPool && (
            <Alert type="info" showIcon className="mb-4"
              message="新建到公海"
              description="该客户将进入公海池（无负责人），后续可由销售员领取或由管理员分配。" />
          )}
          {isEdit && (
            <Form.Item name="status" label="状态">
              <Select options={[
                { label: '活跃', value: 'active' },
                { label: '不活跃', value: 'inactive' },
              ]} />
            </Form.Item>
          )}
          <Form.Item name="tags_json" label="标签">
            <Select mode="tags" placeholder="输入标签后回车添加" tokenSeparators={[',']} />
          </Form.Item>
          <PolicyItem name="remark" label="备注">
            <Input.TextArea rows={3} placeholder="备注信息" />
          </PolicyItem>
          <div className="mb-4">
            <CustomFieldsPanel ref={customFieldsRef} entityType="customer" values={customFields} onChange={setCustomFields} />
          </div>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>保存</Button>
            <Button className="ml-2" onClick={() => navigate('/customers')}>取消</Button>
          </Form.Item>
        </Form>
       </FieldPolicyProvider>
      </Card>
    </div>
  )
}
