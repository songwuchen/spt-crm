/**
 * 合同登记表单分区（对齐简道云「合同登记表」字段顺序 + 控件类型 + 动态显隐）。
 * native → 表单顶层字段；reg → registration_json.*
 * 子表通过 slots 插在简道云 subform 对应位置。
 * 合同/项目评审流水号支持选评审记录带出（对齐简道云 linkfield）。
 */
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Form, Input, InputNumber, DatePicker, Select, Radio, Checkbox, AutoComplete } from 'antd'
import type { FormInstance } from 'antd'
import {
  CONTRACT_REGISTRATION_SECTIONS,
  type RegAfterSlot,
  type RegFieldDef,
  type RegShowWhen,
} from '@/constants/contractRegistration'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { PolicyItem, useFieldPolicy } from '@/components/lowcode/FieldPolicy'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'

const DATE_KEYS = new Set([
  'delivery_date', 'order_date', 'card_date', 'end_date', 'note_date', 'accept_date',
])
const NATIVE_KEYS = new Set([
  'contract_no', 'drawing_no', 'peer_contract_no', 'acquire_method',
  'delivery_date', 'change_type', 'amount_total', 'order_date', 'card_date', 'end_date',
  'assignee_name', 'department_name',
])

const CREATE_SKIP = new Set(['contract_no'])

type Props = {
  form: FormInstance
  mode?: 'create' | 'edit'
  regOnly?: boolean
  slots?: Partial<Record<RegAfterSlot, ReactNode>>
}

function readDepValue(
  values: Record<string, unknown>,
  dep: RegShowWhen,
): unknown {
  if ((dep.source || 'reg') === 'native') return values[dep.field]
  const reg = (values.registration_json || {}) as Record<string, unknown>
  return reg[dep.field]
}

function isVisible(field: RegFieldDef, values: Record<string, unknown>): boolean {
  const sw = field.showWhen
  if (!sw) return true
  const v = readDepValue(values, sw)
  if (sw.equals?.length) {
    const s = v == null ? '' : String(v)
    return sw.equals.includes(s)
  }
  return v != null && v !== ''
}

/** 对齐简道云「选择合同/项目评审」：选中后回填流水号及相关字段；也可手输流水号 */
function ReviewSnPicker({
  value,
  onChange,
  form,
}: {
  value?: string
  onChange?: (v: string) => void
  form: FormInstance
}) {
  const [opts, setOpts] = useState<{ label: string; value: string; review: ContractReview }[]>([])
  const [loading, setLoading] = useState(false)
  const search = async (kw?: string) => {
    setLoading(true)
    try {
      const r = await contractReviewApi.list({ pageNo: 1, pageSize: 20, keyword: kw || undefined })
      setOpts((r.data?.items || []).map((rev) => ({
        value: rev.review_code,
        label: `${rev.review_code}${rev.company_name ? ` · ${rev.company_name}` : ''}${rev.project_title ? ` · ${rev.project_title}` : ''}`,
        review: rev,
      })))
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }
  const applyReview = (code: string) => {
    onChange?.(code || '')
    const hit = opts.find((o) => o.value === code)?.review
    if (!hit) return
    const reg = { ...(form.getFieldValue('registration_json') || {}) } as Record<string, unknown>
    reg.review_sn = code
    if (hit.project_title) reg.project_name = hit.project_title
    if (hit.is_export) reg.is_export = hit.is_export
    if (hit.need_install) reg.need_install = hit.need_install
    if (hit.payment_term) reg.payment_desc = hit.payment_term
    if (hit.delivery_period) reg.delivery_clause = hit.delivery_period
    form.setFieldsValue({
      registration_json: reg,
      ...(hit.department_name ? { department_name: hit.department_name } : {}),
      ...(hit.owner_name ? { assignee_name: hit.owner_name } : {}),
      ...(hit.contract_amount != null && form.getFieldValue('amount_total') == null
        ? { amount_total: hit.contract_amount }
        : {}),
    })
  }
  return (
    <AutoComplete
      allowClear
      value={value}
      options={opts.map((o) => ({ value: o.value, label: o.label }))}
      placeholder="搜索选择合同评审，或直接填写流水号"
      onSearch={search}
      onFocus={() => { if (opts.length === 0) void search() }}
      onSelect={(v) => applyReview(String(v))}
      onChange={(v) => onChange?.(v ?? '')}
      notFoundContent={loading ? '加载中…' : undefined}
    />
  )
}

function FieldControl({ field, form }: { field: RegFieldDef; form: FormInstance }) {
  const widget = field.widget || 'text'
  const opts = (field.options || []).map((o) => ({ value: o.value, label: o.label }))

  if (field.key === 'review_sn') {
    return <ReviewSnPicker form={form} />
  }

  // 显隐依赖字段：写入时展开新对象，避免 antd 对嵌套 registration_json 原地改值导致不刷新
  const SHOW_TRIGGERS = new Set([
    'info_complete', 'is_export', 'standard_delivery', 'is_rotary_sieve', 'has_intelligence',
  ])
  const patchReg = (key: string, val: unknown) => {
    const reg = { ...(form.getFieldValue('registration_json') || {}) } as Record<string, unknown>
    reg[key] = val
    if (key === 'standard_delivery' && val !== '是') delete reg.delivery_mode
    if (key === 'info_complete' && val !== '否') {
      delete reg.missing_items
      delete reg.info_incomplete_note
    }
    if (key === 'is_export' && val !== '是') delete reg.export_type
    if (key === 'is_rotary_sieve' && val !== '是') delete reg.fill_code
    if (key === 'has_intelligence' && val !== '是') delete reg.smart_points
    form.setFieldsValue({ registration_json: reg })
  }

  if (widget === 'radio') {
    const useBtn = opts.length <= 4 && opts.every((o) => o.label.length <= 8)
    const trigger = SHOW_TRIGGERS.has(field.key)
    if (useBtn) {
      return (
        <Radio.Group
          optionType="button"
          buttonStyle="solid"
          className="flex flex-wrap gap-1"
          onChange={trigger ? (e) => patchReg(field.key, e.target.value) : undefined}
        >
          {opts.map((o) => (
            <Radio.Button key={o.value} value={o.value}>{o.label}</Radio.Button>
          ))}
        </Radio.Group>
      )
    }
    return (
      <Radio.Group
        className="flex flex-wrap gap-x-3 gap-y-1"
        onChange={trigger ? (e) => patchReg(field.key, e.target.value) : undefined}
      >
        {opts.map((o) => (
          <Radio key={o.value} value={o.value}>{o.label}</Radio>
        ))}
      </Radio.Group>
    )
  }
  if (widget === 'checkbox') {
    return <Checkbox.Group options={opts} className="flex flex-wrap gap-x-3 gap-y-1" />
  }
  if (widget === 'select') {
    if (opts.length) {
      return (
        <Select
          allowClear
          showSearch
          optionFilterProp="label"
          options={opts}
          placeholder="请选择"
        />
      )
    }
    return <AutoComplete allowClear options={[]} placeholder="请输入或选择" filterOption />
  }
  if (widget === 'date' || DATE_KEYS.has(field.key)) {
    return <DatePicker className="w-full" />
  }
  if (widget === 'money' || widget === 'number') {
    return <InputNumber className="w-full" min={0} precision={widget === 'money' ? 2 : undefined} />
  }
  if (widget === 'textarea') {
    return <Input.TextArea rows={2} />
  }
  return <Input allowClear />
}

function FieldGrid({
  fields,
  mode,
  regOnly,
  form,
}: {
  fields: RegFieldDef[]
  mode: 'create' | 'edit'
  regOnly: boolean
  form: FormInstance
}) {
  const policy = useFieldPolicy()
  const catalogById = new Map(
    (policy.nativeFields || []).map((fd) => [fd.id, fd as { id: string; json_storage?: string }]),
  )

  // shouldUpdate 保证嵌套 registration_json 变更时重算；策略显隐由 PolicyItem 负责
  return (
    <Form.Item noStyle shouldUpdate>
      {() => {
        const all = form.getFieldsValue(true) as Record<string, unknown>
        const values: Record<string, unknown> = {
          change_type: all.change_type,
          registration_json: (all.registration_json as Record<string, unknown>) || {},
        }
        const visible = fields.filter((f) => {
          if (mode === 'create' && CREATE_SKIP.has(f.key)) return false
          if (regOnly && f.source === 'native') return false
          const inCatalog = catalogById.has(f.key)
          const state = policy.states[f.key]
          // 已进字段策略：显隐交给 PolicyItem / states（与自定义字段同一套规则引擎）
          if (inCatalog && policy.loaded && state && !policy.failed) {
            return state.visible
          }
          // 策略未就绪或未编目：回退本地 showWhen（与改造前一致）
          return isVisible(f, values)
        })
        if (!visible.length) return null
        return (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
            {visible.map((f) => {
              const spanFull = f.widget === 'checkbox' || f.widget === 'textarea' || f.key === 'paint_req'
              const inCatalog = catalogById.has(f.key)
              const state = policy.states[f.key]
              const policyOwns = inCatalog && policy.loaded && !!state && !policy.failed
              const needRequired = policyOwns
                ? false
                : (f.required || (f.requiredWhen ? isVisible({ ...f, showWhen: f.requiredWhen }, values) : false))
              const itemProps = {
                label: f.label,
                className: 'mb-3',
                style: spanFull ? { gridColumn: '1 / -1' } : undefined,
                rules: needRequired ? [{
                  required: true,
                  message: `请填写${f.label}`,
                  type: f.widget === 'checkbox' ? 'array' : undefined,
                  ...(f.widget === 'checkbox' ? { min: 1 } : {}),
                } as object] : undefined,
              }
              const cat = catalogById.get(f.key)
              const namePath = (f.source === 'reg' || cat?.json_storage)
                ? (['registration_json', f.key] as (string | number)[])
                : f.key
              if (f.source === 'native' || inCatalog) {
                return (
                  <PolicyItem key={f.key} name={namePath} {...itemProps}>
                    <FieldControl field={f} form={form} />
                  </PolicyItem>
                )
              }
              return (
                <Form.Item
                  key={f.key}
                  name={['registration_json', f.key]}
                  {...itemProps}
                >
                  <FieldControl field={f} form={form} />
                </Form.Item>
              )
            })}
          </div>
        )
      }}
    </Form.Item>
  )
}

export default function ContractRegistrationFields({
  form,
  mode = 'edit',
  regOnly = false,
  slots,
}: Props) {
  return (
    <div className="space-y-5">
      {CONTRACT_REGISTRATION_SECTIONS.map((sec) => (
        <div key={sec.key}>
          <ContractSectionTitle title={sec.title} />
          <FieldGrid fields={sec.fields} mode={mode} regOnly={regOnly} form={form} />
          {sec.afterSlot && slots?.[sec.afterSlot] ? (
            <div className="my-4">{slots[sec.afterSlot]}</div>
          ) : null}
          {sec.fieldsAfterSlot?.length ? (
            <FieldGrid fields={sec.fieldsAfterSlot} mode={mode} regOnly={regOnly} form={form} />
          ) : null}
        </div>
      ))}
      <div className="text-[12px] text-slate-400">
        标 <span className="text-rose-500">*</span> 为必填。附件可直接在对应分区选择/上传。
      </div>
    </div>
  )
}

export { NATIVE_KEYS, DATE_KEYS }
