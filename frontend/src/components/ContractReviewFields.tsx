/**
 * 合同评审表单分区（对齐简道云「合同评审」）。
 * native → 顶层字段；reg → review_json.*
 * 业务员/区域经理/部门/反馈成员走组织架构选人（对齐 JDY user/dept/usergroup）。
 */
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Form, Input, InputNumber, DatePicker, Select, Radio, Checkbox, AutoComplete } from 'antd'
import type { FormInstance } from 'antd'
import {
  CONTRACT_REVIEW_SECTIONS,
  reviewDepVisible,
  type ReviewAfterSlot,
  type ReviewFieldDef,
} from '@/constants/contractReview'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import DepartmentSelect from '@/components/DepartmentSelect'
import PersonField from '@/components/lowcode/fields/PersonField'
import { contractApi } from '@/api/contract'

type Props = {
  form: FormInstance
  mode?: 'create' | 'edit'
  readOnly?: boolean
  slots?: Partial<Record<ReviewAfterSlot, ReactNode>>
}

function isVisible(field: ReviewFieldDef, values: Record<string, unknown>): boolean {
  return reviewDepVisible(field.showWhen, values)
}

/** 组织架构选人；同步写 companion name 字段 */
function OrgPersonField({
  form,
  nameKey,
  value,
  onChange,
  placeholder = '从组织架构选择',
  disabled,
}: {
  form: FormInstance
  nameKey: string
  value?: string
  onChange?: (v: string | undefined) => void
  placeholder?: string
  disabled?: boolean
}) {
  const userSelect = useUserSelect()
  useEffect(() => {
    const name = form.getFieldValue(nameKey) as string | undefined
    if (value && name) userSelect.setInitialOption({ value, label: name })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])
  return (
    <Select
      allowClear
      showSearch
      disabled={disabled}
      filterOption={false}
      placeholder={placeholder}
      value={value}
      loading={userSelect.loading}
      options={userSelect.options}
      onSearch={userSelect.onSearch}
      onDropdownVisibleChange={userSelect.onDropdownVisibleChange}
      onChange={(v, opt) => {
        const id = (v as string | undefined) || undefined
        const label = (opt as { label?: string } | undefined)?.label
        onChange?.(id)
        form.setFieldsValue({ [nameKey]: id ? (label || undefined) : undefined })
      }}
    />
  )
}

function OrgDepartmentField({
  form,
  nameKey = 'department_name',
  value,
  onChange,
  disabled,
}: {
  form: FormInstance
  nameKey?: string
  value?: string
  onChange?: (v: string | undefined) => void
  disabled?: boolean
}) {
  return (
    <DepartmentSelect
      value={value}
      disabled={disabled}
      placeholder="从组织架构选择部门"
      onChange={(id, label) => {
        onChange?.(id)
        form.setFieldsValue({ [nameKey]: id ? (label || undefined) : undefined })
      }}
    />
  )
}

/** 图纸编号：可自由输入 + 从合同图纸对应表联想（对齐 JDY combo） */
function DrawingNoCombo({
  value,
  onChange,
  disabled,
}: {
  value?: string
  onChange?: (v: string) => void
  disabled?: boolean
}) {
  const [opts, setOpts] = useState<{ value: string; label: string }[]>([])
  const [loading, setLoading] = useState(false)

  const search = async (kw?: string) => {
    setLoading(true)
    try {
      const r = await contractApi.drawingMapLookups({ keyword: kw || undefined, limit: 50 })
      const seen = new Set<string>()
      const next: { value: string; label: string }[] = []
      for (const row of r.data || []) {
        const no = (row.drawing_no || '').trim()
        if (!no || seen.has(no)) continue
        seen.add(no)
        next.push({ value: no, label: no })
      }
      setOpts(next)
    } catch { /* ignore */ } finally {
      setLoading(false)
    }
  }

  return (
    <AutoComplete
      allowClear
      disabled={disabled}
      value={value}
      options={opts}
      placeholder="可输入或从合同图纸对应表选择"
      onSearch={search}
      onFocus={() => { if (opts.length === 0) void search() }}
      onChange={(v) => onChange?.(v ?? '')}
      notFoundContent={loading ? '加载中…' : undefined}
    />
  )
}

function FieldControl({
  field,
  form,
  readOnly,
  value,
  onChange,
  ...rest
}: {
  field: ReviewFieldDef
  form: FormInstance
  readOnly?: boolean
  value?: unknown
  onChange?: (...args: any[]) => void
  [k: string]: unknown
}) {
  const widget = field.widget || 'text'
  const opts = (field.options || []).map((o) => ({ value: o.value, label: o.label }))
  const disabled = !!readOnly
  const control = { value, onChange, ...rest } as Record<string, unknown>

  if (widget === 'person' || field.key === 'owner_id' || field.key === 'region_manager_id') {
    const nameKey = field.key === 'region_manager_id' ? 'region_manager_name' : 'owner_name'
    return (
      <OrgPersonField
        form={form}
        nameKey={nameKey}
        value={value as string | undefined}
        onChange={onChange as ((v: string | undefined) => void) | undefined}
        placeholder={`从组织架构选择${field.label}`}
        disabled={disabled}
      />
    )
  }
  if (widget === 'department' || field.key === 'department_id') {
    return (
      <OrgDepartmentField
        form={form}
        value={value as string | undefined}
        onChange={onChange as ((v: string | undefined) => void) | undefined}
        disabled={disabled}
      />
    )
  }
  if (widget === 'person_multi' || field.key === 'feedback_members') {
    return (
      <PersonField
        value={value}
        onChange={onChange as ((v: unknown) => void) | undefined}
        multi
        readonly={disabled}
        placeholder={`从组织架构选择${field.label}`}
      />
    )
  }

  if (widget === 'radio') {
    const useBtn = opts.length <= 4 && opts.every((o) => o.label.length <= 8)
    const handleRadio = (e: { target: { value?: unknown } }) => {
      onChange?.(e)
    }
    if (useBtn) {
      return (
        <Radio.Group
          {...control}
          disabled={disabled}
          optionType="button"
          buttonStyle="solid"
          className="flex flex-wrap gap-1"
          onChange={handleRadio}
        >
          {opts.map((o) => (
            <Radio.Button key={o.value} value={o.value}>{o.label}</Radio.Button>
          ))}
        </Radio.Group>
      )
    }
    return (
      <Radio.Group
        {...control}
        disabled={disabled}
        className="flex flex-wrap gap-x-3 gap-y-1"
        onChange={handleRadio}
      >
        {opts.map((o) => (
          <Radio key={o.value} value={o.value}>{o.label}</Radio>
        ))}
      </Radio.Group>
    )
  }
  if (widget === 'checkbox') {
    return <Checkbox.Group {...control} disabled={disabled} options={opts} className="flex flex-wrap gap-x-3 gap-y-1" />
  }
  if (widget === 'select') {
    return (
      <Select
        {...control}
        disabled={disabled}
        allowClear
        showSearch
        optionFilterProp="label"
        options={opts}
        placeholder="请选择"
      />
    )
  }
  if (widget === 'date') {
    return <DatePicker {...control} disabled={disabled} className="w-full" showTime />
  }
  if (widget === 'money' || widget === 'number') {
    return (
      <InputNumber
        disabled={disabled}
        className="w-full"
        min={0}
        precision={widget === 'money' ? 2 : undefined}
        value={value as number | null | undefined}
        onChange={(v) => onChange?.(v)}
      />
    )
  }
  if (widget === 'textarea') {
    return <Input.TextArea {...control} disabled={disabled} rows={2} />
  }
  if (widget === 'combo' || field.key === 'drawing_no') {
    return (
      <DrawingNoCombo
        value={value as string | undefined}
        onChange={onChange as ((v: string) => void) | undefined}
        disabled={disabled}
      />
    )
  }
  return <Input {...control} disabled={disabled} allowClear />
}

function buildRequiredRules(f: ReviewFieldDef): object[] {
  const msg = f.widget === 'person' || f.widget === 'department' || f.widget === 'person_multi'
    ? `请选择${f.label}`
    : `请填写${f.label}`
  // InputNumber 值为 number/null；antd 默认 required 对数字易误判，需 type:'number' 或显式 validator
  if (f.widget === 'number' || f.widget === 'money') {
    return [{
      validator: (_: unknown, v: unknown) => {
        if (v === null || v === undefined || v === '') {
          return Promise.reject(new Error(msg))
        }
        if (typeof v === 'number' && Number.isNaN(v)) {
          return Promise.reject(new Error(msg))
        }
        return Promise.resolve()
      },
    }]
  }
  if (f.widget === 'checkbox' || f.widget === 'person_multi') {
    return [{ required: true, message: msg, type: 'array' as const, min: 1 }]
  }
  return [{ required: true, message: msg }]
}

function FieldGrid({
  fields,
  values,
  form,
  readOnly,
}: {
  fields: ReviewFieldDef[]
  values: Record<string, unknown>
  form: FormInstance
  readOnly?: boolean
}) {
  // 创建/编辑：审批填写 / 仅详情展示字段不出现；详情只读仍展示（并遵守 showWhen）
  const visible = fields.filter((f) => {
    if (!readOnly && (f.fillStage === 'approver' || f.fillStage === 'display')) return false
    return isVisible(f, values)
  })
  if (!visible.length) return null
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-3">
      {visible.map((f) => {
        const name = f.source === 'native' ? f.key : ['review_json', f.key]
        const spanFull = f.widget === 'checkbox' || f.widget === 'textarea' || f.widget === 'person_multi'
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
            rules={needRequired ? buildRequiredRules(f) : undefined}
          >
            <FieldControl field={f} form={form} readOnly={readOnly} />
          </Form.Item>
        )
      })}
    </div>
  )
}

function sectionVisibleFields(
  fields: ReviewFieldDef[],
  values: Record<string, unknown>,
  readOnly?: boolean,
): ReviewFieldDef[] {
  return fields.filter((f) => {
    if (!readOnly && (f.fillStage === 'approver' || f.fillStage === 'display')) return false
    return isVisible(f, values)
  })
}

export default function ContractReviewFields({ form, readOnly, slots }: Props) {
  const reviewWatch = Form.useWatch('review_json', form) as Record<string, unknown> | undefined
  const reviewType = Form.useWatch('review_type', form)
  const isExport = Form.useWatch('is_export', form)
  const needPricing = Form.useWatch('need_pricing', form)
  const values: Record<string, unknown> = {
    review_type: reviewType,
    is_export: isExport,
    need_pricing: needPricing,
    review_json: { ...(reviewWatch || {}) },
  }
  // 联系信息 / 核价附件：仅合同评审（新建已固定为合同评审）
  const showContacts = !reviewType || reviewType === '合同评审'
  const showPricingSlot = needPricing === '有核价' && showContacts
  // 附件：有评审类型即显示（历史项目评审详情仍可见）
  const showReviewFiles = !!reviewType || !readOnly

  return (
    <div className="space-y-5">
      {CONTRACT_REVIEW_SECTIONS.map((sec) => {
        const visibleMain = sectionVisibleFields(sec.fields, values, readOnly)
        const visibleAfter = sectionVisibleFields(sec.fieldsAfterSlot || [], values, readOnly)
        const showSlotCreate = !readOnly && sec.afterSlot && sec.afterSlot !== 'feedback_files'
          && (sec.afterSlot !== 'contacts' || showContacts)
          && (sec.afterSlot !== 'pricing_files' || showPricingSlot)
          && (sec.afterSlot !== 'review_files' || showReviewFiles)
          && !!slots?.[sec.afterSlot]
        // 详情只读：联系人/核价/主附件同样按简道云显隐
        const showSlotDetail = !!readOnly && !!sec.afterSlot && !!slots?.[sec.afterSlot]
          && (sec.afterSlot !== 'contacts' || showContacts)
          && (sec.afterSlot !== 'pricing_files' || showPricingSlot)
          && (sec.afterSlot !== 'review_files' || showReviewFiles)
        if (!visibleMain.length && !visibleAfter.length && !showSlotCreate && !showSlotDetail) {
          return null
        }

        return (
          <div key={sec.key}>
            <ContractSectionTitle title={sec.title} />
            <FieldGrid fields={sec.fields} values={values} form={form} readOnly={readOnly} />
            {showSlotDetail ? <div className="my-4">{slots![sec.afterSlot!]}</div> : null}
            {showSlotCreate ? <div className="my-4">{slots![sec.afterSlot!]}</div> : null}
            {sec.fieldsAfterSlot?.length ? (
              <FieldGrid fields={sec.fieldsAfterSlot} values={values} form={form} readOnly={readOnly} />
            ) : null}
          </div>
        )
      })}
      {!readOnly && (
        <div className="text-[12px] text-slate-400">
          标 <span className="text-rose-500">*</span> 为必填（对齐简道云显隐与带 * 字段）。
          风险按「合同评审」规则显隐（简道云已取消项目评审）；风险 / 结论 / 签约在审批节点填写。
        </div>
      )}
    </div>
  )
}
