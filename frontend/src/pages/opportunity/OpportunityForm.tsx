import { useEffect, useState } from 'react'
import { Form, Input, Select, Button, Card, InputNumber, DatePicker, Switch, Alert, message } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import { useParams, useNavigate } from 'react-router-dom'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import { useCustomerSelect, useUserSelect } from '@/hooks/useSelectOptions'
import { usePageTitle } from '@/hooks/usePageTitle'
import { useDataDict } from '@/hooks/useDataDict'
import { useAutoSave } from '@/hooks/useAutoSave'
import AttachmentPanel from '@/components/AttachmentPanel'
import CustomFieldsPanel from '@/components/CustomFieldsPanel'
import dayjs from 'dayjs'

const defaultRiskOptions = [
  { label: '低', value: 'L' }, { label: '中', value: 'M' }, { label: '高', value: 'H' },
]
const defaultStatusOptions = [
  { label: '进行中', value: 'active' }, { label: '赢单', value: 'won' },
  { label: '丢单', value: 'lost' }, { label: '暂停', value: 'suspended' },
]
const defaultPaymentMethods = [
  { label: '电汇 TT', value: 'tt' },
  { label: '信用证 L/C', value: 'lc' },
  { label: '银行承兑汇票', value: 'bank_acceptance' },
  { label: '商业承兑汇票', value: 'commercial_acceptance' },
  { label: '分期付款', value: 'installment' },
  { label: '货到付款', value: 'cash_on_delivery' },
  { label: '其他', value: 'other' },
]

// 兼容历史数据：旧版 key_requirements_json 是单条 {summary, acceptance, confirmed}，
// 新版是多条数组 [{title, tech_spec, acceptance, confirmed}]。统一归一化为数组供表格录入。
type ReqRow = { title?: string; tech_spec?: string; acceptance?: string; confirmed?: boolean }
function normalizeRequirements(kr: unknown): ReqRow[] {
  if (Array.isArray(kr)) return kr as ReqRow[]
  if (kr && typeof kr === 'object') {
    const o = kr as Record<string, unknown>
    if (o.summary || o.acceptance || o.confirmed || o.title || o.tech_spec) {
      return [{
        title: (o.title as string) || '关键需求',
        tech_spec: (o.tech_spec as string) || (o.summary as string) || '',
        acceptance: (o.acceptance as string) || '',
        confirmed: !!o.confirmed,
      }]
    }
  }
  return []
}

export default function OpportunityForm() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const isEdit = !!id
  usePageTitle(isEdit ? '编辑商机' : '新建商机')

  const riskDict = useDataDict('risk_level', defaultRiskOptions)
  const statusDict = useDataDict('project_status', defaultStatusOptions)
  const paymentMethodDict = useDataDict('payment_method', defaultPaymentMethods)

  const customerSelect = useCustomerSelect()

  const userSelect = useUserSelect()
  const [customFields, setCustomFields] = useState<Record<string, unknown>>({})

  const { restoreDraft, clearDraft, markDirty } = useAutoSave(`opportunity_form_${id || 'new'}`, form)

  useEffect(() => {
    if (id) {
      projectApi.get(id).then((res) => {
        const d = res.data
        form.setFieldsValue({
          ...d,
          close_date_expect: d.close_date_expect ? dayjs(d.close_date_expect) : undefined,
          biz_date: d.biz_date ? dayjs(d.biz_date) : undefined,
          key_requirements_json: normalizeRequirements(d.key_requirements_json),
        })
        setCustomFields((d.custom_fields_json as Record<string, unknown>) || {})
        // Seed display names for Select components
        if (d.owner_id && d.owner_name) {
          userSelect.setInitialOption({ label: d.owner_name, value: d.owner_id })
        }
        if (d.customer_id) {
          const cid = d.customer_id
          customerApi.get(cid).then((r) => {
            if (r.data?.name) {
              customerSelect.setInitialOption({ label: r.data.name, value: cid })
            }
          }).catch(() => {})
        }
      }).catch(() => message.error('加载商机数据失败'))
    } else {
      const restored = restoreDraft()
      if (restored) message.info('已恢复上次未保存的草稿')
    }
  }, [id])

  const onFinish = async (values: Record<string, unknown>) => {
    setLoading(true)
    try {
      // 多条需求明细：丢弃完全空白的行；全空则存 []（闸门继续拦截 S3）
      const rows = (Array.isArray(values.key_requirements_json) ? values.key_requirements_json : []) as ReqRow[]
      const cleanedReqs = rows
        .filter((r) => r && ((r.title || '').trim() || (r.tech_spec || '').trim() || (r.acceptance || '').trim()))
        .map((r) => ({
          title: (r.title || '').trim() || '需求',
          tech_spec: (r.tech_spec || '').trim(),
          acceptance: (r.acceptance || '').trim(),
          confirmed: !!r.confirmed,
        }))
      const payload = {
        ...values,
        close_date_expect: values.close_date_expect ? (values.close_date_expect as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        biz_date: values.biz_date ? (values.biz_date as dayjs.Dayjs).format('YYYY-MM-DD') : undefined,
        key_requirements_json: cleanedReqs,
        custom_fields_json: customFields,
      }
      if (isEdit) {
        await projectApi.update(id!, payload)
        message.success('商机已更新')
      } else {
        await projectApi.create(payload)
        message.success('商机已创建')
      }
      clearDraft()
      navigate('/opportunities')
    } catch {
      message.error('保存失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4">{isEdit ? '编辑商机' : '新建商机'}</h2>
      <Card>
        <Form form={form} layout="vertical" onFinish={onFinish} onValuesChange={markDirty} className="max-w-2xl">
          <Form.Item name="name" label="项目名称" rules={[{ required: true, message: '请输入项目名称' }]}>
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item name="customer_id" label="关联客户" rules={[{ required: true, message: '请选择关联客户' }]}>
            <Select placeholder="请选择客户" showSearch filterOption={false}
              loading={customerSelect.loading}
              options={customerSelect.options}
              onSearch={customerSelect.onSearch}
              onDropdownVisibleChange={customerSelect.onDropdownVisibleChange} />
          </Form.Item>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Form.Item name="amount_expect" label="预期金额" rules={[{ required: true, message: '请输入预期金额' }]}>
              <InputNumber className="w-full" placeholder="请输入预期金额" min={0} precision={2} />
            </Form.Item>
            <Form.Item name="probability" label="成交概率 (%)" rules={[{ type: 'number', min: 0, max: 100, message: '概率范围 0-100' }]}>
              <InputNumber className="w-full" placeholder="0-100" min={0} max={100} />
            </Form.Item>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Form.Item name="close_date_expect" label="预期成交日期">
              <DatePicker className="w-full" />
            </Form.Item>
            <Form.Item name="biz_date" label="日期" tooltip="业务日期，可自行编辑，用于标识不同时间的商机">
              <DatePicker className="w-full" placeholder="请选择日期" />
            </Form.Item>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Form.Item name="risk_level" label="风险等级">
              <Select placeholder="请选择风险等级" allowClear options={riskDict.options} loading={riskDict.loading} />
            </Form.Item>
            <Form.Item name="payment_method" label="付款方式">
              <Select placeholder="请选择付款方式" allowClear options={paymentMethodDict.options} loading={paymentMethodDict.loading} />
            </Form.Item>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Form.Item name="has_guarantee" label="是否有保函" valuePropName="checked" tooltip="项目是否需要银行保函">
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
            <Form.Item name="has_weight_requirement" label="是否有重量要求" valuePropName="checked" tooltip="项目对设备重量是否有特殊要求">
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
            <Form.Item name="uses_idle_equipment" label="是否使用呆滞设备" valuePropName="checked" tooltip="是否使用库存呆滞设备">
              <Switch checkedChildren="是" unCheckedChildren="否" />
            </Form.Item>
          </div>
          {isEdit ? (
            <Form.Item name="owner_id" label="负责人"
              tooltip="负责人变更请在商机详情页使用「转移负责人」（需相应权限）">
              <Select disabled options={userSelect.options} />
            </Form.Item>
          ) : (
            <Form.Item label="负责人" tooltip="新建后默认负责人为当前用户（录入人），如需改派可在详情页转移">
              <Input disabled value="（创建后默认为当前用户）" />
            </Form.Item>
          )}
          <div className="border-t border-slate-100 pt-4 mt-2 mb-1">
            <div className="text-sm font-semibold text-slate-700">关键需求</div>
            <div className="text-xs text-slate-400 mb-3">推进到「S3 方案报价」前需填写。可新增多条需求，每条单独填写技术需求与验收标准。</div>
            <Form.List name="key_requirements_json">
              {(fields, { add, remove }) => (
                <>
                  {fields.map(({ key, name }) => (
                    <div key={key} className="border border-slate-200 rounded-lg p-3 mb-2 bg-slate-50/40">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xs font-bold text-slate-400 shrink-0">需求 {name + 1}</span>
                        <Form.Item name={[name, 'title']} className="!mb-0 flex-1"
                          rules={[{ required: true, message: '请填写需求标题' }]}>
                          <Input placeholder="需求标题，如：筛分效率≥92%、防爆电机" />
                        </Form.Item>
                        <Form.Item name={[name, 'confirmed']} valuePropName="checked" className="!mb-0">
                          <Switch checkedChildren="已确认" unCheckedChildren="待确认" />
                        </Form.Item>
                        <a className="text-rose-500 text-sm shrink-0" onClick={() => remove(name)}>删除</a>
                      </div>
                      <Form.Item name={[name, 'tech_spec']} className="!mb-2" label="技术需求">
                        <Input.TextArea rows={2} placeholder="技术规格 / 参数要求 / 约束条件" />
                      </Form.Item>
                      <Form.Item name={[name, 'acceptance']} className="!mb-0" label="验收标准">
                        <Input.TextArea rows={2} placeholder="可量化的验收标准 / 技术协议要点（可选）" />
                      </Form.Item>
                    </div>
                  ))}
                  <Button type="dashed" icon={<PlusOutlined />} onClick={() => add({ confirmed: false })} block>
                    添加需求
                  </Button>
                </>
              )}
            </Form.List>
          </div>
          {isEdit && (
            <Form.Item name="status" label="状态">
              <Select options={statusDict.options} loading={statusDict.loading} />
            </Form.Item>
          )}
          <Form.Item name="remark" label="备注">
            <Input.TextArea rows={3} placeholder="备注信息" />
          </Form.Item>
          <div className="mb-4">
            <CustomFieldsPanel entityType="project" values={customFields} onChange={setCustomFields} />
          </div>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading}>保存</Button>
            <Button className="ml-2" onClick={() => navigate('/opportunities')}>取消</Button>
          </Form.Item>
        </Form>
      </Card>

      {isEdit ? (
        <Card className="mt-4" title="附件">
          <AttachmentPanel bizType="project" bizId={id!} />
        </Card>
      ) : (
        <Alert
          className="mt-4"
          type="info"
          showIcon
          message="附件需保存后再上传"
          description="商机创建成功后，请在编辑页面或商机详情中的「附件」面板上传相关文件（保函扫描件、技术规格书等）。"
        />
      )}
    </div>
  )
}
