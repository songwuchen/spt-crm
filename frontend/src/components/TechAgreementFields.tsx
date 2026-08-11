/**
 * 技术协议评审表单分区（对齐简道云「合同技术协议评审」）。
 * native → 顶层字段；form → form_json.*
 */
import type { ReactNode } from 'react'
import { useEffect, useState } from 'react'
import { Form, Input, DatePicker, Select, Radio, AutoComplete } from 'antd'
import type { FormInstance } from 'antd'
import {
  TECH_AGREEMENT_SECTIONS,
  type TarFieldDef,
} from '@/constants/techAgreementReview'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { useUserSelect } from '@/hooks/useSelectOptions'
import PersonField from '@/components/lowcode/fields/PersonField'
import DeptField from '@/components/lowcode/fields/DeptField'
import client from '@/api/client'
import type { ApiResponse } from '@/api/types'

type Props = {
  form: FormInstance
  readOnly?: boolean
  /** 查看/审批详情时展示「审批填写」区；新建/编辑发起表单默认隐藏 */
  includeApproverSections?: boolean
  slots?: Partial<Record<'approve_files' | 'tech_files', ReactNode>>
}

type ContractRow = { id: string; contract_no?: string | null; drawing_no?: string | null }

/** 参考合同号：从合同管理取数，存/显图纸编号（可手输） */
function RefContractNoCombo({
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
      const r = await client.get<unknown, ApiResponse<ContractRow[]>>('/api/v1/lc/pickable-contracts', {
        params: { keyword: kw || undefined },
        headers: { 'X-Silent-Error': '1' },
      })
      const seen = new Set<string>()
      const next: { value: string; label: string }[] = []
      for (const row of r.data || []) {
        const draw = String(row.drawing_no || '').trim()
        if (!draw || seen.has(draw)) continue
        seen.add(draw)
        const cno = String(row.contract_no || '').trim()
        next.push({
          value: draw,
          label: cno && cno !== draw ? `${draw}（${cno}）` : draw,
        })
      }
      setOpts(next)
    } catch {
      setOpts([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <AutoComplete
      allowClear
      disabled={disabled}
      value={value}
      options={opts}
      placeholder="从合同管理按图纸编号选择，也可手输"
      onSearch={search}
      onFocus={() => { if (opts.length === 0) void search() }}
      onChange={(v) => onChange?.(v ?? '')}
      notFoundContent={loading ? '加载中…' : '无匹配图纸编号'}
      filterOption={false}
    />
  )
}

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

function ReadonlyText({ children }: { children: ReactNode }) {
  const empty = children == null || children === ''
  return (
    <div className="min-h-[32px] py-1 text-[15px] leading-6 text-slate-800 break-words whitespace-pre-wrap">
      {empty ? <span className="text-slate-400">—</span> : children}
    </div>
  )
}

function formatReadonlyDisplay(
  field: TarFieldDef,
  form: FormInstance,
  value: unknown,
): ReactNode {
  if (field.key === 'owner_id') return (form.getFieldValue('owner_name') as string) || ''
  if (field.key === 'applicant_id') return (form.getFieldValue('applicant_name') as string) || ''
  if (field.key === 'department_id') return (form.getFieldValue('department_name') as string) || ''

  if (value == null || value === '') return ''
  if (field.key === 'apply_at' || field.widget === 'date') {
    try {
      const d = new Date(String(value))
      if (!Number.isNaN(d.getTime())) return d.toLocaleString('zh-CN')
    } catch { /* fallthrough */ }
    return String(value)
  }
  if (Array.isArray(value)) {
    // person_multi 多为 id；若表单另有名称字段则上面已处理；此处尽量展示
    return value.length ? value.map(String).join('、') : ''
  }
  const opts = field.options || []
  if (opts.length) {
    const hit = opts.find((o) => o.value === value)
    if (hit) return hit.label
  }
  return String(value)
}

function FieldControl({
  field,
  form,
  readOnly,
  value,
  onChange,
  ...rest
}: {
  field: TarFieldDef
  form: FormInstance
  readOnly?: boolean
  value?: unknown
  onChange?: (...args: any[]) => void
  [k: string]: unknown
}) {
  const widget = field.widget || 'text'
  const opts = (field.options || []).map((o) => ({ value: o.value, label: o.label }))
  const control = { value, onChange, ...rest } as Record<string, unknown>

  // 查看态：纯文本，不用 disabled 控件
  if (readOnly) {
    if (widget === 'person_multi') {
      return (
        <PersonField
          value={value}
          multi
          readonly
          placeholder={`从组织架构选择${field.label}`}
        />
      )
    }
    return <ReadonlyText>{formatReadonlyDisplay(field, form, value)}</ReadonlyText>
  }

  if (widget === 'person') {
    const nameKey = field.key === 'applicant_id' ? 'applicant_name' : 'owner_name'
    return (
      <OrgPersonField
        form={form}
        nameKey={nameKey}
        value={value as string | undefined}
        onChange={onChange as ((v: string | undefined) => void) | undefined}
        placeholder={`从组织架构选择${field.label}`}
      />
    )
  }
  if (widget === 'department') {
    return (
      <DeptField
        value={value}
        placeholder="从组织架构选择部门"
        onChange={(v) => {
          const id = (typeof v === 'string' ? v : undefined) || undefined
          onChange?.(id)
          if (!id) {
            form.setFieldsValue({ department_name: undefined })
            return
          }
          void client
            .get<unknown, ApiResponse<Record<string, string>>>('/api/v1/lc/department-labels', {
              params: { ids: id },
              headers: { 'X-Silent-Error': '1' },
            })
            .then((res) => {
              const label = res.data?.[id]
              if (label) form.setFieldsValue({ department_name: label })
            })
            .catch(() => { /* keep previous name */ })
        }}
      />
    )
  }
  if (widget === 'person_multi') {
    return (
      <PersonField
        value={value}
        onChange={onChange as ((v: unknown) => void) | undefined}
        multi
        placeholder={`从组织架构选择${field.label}`}
      />
    )
  }
  if (widget === 'radio') {
    const useBtn = opts.length <= 4 && opts.every((o) => o.label.length <= 8)
    if (useBtn) {
      return (
        <Radio.Group
          {...control}
          optionType="button"
          buttonStyle="solid"
          className="flex flex-wrap gap-1"
        >
          {opts.map((o) => (
            <Radio.Button key={o.value} value={o.value}>{o.label}</Radio.Button>
          ))}
        </Radio.Group>
      )
    }
    return (
      <Radio.Group {...control} className="flex flex-wrap gap-x-3 gap-y-1">
        {opts.map((o) => (
          <Radio key={o.value} value={o.value}>{o.label}</Radio>
        ))}
      </Radio.Group>
    )
  }
  if (widget === 'date') {
    return <DatePicker {...control} className="w-full" showTime />
  }
  if (widget === 'textarea') {
    return <Input.TextArea {...control} rows={3} />
  }
  if (widget === 'combo' || field.key === 'ref_contract_no') {
    return (
      <RefContractNoCombo
        value={value as string | undefined}
        onChange={onChange as ((v: string) => void) | undefined}
      />
    )
  }
  return <Input {...control} allowClear />
}

function renderField(f: TarFieldDef, form: FormInstance, readOnly?: boolean) {
  const name = f.source === 'native' ? f.key : ['form_json', f.key]
  const rules = !readOnly && f.required
    ? [{
        required: true,
        message: f.widget === 'person' || f.widget === 'department' || f.widget === 'person_multi'
          ? `请选择${f.label}`
          : `请填写${f.label}`,
        ...(f.widget === 'person_multi' ? { type: 'array' as const, min: 1 } : {}),
      }]
    : undefined
  return (
    <Form.Item
      key={f.key}
      name={name}
      label={f.label}
      rules={rules}
      required={readOnly ? false : !!f.required}
      className="mb-3"
    >
      <FieldControl field={f} form={form} readOnly={readOnly} />
    </Form.Item>
  )
}

export default function TechAgreementFields({ form, readOnly, includeApproverSections, slots }: Props) {
  return (
    <>
      {TECH_AGREEMENT_SECTIONS.map((sec) => {
        // 发起表单不展示审批节点填写区
        if (sec.fillStage === 'approver' && !includeApproverSections) return null
        const fields = includeApproverSections
          ? sec.fields
          : sec.fields.filter((f) => (f.fillStage || 'initiator') !== 'approver')
        const after = includeApproverSections
          ? (sec.fieldsAfterSlot || [])
          : (sec.fieldsAfterSlot || []).filter((f) => (f.fillStage || 'initiator') !== 'approver')
        return (
          <div key={sec.key} className="mb-6">
            <ContractSectionTitle title={sec.title} />
            {sec.fillStage === 'approver' && (
              <p className="text-xs text-slate-400 mb-2 m-0">
                由总工填写「设计审批」、设计审批1 填写「设计审批2」；审批过程中写回。
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
              {fields.map((f) => renderField(f, form, readOnly))}
            </div>
            {sec.afterSlot === 'approve_files' && slots?.approve_files}
            {sec.afterSlot === 'tech_files' && slots?.tech_files}
            {after.length ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 mt-2">
                {after.map((f) => renderField(f, form, readOnly))}
              </div>
            ) : null}
          </div>
        )
      })}
    </>
  )
}
