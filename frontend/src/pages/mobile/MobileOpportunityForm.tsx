import { useRef, useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, InputNumber, Select, DatePicker, Checkbox, message } from 'antd'
import dayjs from 'dayjs'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import { usePageTitle } from '@/hooks/usePageTitle'
import EntityCustomFields, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import { MField, MoreFields, reportFirstFormError } from './MobilePolicyField'


export default function MobileOpportunityForm() {
  usePageTitle('新建商机')
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [customers, setCustomers] = useState<{ id: string; name: string }[]>([])
  const [form] = Form.useForm()
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)

  useEffect(() => {
    customerApi.list({ pageNo: 1, pageSize: 100 })
      .then(r => setCustomers((r.data?.items || []).map((c: any) => ({ id: c.id, name: c.name }))))
      .catch(() => {})
  }, [])

  const inputCls = 'w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm'
  const labelCls = 'text-sm font-bold text-slate-500 uppercase tracking-wider'

  const handleSubmit = async () => {
    let v: Record<string, any>
    // 折叠区用 display:none 隐藏，错误若落在收起的字段上，用户只会看到「保存没反应」
    try { v = await form.validateFields() } catch (e) { reportFirstFormError(e, message.error); return }
    // 扩展字段不在 antd Form 状态里，validateFields 覆盖不到；后端也会二次校验
    const cfError = customFieldsRef.current?.validate()
    if (cfError) { message.error(cfError); return }
    setLoading(true)
    try {
      const data: any = {
        ...v,
        close_date_expect: v.close_date_expect
          ? (v.close_date_expect as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        custom_fields_json: customFields,
      }
      // 关键需求（推进到 S3 前必填），剔除空值
      const kr: Record<string, unknown> = {}
      if ((v.req_summary || '').trim()) kr.summary = v.req_summary.trim()
      if ((v.req_acceptance || '').trim()) kr.acceptance = v.req_acceptance.trim()
      if (v.req_confirmed) kr.confirmed = true
      if (Object.keys(kr).length) data.key_requirements_json = kr
      delete data.req_summary; delete data.req_acceptance; delete data.req_confirmed
      await projectApi.create(data)
      message.success('商机已创建')
      navigate(-1)
    } catch { message.error('创建失败') }
    finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="text-primary font-bold text-sm">取消</button>
        <h1 className="text-base font-bold text-slate-900">新建商机</h1>
        <button onClick={handleSubmit} disabled={loading}
          className="text-primary font-bold text-sm disabled:opacity-50">
          {loading ? '提交中...' : '保存'}
        </button>
      </div>

      <FieldPolicyProvider entityType="project" form={form} customFieldValues={customFields}>
        <Form form={form} layout="vertical" className="p-4 space-y-4"
          initialValues={{ stage: 'S1' }}>
          <MField name="name" label="商机名称">
            <Input placeholder="输入商机名称" className={inputCls} />
          </MField>
          {/* 客户与阶段不在原生字段目录里，保持普通 Form.Item */}
          <Form.Item name="customer_id" label={<span className={labelCls}>客户</span>}
            rules={[{ required: true, message: '请选择客户' }]}>
            <Select placeholder="请选择客户" className="w-full" showSearch optionFilterProp="label"
              options={customers.map((c) => ({ value: c.id, label: c.name }))} />
          </Form.Item>
          <div className="grid grid-cols-2 gap-3">
            <MField name="amount_expect" label="预期金额">
              <InputNumber className="w-full" min={0} placeholder="0.00" />
            </MField>
            <Form.Item name="stage" label={<span className={labelCls}>阶段</span>}>
              <Select className="w-full" options={[
                { value: 'S1', label: 'S1 线索确认' },
                { value: 'S2', label: 'S2 需求分析' },
                { value: 'S3', label: 'S3 方案报价' },
              ]} />
            </Form.Item>
          </div>

          {/* 桌面端可填而移动端此前缺失的字段。缺了它们，租户一旦把其中任一项配成必填，
              移动端就再也建不了商机 —— 后端 create 是按全部必填字段校验的。 */}
          <MoreFields>
            <MField name="probability" label="赢单概率">
              <InputNumber className="w-full" min={0} max={100} placeholder="0-100" />
            </MField>
            <MField name="close_date_expect" label="预计成交日期">
              <DatePicker className="w-full" placeholder="请选择日期" />
            </MField>
            <MField name="payment_method" label="付款方式">
              <Input placeholder="如 电汇 / 承兑" className={inputCls} />
            </MField>
          </MoreFields>

          <div className="border-t border-slate-100 pt-4">
            <div className="text-sm font-bold text-slate-700">关键需求</div>
            <div className="text-[13px] text-slate-400 mb-2">推进到「S3 方案报价」前需填写</div>
            <Form.Item name="req_summary" noStyle>
              <Input.TextArea placeholder="需求摘要：客户核心需求、技术规格、交付/预算约束等"
                rows={3} className={`${inputCls} resize-none`} />
            </Form.Item>
            <Form.Item name="req_acceptance" noStyle>
              <Input.TextArea placeholder="验收标准 / 技术协议要点（可选）"
                rows={2} className={`mt-2 ${inputCls} resize-none`} />
            </Form.Item>
            <Form.Item name="req_confirmed" valuePropName="checked" noStyle>
              <Checkbox className="mt-2 text-sm text-slate-600">需求已与客户确认</Checkbox>
            </Form.Item>
          </div>

          <MField name="remark" label="备注">
            <Input.TextArea placeholder="其他信息" rows={3} className={`${inputCls} resize-none`} />
          </MField>

          <EntityCustomFields ref={customFieldsRef} entityType="project"
            value={customFields} onChange={setCustomFields} />
        </Form>
      </FieldPolicyProvider>
    </div>
  )
}
