import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Form, Input, Select, DatePicker, Radio, message } from 'antd'
import dayjs from 'dayjs'
import { leadApi } from '@/api/lead'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useDataDict } from '@/hooks/useDataDict'
import { useUserSelect } from '@/hooks/useSelectOptions'
import DepartmentSelect from '@/components/DepartmentSelect'
import EntityCustomFields, { type EntityCustomFieldsRef } from '@/components/lowcode/EntityCustomFields'
import { FieldPolicyProvider } from '@/components/lowcode/FieldPolicy'
import { MField, MoreFields, reportFirstFormError } from './MobilePolicyField'
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
} from '@/constants/leadForm'

export default function MobileLeadForm() {
  usePageTitle('新建线索')
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})
  const customFieldsRef = useRef<EntityCustomFieldsRef>(null)

  const sourceDict = useDataDict('lead_source', DEFAULT_LEAD_SOURCES)
  const industryDict = useDataDict('industry', INDUSTRY_OPTIONS)
  const customerTypeDict = useDataDict('customer_type', CUSTOMER_TYPE_OPTIONS)
  const countryType = Form.useWatch('country_type', form)
  const hasConflict = Form.useWatch('has_internal_conflict', form)
  const reporterSelect = useUserSelect()
  const ownerSelect = useUserSelect()

  useEffect(() => {
    form.setFieldsValue({
      reported_at: dayjs(),
      has_internal_conflict: '否',
    })
  }, [])

  const handleSave = async (andSubmit: boolean) => {
    let values: Record<string, unknown>
    try {
      if (andSubmit) {
        values = await form.validateFields()
      } else {
        // 存草稿：仅项目名称必填（与桌面端一致）
        await form.validateFields(['title'])
        values = form.getFieldsValue(true)
      }
    } catch (e) {
      reportFirstFormError(e, message.error)
      return
    }
    if (andSubmit) {
      const cfError = customFieldsRef.current?.validate()
      if (cfError) { message.error(cfError); return }
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
        ...(andSubmit ? {} : { as_draft: true }),
      }
      const res = await leadApi.create(payload as Partial<import('@/api/types').Lead> & { as_draft?: boolean })
      message.success(andSubmit ? '已提交审批' : '已存为草稿')
      if (res.data?.id) navigate(`/m/leads/${res.data.id}`)
      else navigate(-1)
    } catch { message.error(andSubmit ? '提交失败' : '保存失败') }
    finally { setLoading(false) }
  }

  const inputCls = 'w-full bg-white border border-slate-200 rounded-lg px-3 py-2.5 text-sm'

  return (
    <div className="min-h-screen bg-slate-50 pb-20">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
        <button onClick={() => navigate(-1)} className="text-primary font-bold text-sm">取消</button>
        <h1 className="text-base font-bold text-slate-900">新建线索</h1>
        <span className="w-10" />
      </div>

      <FieldPolicyProvider
        entityType="lead"
        form={form}
        customFieldValues={customFields}
        formMode="create"
      >
        <Form form={form} layout="vertical" className="p-4 space-y-4 mobile-policy-form">
          <MField name="category" label="来源">
            <Radio.Group options={CATEGORY_OPTIONS} />
          </MField>
          <MField name="title" label="项目名称">
            <Input placeholder="输入项目名称" className={inputCls} />
          </MField>
          <MField name="company_name" label="公司名称">
            <Input placeholder="输入公司名称" className={inputCls} />
          </MField>
          <MField name="customer_type" label="客户类型">
            <Select placeholder="请选择" allowClear options={customerTypeDict.options}
              loading={customerTypeDict.loading} className="w-full" />
          </MField>
          <MField name="has_internal_conflict" label="是否内部冲突">
            <Radio.Group options={YES_NO} />
          </MField>
          {(hasConflict === '是') && (
            <MField name="conflict_note" label="请示部门经理的结果">
              <Input placeholder="请示结果" className={inputCls} />
            </MField>
          )}
          <MField name="industry" label="行业">
            <Select placeholder="请选择" allowClear options={industryDict.options}
              loading={industryDict.loading} className="w-full" />
          </MField>
          <MField name="country_type" label="国别">
            <Radio.Group options={COUNTRY_OPTIONS} />
          </MField>
          {countryType === 'overseas' && (
            <MField name="country_name" label="国家">
              <Input placeholder="输入国家名称" className={inputCls} />
            </MField>
          )}
          <MField name="region" label="详细地址">
            <Input placeholder="可补充详细地址" className={inputCls} />
          </MField>
          <MField name="project_activity" label="项目动态">
            <Radio.Group options={PROJECT_ACTIVITY_OPTIONS} />
          </MField>
          <MField name="reporter_id" label="申报人">
            <Select placeholder="请选择申报人" allowClear showSearch filterOption={false}
              className="w-full" loading={reporterSelect.loading} options={reporterSelect.options}
              onSearch={reporterSelect.onSearch}
              onDropdownVisibleChange={reporterSelect.onDropdownVisibleChange} />
          </MField>
          <MField name="reported_at" label="申报时间">
            <DatePicker showTime className="w-full" placeholder="请选择申报时间"
              format="YYYY-MM-DD HH:mm" />
          </MField>
          <MField name="department_id" label="部门">
            <DepartmentSelect />
          </MField>
          <MField name="demand_summary" label="备注1">
            <Input.TextArea placeholder="备注" rows={2} className={inputCls} />
          </MField>

          <MoreFields>
            <MField name="entrust_status" label="委托状态">
              <Radio.Group options={ENTRUST_STATUS_OPTIONS} />
            </MField>
            <MField name="entrust_issued_at" label="委托开具日期">
              <DatePicker showTime className="w-full" format="YYYY-MM-DD HH:mm" />
            </MField>
            <MField name="entrust_term" label="委托期限">
              <Input placeholder="委托期限" className={inputCls} />
            </MField>
            <MField name="owner_id" label="负责人">
              <Select placeholder="请选择负责人" allowClear showSearch filterOption={false}
                className="w-full" loading={ownerSelect.loading} options={ownerSelect.options}
                onSearch={ownerSelect.onSearch}
                onDropdownVisibleChange={ownerSelect.onDropdownVisibleChange} />
            </MField>
            <MField name="project_recent" label="项目近况">
              <Input placeholder="项目近况" className={inputCls} />
            </MField>
            <MField name="follow_progress" label="跟进进度">
              <Input placeholder="跟进进度" className={inputCls} />
            </MField>
            <MField name="site_visit" label="实地拜访情况">
              <Input placeholder="实地拜访情况" className={inputCls} />
            </MField>
            <MField name="report_project_status" label="项目状态">
              <Radio.Group options={REPORT_PROJECT_STATUS_OPTIONS} />
            </MField>
            <div className="grid grid-cols-2 gap-3">
              <MField name="contact_name" label="联系人">
                <Input placeholder="姓名" className={inputCls} />
              </MField>
              <MField name="contact_phone" label="电话">
                <Input placeholder="电话号码" className={inputCls} />
              </MField>
            </div>
            <MField name="contact_email" label="联系邮箱">
              <Input placeholder="邮箱" className={inputCls} />
            </MField>
            <MField name="source" label="线索来源">
              <Select options={sourceDict.options} loading={sourceDict.loading} className="w-full" allowClear />
            </MField>
            <MField name="biz_date" label="业务日期">
              <DatePicker className="w-full" placeholder="请选择日期" />
            </MField>
            <MField name="remark" label="备注">
              <Input.TextArea placeholder="其他信息" rows={2} className={inputCls} />
            </MField>
          </MoreFields>

          <EntityCustomFields ref={customFieldsRef} entityType="lead"
            value={customFields} onChange={setCustomFields} />
        </Form>
      </FieldPolicyProvider>

      <div
        className="fixed bottom-0 left-0 right-0 bg-white border-t border-slate-100 p-3 grid grid-cols-2 gap-2 z-20"
        style={{ paddingBottom: 'calc(env(safe-area-inset-bottom) + 12px)' }}
      >
        <button
          type="button"
          disabled={loading}
          onClick={() => void handleSave(false)}
          className="h-11 rounded-xl bg-slate-100 text-slate-700 font-bold disabled:opacity-50"
        >
          存草稿
        </button>
        <button
          type="button"
          disabled={loading}
          onClick={() => void handleSave(true)}
          className="h-11 rounded-xl bg-primary text-white font-bold disabled:opacity-50"
        >
          提交审批
        </button>
      </div>
    </div>
  )
}
