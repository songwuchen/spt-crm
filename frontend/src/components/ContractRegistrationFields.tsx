/**
 * 合同登记表单分区（对齐简道云「合同登记表」字段顺序 + 控件类型 + 动态显隐）。
 * native → 表单顶层字段；reg → registration_json.*
 * 子表通过 slots 插在简道云 subform 对应位置。
 * 合同/项目评审流水号支持选数带出；合同号手填；图纸编号按规则系统生成。
 */
import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Form, Input, InputNumber, DatePicker, Select, Radio, Checkbox, AutoComplete, Button, Space, Tooltip } from 'antd'
import type { FormInstance } from 'antd'
import { ReloadOutlined } from '@ant-design/icons'
import {
  CONTRACT_REGISTRATION_SECTIONS,
  type RegAfterSlot,
  type RegFieldDef,
  type RegShowWhen,
} from '@/constants/contractRegistration'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { PolicyItem, useFieldPolicy } from '@/components/lowcode/FieldPolicy'
import { contractReviewApi, type ContractReview } from '@/api/contractReview'
import { contractApi } from '@/api/contract'
import { useUserSelect } from '@/hooks/useSelectOptions'
import DepartmentSelect from '@/components/DepartmentSelect'
import { formDateRule } from '@/utils/formDate'

const DATE_KEYS = new Set([
  'delivery_date', 'order_date', 'card_date', 'end_date', 'note_date', 'accept_date',
])
const NATIVE_KEYS = new Set([
  'contract_no', 'drawing_no', 'peer_contract_no', 'acquire_method',
  'delivery_date', 'change_type', 'amount_total', 'order_date', 'card_date', 'end_date',
  'assignee_id', 'assignee_name', 'department_id', 'department_name',
])

type Props = {
  form: FormInstance
  mode?: 'create' | 'edit'
  regOnly?: boolean
  slots?: Partial<Record<RegAfterSlot, ReactNode>>
  /** 新建：图纸编号旁「重新取号」 */
  onRefreshDrawingNo?: () => void
  refreshingDrawingNo?: boolean
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

/** 组织架构选人；同步写 companion name 字段 */
function OrgPersonField({
  form,
  nameKey = 'assignee_name',
  value,
  onChange,
  placeholder = '从组织架构选择',
}: {
  form: FormInstance
  nameKey?: string
  value?: string
  onChange?: (v: string | undefined) => void
  placeholder?: string
}) {
  const userSelect = useUserSelect()
  // 编辑回显：已有 id+name 时注入选项，否则 Select 只显示裸 uuid
  useEffect(() => {
    const name = form.getFieldValue(nameKey) as string | undefined
    if (value && name) userSelect.setInitialOption({ value, label: name })
    // 仅在挂载/id 变化时补选项
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])
  return (
    <Select
      allowClear
      showSearch
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
}: {
  form: FormInstance
  nameKey?: string
  value?: string
  onChange?: (v: string | undefined) => void
}) {
  return (
    <DepartmentSelect
      value={value}
      placeholder="从组织架构选择部门"
      onChange={(id, label) => {
        onChange?.(id)
        form.setFieldsValue({ [nameKey]: id ? (label || undefined) : undefined })
      }}
    />
  )
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
      ...(hit.department_id ? { department_id: hit.department_id } : {}),
      ...(hit.department_name ? { department_name: hit.department_name } : {}),
      ...(hit.owner_id ? { assignee_id: hit.owner_id } : {}),
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

/** 应用领域 / 应用物料：从低代码基础表异步取选项 */
function BaseFormLookupSelect({
  formCode,
  value,
  onChange,
  placeholder = '请选择',
}: {
  formCode: 'application_field' | 'application_material' | 'material_name'
  value?: string
  onChange?: (v: string | undefined) => void
  placeholder?: string
}) {
  const [options, setOptions] = useState<{ label: string; value: string }[]>([])
  const [loading, setLoading] = useState(false)
  const load = async (kw?: string) => {
    setLoading(true)
    try {
      const r = await contractApi.baseLookups({
        type: formCode,
        keyword: kw || undefined,
        limit: 200,
      })
      const items = r.data || []
      setOptions(items.map((it) => ({ value: it.name, label: it.label || it.name })))
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formCode])
  // 编辑回显：已有值但不在选项中时注入
  useEffect(() => {
    const v = (value || '').trim()
    if (!v) return
    setOptions((prev) => (prev.some((o) => o.value === v) ? prev : [{ value: v, label: v }, ...prev]))
  }, [value])
  return (
    <Select
      allowClear
      showSearch
      filterOption={false}
      placeholder={placeholder}
      value={value || undefined}
      loading={loading}
      options={options}
      onSearch={(kw) => void load(kw)}
      onDropdownVisibleChange={(open) => { if (open && options.length === 0) void load() }}
      onChange={(v) => onChange?.((v as string | undefined) || undefined)}
    />
  )
}

function FieldControl({
  field,
  form,
  value,
  onChange,
  onRefreshDrawingNo,
  refreshingDrawingNo,
  ...rest
}: {
  field: RegFieldDef
  form: FormInstance
  value?: unknown
  onChange?: (...args: any[]) => void
  onRefreshDrawingNo?: () => void
  refreshingDrawingNo?: boolean
  [k: string]: unknown
}) {
  const widget = field.widget || 'text'
  const opts = (field.options || []).map((o) => ({ value: o.value, label: o.label }))
  // Form.Item 注入的 value/onChange 必须透传到真实控件，否则界面能填但表单 store 仍为空
  const control = { value, onChange, ...rest } as Record<string, unknown>

  if (field.key === 'review_sn') {
    return (
      <ReviewSnPicker
        form={form}
        value={value as string | undefined}
        onChange={onChange as ((v: string) => void) | undefined}
      />
    )
  }

  if (field.key === 'drawing_no' && onRefreshDrawingNo) {
    return (
      <Space.Compact className="w-full">
        <Input
          {...control}
          allowClear
          placeholder={field.placeholder}
        />
        <Tooltip title="重新取号">
          <Button
            icon={<ReloadOutlined />}
            loading={!!refreshingDrawingNo}
            onClick={() => onRefreshDrawingNo()}
          />
        </Tooltip>
      </Space.Compact>
    )
  }

  if (field.lookupFormCode) {
    return (
      <BaseFormLookupSelect
        formCode={field.lookupFormCode}
        value={value as string | undefined}
        onChange={onChange as ((v: string | undefined) => void) | undefined}
        placeholder={field.placeholder || '请选择'}
      />
    )
  }

  if (widget === 'person' || field.key === 'assignee_id') {
    return (
      <OrgPersonField
        form={form}
        nameKey="assignee_name"
        value={value as string | undefined}
        onChange={onChange as ((v: string | undefined) => void) | undefined}
        placeholder="从组织架构选择业务人员"
      />
    )
  }
  if (widget === 'department' || field.key === 'department_id') {
    return (
      <OrgDepartmentField
        form={form}
        nameKey="department_name"
        value={value as string | undefined}
        onChange={onChange as ((v: string | undefined) => void) | undefined}
      />
    )
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
    const handleRadio = (e: { target: { value?: unknown } }) => {
      onChange?.(e)
      if (trigger) patchReg(field.key, e.target.value)
    }
    if (useBtn) {
      return (
        <Radio.Group
          {...control}
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
    return <Checkbox.Group {...control} options={opts} className="flex flex-wrap gap-x-3 gap-y-1" />
  }
  if (widget === 'select') {
    if (opts.length) {
      return (
        <Select
          {...control}
          allowClear
          showSearch
          optionFilterProp="label"
          options={opts}
          placeholder="请选择"
        />
      )
    }
    return <AutoComplete {...control} allowClear options={[]} placeholder="请输入或选择" filterOption />
  }
  if (widget === 'date' || DATE_KEYS.has(field.key)) {
    // 允许手输，但由 formDateRule 拦截 invalid dayjs，避免提交 "Invalid Date"
    return <DatePicker {...control} className="w-full" />
  }
  if (widget === 'money' || widget === 'number') {
    return (
      <InputNumber
        {...control}
        className="w-full"
        min={0}
        precision={widget === 'money' ? 2 : undefined}
      />
    )
  }
  if (widget === 'textarea') {
    return <Input.TextArea {...control} rows={2} disabled={field.readOnly} placeholder={field.placeholder} />
  }
  return (
    <Input
      {...control}
      allowClear={!field.readOnly}
      disabled={field.readOnly}
      placeholder={field.placeholder}
    />
  )
}

function FieldGrid({
  fields,
  mode: _mode,
  regOnly,
  form,
  onRefreshDrawingNo,
  refreshingDrawingNo,
}: {
  fields: RegFieldDef[]
  mode: 'create' | 'edit'
  regOnly: boolean
  form: FormInstance
  onRefreshDrawingNo?: () => void
  refreshingDrawingNo?: boolean
}) {
  const policy = useFieldPolicy()
  const catalogById = new Map(
    (policy.nativeFields || []).map((fd) => [fd.id, fd as {
      id: string
      json_storage?: string
      available_on_create?: boolean
    }]),
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
          if (regOnly && f.source === 'native') return false
          // 仅审批填写：创建/编辑填报页不展示（对齐 FormRenderer available_on_create）
          const cat = catalogById.get(f.key)
          const approverOnly = cat
            ? cat.available_on_create === false
            : f.availableOnCreate === false
          if (approverOnly) return false
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
              // 本地 required 与策略取并集：避免策略里被租户关掉后，业务仍强制必填却无星号
              const localRequired = f.required
                || (f.requiredWhen ? isVisible({ ...f, showWhen: f.requiredWhen }, values) : false)
              const policyRequired = policyOwns ? !!state?.required : false
              const needRequired = localRequired || policyRequired
              const isDate = f.widget === 'date' || DATE_KEYS.has(f.key)
              const rules: object[] = []
              if (needRequired) {
                rules.push({
                  required: true,
                  message: `请填写${f.label}`,
                  type: f.widget === 'checkbox' ? 'array' : undefined,
                  ...(f.widget === 'checkbox' ? { min: 1 } : {}),
                })
              }
              if (isDate) rules.push(formDateRule)
              const itemProps = {
                label: f.label,
                className: 'mb-3',
                style: spanFull ? { gridColumn: '1 / -1' } : undefined,
                rules: rules.length ? rules : undefined,
              }
              const cat = catalogById.get(f.key)
              const namePath = (f.source === 'reg' || cat?.json_storage)
                ? (['registration_json', f.key] as (string | number)[])
                : f.key
              if (f.source === 'native' || inCatalog) {
                return (
                  <PolicyItem key={f.key} name={namePath} {...itemProps}>
                    <FieldControl
                      field={f}
                      form={form}
                      onRefreshDrawingNo={onRefreshDrawingNo}
                      refreshingDrawingNo={refreshingDrawingNo}
                    />
                  </PolicyItem>
                )
              }
              return (
                <Form.Item
                  key={f.key}
                  name={['registration_json', f.key]}
                  {...itemProps}
                >
                  <FieldControl
                    field={f}
                    form={form}
                    onRefreshDrawingNo={onRefreshDrawingNo}
                    refreshingDrawingNo={refreshingDrawingNo}
                  />
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
  onRefreshDrawingNo,
  refreshingDrawingNo,
}: Props) {
  const refreshProps = mode === 'create'
    ? { onRefreshDrawingNo, refreshingDrawingNo }
    : {}
  return (
    <div className="space-y-5">
      {/* companion 显示名：选人/选部门时同步写入，提交落库但不单独展示 */}
      <Form.Item name="assignee_name" hidden><Input /></Form.Item>
      <Form.Item name="department_name" hidden><Input /></Form.Item>
      {CONTRACT_REGISTRATION_SECTIONS.map((sec) => {
        // 整区字段均为「仅审批填写」时，创建/编辑填报页不渲染该分区（含附件槽）
        if (sec.fields.length > 0 && sec.fields.every((f) => f.availableOnCreate === false)) {
          return null
        }
        return (
          <div key={sec.key}>
            <ContractSectionTitle title={sec.title} />
            <FieldGrid fields={sec.fields} mode={mode} regOnly={regOnly} form={form} {...refreshProps} />
            {sec.afterSlot && slots?.[sec.afterSlot] ? (
              <div className="my-4">{slots[sec.afterSlot]}</div>
            ) : null}
            {sec.fieldsAfterSlot?.length ? (
              <FieldGrid fields={sec.fieldsAfterSlot} mode={mode} regOnly={regOnly} form={form} {...refreshProps} />
            ) : null}
          </div>
        )
      })}
      <div className="text-[12px] text-slate-400">
        标 <span className="text-rose-500">*</span> 为必填。附件可直接在对应分区选择/上传。
      </div>
    </div>
  )
}

export { NATIVE_KEYS, DATE_KEYS }
