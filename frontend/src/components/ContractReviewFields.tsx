/**
 * 合同评审表单分区（对齐简道云「合同评审」）。
 * native → 顶层字段；reg → review_json.*
 */
import type { ReactNode } from 'react'
import { Form, Input, InputNumber, DatePicker, Select, Radio, Checkbox } from 'antd'
import type { FormInstance } from 'antd'
import {
  CONTRACT_REVIEW_SECTIONS,
  type ReviewAfterSlot,
  type ReviewFieldDef,
  type ReviewShowWhen,
} from '@/constants/contractReview'
import ContractSectionTitle from '@/components/ContractSectionTitle'

type Props = {
  form: FormInstance
  mode?: 'create' | 'edit'
  readOnly?: boolean
  slots?: Partial<Record<ReviewAfterSlot, ReactNode>>
}

function readDepValue(values: Record<string, unknown>, dep: ReviewShowWhen): unknown {
  if ((dep.source || 'reg') === 'native') return values[dep.field]
  const reg = (values.review_json || {}) as Record<string, unknown>
  return reg[dep.field]
}

function isVisible(field: ReviewFieldDef, values: Record<string, unknown>): boolean {
  const sw = field.showWhen
  if (!sw) return true
  const v = readDepValue(values, sw)
  if (sw.equals?.length) {
    return sw.equals.includes(v == null ? '' : String(v))
  }
  return v != null && v !== ''
}

function FieldControl({ field, readOnly }: { field: ReviewFieldDef; readOnly?: boolean }) {
  const widget = field.widget || 'text'
  const opts = (field.options || []).map((o) => ({ value: o.value, label: o.label }))
  const disabled = !!readOnly

  if (widget === 'radio') {
    const useBtn = opts.length <= 4 && opts.every((o) => o.label.length <= 8)
    if (useBtn) {
      return (
        <Radio.Group disabled={disabled} optionType="button" buttonStyle="solid" className="flex flex-wrap gap-1">
          {opts.map((o) => (
            <Radio.Button key={o.value} value={o.value}>{o.label}</Radio.Button>
          ))}
        </Radio.Group>
      )
    }
    return (
      <Radio.Group disabled={disabled} className="flex flex-wrap gap-x-3 gap-y-1">
        {opts.map((o) => (
          <Radio key={o.value} value={o.value}>{o.label}</Radio>
        ))}
      </Radio.Group>
    )
  }
  if (widget === 'checkbox') {
    return <Checkbox.Group disabled={disabled} options={opts} className="flex flex-wrap gap-x-3 gap-y-1" />
  }
  if (widget === 'select') {
    return <Select disabled={disabled} allowClear showSearch optionFilterProp="label" options={opts} placeholder="请选择" />
  }
  if (widget === 'date') {
    return <DatePicker disabled={disabled} className="w-full" showTime />
  }
  if (widget === 'money' || widget === 'number') {
    return <InputNumber disabled={disabled} className="w-full" min={0} precision={widget === 'money' ? 2 : undefined} />
  }
  if (widget === 'textarea') {
    return <Input.TextArea disabled={disabled} rows={2} />
  }
  return <Input disabled={disabled} allowClear />
}

function FieldGrid({
  fields,
  values,
  readOnly,
}: {
  fields: ReviewFieldDef[]
  values: Record<string, unknown>
  readOnly?: boolean
}) {
  const visible = fields.filter((f) => isVisible(f, values))
  if (!visible.length) return null
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
      {visible.map((f) => {
        const name = f.source === 'native' ? f.key : ['review_json', f.key]
        const spanFull = f.widget === 'checkbox' || f.widget === 'textarea'
        const needRequired = !readOnly && (f.required || (f.requiredWhen
          ? isVisible({ ...f, showWhen: f.requiredWhen }, values)
          : false))
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
            <FieldControl field={f} readOnly={readOnly} />
          </Form.Item>
        )
      })}
    </div>
  )
}

export default function ContractReviewFields({ form, readOnly, slots }: Props) {
  const reviewWatch = Form.useWatch('review_json', form) as Record<string, unknown> | undefined
  const reviewType = Form.useWatch('review_type', form)
  const isExport = Form.useWatch('is_export', form)
  const values: Record<string, unknown> = {
    review_type: reviewType,
    is_export: isExport,
    review_json: reviewWatch || {},
  }

  return (
    <div className="space-y-5">
      {CONTRACT_REVIEW_SECTIONS.map((sec) => (
        <div key={sec.key}>
          <ContractSectionTitle title={sec.title} />
          <FieldGrid fields={sec.fields} values={values} readOnly={readOnly} />
          {sec.afterSlot && slots?.[sec.afterSlot] ? (
            <div className="my-4">{slots[sec.afterSlot]}</div>
          ) : null}
          {sec.fieldsAfterSlot?.length ? (
            <FieldGrid fields={sec.fieldsAfterSlot} values={values} readOnly={readOnly} />
          ) : null}
        </div>
      ))}
      {!readOnly && (
        <div className="text-[12px] text-slate-400">
          标 <span className="text-rose-500">*</span> 为必填。字段对齐简道云「合同评审」。
        </div>
      )}
    </div>
  )
}
