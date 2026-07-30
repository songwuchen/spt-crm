/**
 * 合同登记表单分区（对齐简道云「合同登记表」字段顺序 + 控件类型 + 动态显隐）。
 * native → 表单顶层字段；reg → registration_json.*
 * 子表通过 slots 插在简道云 subform 对应位置。
 */
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

function FieldControl({ field }: { field: RegFieldDef }) {
  const widget = field.widget || 'text'
  const opts = (field.options || []).map((o) => ({ value: o.value, label: o.label }))

  if (widget === 'radio') {
    const useBtn = opts.length <= 4 && opts.every((o) => o.label.length <= 8)
    if (useBtn) {
      return (
        <Radio.Group optionType="button" buttonStyle="solid" className="flex flex-wrap gap-1">
          {opts.map((o) => (
            <Radio.Button key={o.value} value={o.value}>{o.label}</Radio.Button>
          ))}
        </Radio.Group>
      )
    }
    return (
      <Radio.Group className="flex flex-wrap gap-x-3 gap-y-1">
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
  values,
}: {
  fields: RegFieldDef[]
  mode: 'create' | 'edit'
  regOnly: boolean
  values: Record<string, unknown>
}) {
  const visible = fields.filter((f) => {
    if (mode === 'create' && CREATE_SKIP.has(f.key)) return false
    if (regOnly && f.source === 'native') return false
    return isVisible(f, values)
  })
  if (!visible.length) return null
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
      {visible.map((f) => {
        const name = f.source === 'native' ? f.key : ['registration_json', f.key]
        const spanFull = f.widget === 'checkbox' || f.widget === 'textarea' || f.key === 'paint_req'
        const needRequired = f.required || (f.requiredWhen ? isVisible({ ...f, showWhen: f.requiredWhen }, values) : false)
        return (
          <Form.Item
            key={f.key}
            name={name}
            label={f.label}
            className="mb-3"
            style={spanFull ? { gridColumn: '1 / -1' } : undefined}
            rules={needRequired ? [{
              required: true,
              message: `请填写${f.label}`,
              type: f.widget === 'checkbox' ? 'array' : undefined,
              ...(f.widget === 'checkbox' ? { min: 1 } : {}),
            } as object] : undefined}
          >
            <FieldControl field={f} />
          </Form.Item>
        )
      })}
    </div>
  )
}

export default function ContractRegistrationFields({
  form,
  mode = 'edit',
  regOnly = false,
  slots,
}: Props) {
  const changeType = Form.useWatch('change_type', form)
  const regWatch = Form.useWatch('registration_json', form) as Record<string, unknown> | undefined
  const values: Record<string, unknown> = {
    change_type: changeType,
    registration_json: regWatch || {},
  }

  return (
    <div className="space-y-5">
      {CONTRACT_REGISTRATION_SECTIONS.map((sec) => (
        <div key={sec.key}>
          <ContractSectionTitle title={sec.title} />
          <FieldGrid fields={sec.fields} mode={mode} regOnly={regOnly} values={values} />
          {sec.afterSlot && slots?.[sec.afterSlot] ? (
            <div className="my-4">{slots[sec.afterSlot]}</div>
          ) : null}
          {sec.fieldsAfterSlot?.length ? (
            <FieldGrid fields={sec.fieldsAfterSlot} mode={mode} regOnly={regOnly} values={values} />
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
