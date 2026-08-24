/** 审批节点可填业务字段表单（对齐简道云 optAuth）。 */
import { useEffect, useMemo, useState } from 'react'
import { DatePicker, Input, InputNumber, Radio, Space, Typography } from 'antd'
import dayjs from 'dayjs'
import type {
  FieldDefinition, FieldPermission, FormRule, WfCurrentTask, WfFieldPerm,
} from '@/types/lowcode'
import PersonField, {
  filterDeptIdsFromValues, shouldFilterByDeptFields, type PickableScope,
} from '@/components/lowcode/fields/PersonField'
import DeptField from '@/components/lowcode/fields/DeptField'
import FileField from '@/components/lowcode/fields/FileField'
import CustomerField from '@/components/lowcode/fields/CustomerField'
import ContractField, {
  fetchProdCardContractFill, PROD_CARD_FILL_CLEAR, warnPriorInvoicesAfterFill,
} from '@/components/lowcode/fields/ContractField'
import TechAgreementReviewField, {
  fetchProdCardTarFill, PROD_CARD_TAR_FILL_CLEAR, resolveTarFilterIds,
} from '@/components/lowcode/fields/TechAgreementReviewField'
import { useAuthStore } from '@/stores/useAuthStore'
import { contractPickDepartments } from '@/utils/contractPickDepartments'
import FormRenderer from '@/components/lowcode/FormRenderer'
import { computeFieldStates, validateApproverDetailRows } from '@/components/lowcode/RuleEngine'
import { dateFieldFormat, fieldShowsTime } from '@/components/lowcode/dateField'
import {
  applyProdCardOrderTypeMerged,
  applySimpleFormulas,
} from '@/utils/lowcodeSimpleFormulas'
import { prodCardInstallClearKeys } from '@/constants/prodCardInstallLinks'

const { Text } = Typography

const RISK_OPTS = [
  { value: '高', label: '高' },
  { value: '中', label: '中' },
  { value: '低', label: '低' },
]
const YES_NO_OPTS = [
  { value: '是', label: '是' },
  { value: '否', label: '否' },
]

function isEmpty(v: unknown): boolean {
  if (v == null) return true
  if (typeof v === 'string' && !v.trim()) return true
  if (Array.isArray(v) && v.length === 0) return true
  return false
}

function buildApproveFields(
  fieldMeta: WfCurrentTask['field_meta'] | undefined,
  fieldPerms: WfFieldPerm[] | undefined,
  formFields?: FieldDefinition[],
): FieldDefinition[] {
  const byId = new Map<string, FieldDefinition>()
  for (const f of formFields || []) {
    if (f?.id) byId.set(f.id, f)
  }
  for (const m of fieldMeta || []) {
    if (!m?.id) continue
    const base = byId.get(m.id)
    byId.set(m.id, {
      ...(base || { id: m.id, type: (m.type || 'text') as FieldDefinition['type'], label: m.label }),
      id: m.id,
      label: m.label || base?.label || m.id,
      type: (m.type || base?.type || 'text') as FieldDefinition['type'],
      options: m.options?.length ? m.options : base?.options,
      detail_table_columns: m.detail_table_columns || base?.detail_table_columns,
      props: { ...(base?.props || {}), ...(m.props || {}) },
      required: false,
    })
  }
  // 确保节点可填字段一定在 states 里
  for (const p of fieldPerms || []) {
    if (!byId.has(p.field)) {
      byId.set(p.field, {
        id: p.field,
        type: 'text',
        label: p.field,
        required: false,
      })
    }
  }
  return [...byId.values()]
}

export function missingRequiredFields(
  fieldPerms: WfFieldPerm[] | undefined,
  values: Record<string, unknown>,
  opts?: {
    rules?: FormRule[]
    formFields?: FieldDefinition[]
    formData?: Record<string, unknown>
    fieldMeta?: WfCurrentTask['field_meta']
  },
): string[] {
  const perms = fieldPerms || []
  if (!perms.length) return []
  const fields = buildApproveFields(opts?.fieldMeta, perms, opts?.formFields)
  const merged = { ...(opts?.formData || {}), ...values }
  const rules = opts?.rules || []

  const detailRequiredMissing = (fieldId: string): boolean => {
    // 仅节点把明细标为 required 时强制审批列（editable 可改但不卡仓库判定等）
    return !!validateApproverDetailRows(fields, fieldId, merged[fieldId])
  }

  if (!rules.length) {
    return perms
      .filter((p) => {
        if (p.access !== 'required') return false
        if (isEmpty(merged[p.field])) return true
        return detailRequiredMissing(p.field)
      })
      .map((p) => p.field)
  }
  const permissions: FieldPermission[] = perms.map((p) => ({
    fieldId: p.field,
    access: p.access === 'required' ? 'required'
      : p.access === 'readonly' ? 'readonly' : 'editable',
  }))
  const states = computeFieldStates(fields, merged, rules, permissions)
  return perms
    .filter((p) => {
      const st = states[p.field]
      // 被显隐规则藏掉的字段不校验（如设计单分派=总部单时「转新乡」）
      if (st && !st.visible) return false
      const req = st ? st.required : p.access === 'required'
      if (!req) return false
      if (isEmpty(merged[p.field])) return true
      return detailRequiredMissing(p.field)
    })
    .map((p) => p.field)
}

function FieldLabel({ label, required, error }: { label: string; required?: boolean; error?: boolean }) {
  return (
    <Text style={{ fontSize: 12, color: error ? '#cf1322' : undefined }}>
      {label}
      {required ? <span style={{ color: '#cf1322', marginLeft: 2 }}>*</span> : null}
    </Text>
  )
}

export default function ApproveFieldForm({
  currentTask,
  values,
  onChange,
  showTitle = true,
  highlightMissing = false,
  rules = [],
  formData = {},
  formFields = [],
}: {
  currentTask: WfCurrentTask
  values: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
  /** 外层已有「本节点填写」标题时传 false，避免重复 */
  showTitle?: boolean
  /** 点击通过后高亮未填必填项 */
  highlightMissing?: boolean
  /** 表单显隐/必填规则（如设计单分派 → 转新乡） */
  rules?: FormRule[]
  /** 整单已有字段值（含 scheme_type 等，供规则求值） */
  formData?: Record<string, unknown>
  formFields?: FieldDefinition[]
}) {
  const currentUser = useAuthStore((s) => s.user)
  const metaById = Object.fromEntries((currentTask.field_meta || []).map((m) => [m.id, m]))
  const perms = currentTask.field_perms || []
  const [localHighlight, setLocalHighlight] = useState(highlightMissing)
  useEffect(() => { setLocalHighlight(highlightMissing) }, [highlightMissing])

  const mergedValues = useMemo(
    () => ({ ...formData, ...values }),
    [formData, values],
  )

  const fieldsForRules = useMemo(
    () => buildApproveFields(currentTask.field_meta, perms, formFields),
    [currentTask.field_meta, perms, formFields],
  )

  const fieldStates = useMemo(() => {
    if (!rules.length) return null
    const permissions: FieldPermission[] = perms.map((p) => ({
      fieldId: p.field,
      access: p.access === 'required' ? 'required'
        : p.access === 'readonly' ? 'readonly' : 'editable',
    }))
    return computeFieldStates(fieldsForRules, mergedValues, rules, permissions)
  }, [rules, perms, fieldsForRules, mergedValues])

  // 打开节点时若已有下单类型，立刻回填「下单类型（合并含补充）」
  useEffect(() => {
    if (!perms.some((p) => p.field === 'field' || p.field === 'order_type')) return
    const base = { ...formData, ...values }
    let out = applySimpleFormulas(fieldsForRules, base)
    out = applyProdCardOrderTypeMerged(out)
    const nextField = out.field
    if (nextField == null || nextField === '') return
    if (values.field === nextField) return
    onChange({ ...values, field: nextField })
  }, [fieldsForRules, formData, onChange, perms, values])

  if (!perms.length) return null

  const emitValues = (next: Record<string, unknown>) => {
    // 审批可写字段 + 表单字段定义（含公式）一起重算，如生产卡「下单类型（合并含补充）」
    let out = applySimpleFormulas(fieldsForRules, { ...formData, ...next })
    // 审批节点 values 只存本节点可写字段；合并后写回 next 里出现过的键 + 公式产物 field
    const patch: Record<string, unknown> = { ...next }
    for (const f of fieldsForRules) {
      if (f.type === 'formula' && f.id in out) patch[f.id] = out[f.id]
    }
    out = applyProdCardOrderTypeMerged({ ...formData, ...patch })
    if ('field' in out) patch.field = out.field
    onChange(patch)
  }

  const setField = (id: string, v: unknown) => {
    emitValues({ ...values, [id]: v })
  }
  const patchFields = (patch: Record<string, unknown>) => {
    emitValues({ ...values, ...patch })
  }

  const missing = new Set(
    localHighlight
      ? missingRequiredFields(perms, values, {
        rules, formFields, formData, fieldMeta: currentTask.field_meta,
      })
      : [],
  )

  return (
    <div style={{ marginBottom: showTitle ? 12 : 0 }}>
      {showTitle && (
        <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>
          本节点填写（{currentTask.node_name || '审批'}）
        </Text>
      )}
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        {perms.map((p) => {
          const st = fieldStates?.[p.field]
          // 节点可填字段仍走显隐（设计单分派→转新乡/设计指派）；无规则时默认可见
          if (fieldStates && st && !st.visible) return null

          const formFd = formFields.find((f) => f.id === p.field)
          const meta = metaById[p.field] || { id: p.field, label: p.field, type: 'text' as const }
          // field_meta 已按已发布模板覆盖 type；实例 form_fields 快照可能仍是旧类型（如科室单选）
          // 科室字段业务固定多选，避免在途单快照/缓存仍按 department 渲染成单选
          let t = meta.type || formFd?.type || 'text'
          if (p.field === 'offices' || p.field === 'offices_multi') {
            t = 'department_multi'
          }
          // 公式字段只读展示（如生产卡「下单类型（合并含补充）」）
          const isReadonly = p.access === 'readonly' || st?.readonly === true || t === 'formula'
          const required = !isReadonly && (st ? st.required : p.access === 'required')
          const err = missing.has(p.field)
          const val = values[p.field]
          const status = err ? 'error' as const : undefined
          const label = meta.label || formFd?.label || p.field
          const options = (meta.options?.length ? meta.options : formFd?.options) || []
          const detailCols = meta.detail_table_columns || formFd?.detail_table_columns
          const fieldProps = {
            ...((formFd?.props as Record<string, unknown> | undefined) || {}),
            ...((meta.props as Record<string, unknown> | undefined) || {}),
          }

          if (isReadonly) {
            const fd: FieldDefinition = {
              id: p.field,
              label,
              type: t as FieldDefinition['type'],
              options,
              props: fieldProps,
            }
            const displayVal = values[p.field] ?? formData[p.field]
            return (
              <div key={p.field}>
                <FieldLabel label={label} required={false} />
                <div style={{ marginTop: 4 }}>
                  <FormRenderer
                    fields={[fd]}
                    mode="readonly"
                    value={{ [p.field]: displayVal }}
                    rules={[]}
                    applyFieldPerms={false}
                  />
                </div>
              </div>
            )
          }

          if (t === 'detail_table') {
            const fd: FieldDefinition = {
              id: p.field,
              label,
              type: 'detail_table',
              required,
              detail_table_columns: detailCols,
              available_on_create: true,
            }
            const parentFillKeys = prodCardInstallClearKeys()
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FormRenderer
                  fields={[fd]}
                  mode="edit"
                  value={{ ...formData, ...values, [p.field]: val }}
                  onChange={(next) => {
                    const patch: Record<string, unknown> = { ...values }
                    if (p.field in next) patch[p.field] = next[p.field]
                    for (const k of parentFillKeys) {
                      if (k in next) patch[k] = next[k]
                    }
                    emitValues(patch)
                  }}
                  rules={[]}
                  detailCreateFill={false}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请填写{label}</Text>}
              </div>
            )
          }

          if (t === 'person' || t === 'user' || t === 'person_multi') {
            const scope = (fieldProps as { pickable_scope?: PickableScope })?.pickable_scope
            const useDeptFilter = shouldFilterByDeptFields(scope, p.field)
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <div style={{ marginTop: 4 }}>
                  <PersonField
                    value={val}
                    onChange={(v) => setField(p.field, v)}
                    multi={t === 'person_multi'}
                    placeholder={`请选择${label}`}
                    pickableScope={scope}
                    deptIds={useDeptFilter ? filterDeptIdsFromValues(values, scope?.filter_by_fields) : undefined}
                  />
                </div>
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }

          if (t === 'department' || t === 'department_multi') {
            const scope = (fieldProps as { pickable_scope?: PickableScope })?.pickable_scope
            const asMulti = t === 'department_multi' || Array.isArray(val)
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <div style={{ marginTop: 4 }}>
                  <DeptField
                    value={val}
                    onChange={(v) => setField(p.field, v)}
                    multi={asMulti}
                    placeholder={`请选择${label}`}
                    scopeCode={scope?.scope_code}
                    rangeDeptIds={scope?.scope_code ? undefined : scope?.dept_ids}
                    includeChildren={scope?.include_children}
                  />
                </div>
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }

          if (t === 'file' || t === 'image') {
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <div style={{ marginTop: 4 }}>
                  <FileField
                    value={val}
                    onChange={(v) => setField(p.field, v)}
                    image={t === 'image'}
                  />
                </div>
                {err && <Text type="danger" style={{ fontSize: 12 }}>请上传{label}</Text>}
              </div>
            )
          }

          if (t === 'customer') {
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <div style={{ marginTop: 4 }}>
                  <CustomerField
                    value={val}
                    onChange={(v) => setField(p.field, v)}
                    placeholder={`请选择${label}`}
                  />
                </div>
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }

          if (t === 'contract') {
            const fillMode = (fieldProps as { contract_fill?: 'drawing_no_query' | 'contract_no_select' | 'invoice_application' | 'shipment_notice' }).contract_fill
            const deptField = (fieldProps as { filter_by_department_field?: string }).filter_by_department_field
            let formDepartmentId: string | undefined
            if (deptField) {
              const rawDept = mergedValues[deptField]
              if (Array.isArray(rawDept) && rawDept[0] != null && rawDept[0] !== '') {
                formDepartmentId = String(rawDept[0])
              } else if (rawDept != null && rawDept !== '') {
                formDepartmentId = String(rawDept)
              }
            }
            const pickDepts = contractPickDepartments(currentUser, formDepartmentId)
            const invoicePick = fillMode === 'invoice_application'
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <div style={{ marginTop: 4 }}>
                  <ContractField
                    value={val}
                    departmentId={invoicePick ? undefined : pickDepts.departmentId}
                    departmentIds={invoicePick ? undefined : pickDepts.departmentIds}
                    purpose={invoicePick ? 'invoice_application' : undefined}
                    placeholder={`请选择${label}`}
                    onChange={(v) => {
                      if (!fillMode) {
                        setField(p.field, v)
                        return
                      }
                      if (!v) {
                        const cleared: Record<string, unknown> = { [p.field]: undefined }
                        for (const k of PROD_CARD_FILL_CLEAR[fillMode] || []) cleared[k] = undefined
                        patchFields(cleared)
                        return
                      }
                      void fetchProdCardContractFill(v, fillMode).then((pack) => {
                        patchFields({ [p.field]: v, ...pack.fill })
                        warnPriorInvoicesAfterFill(fillMode, pack)
                      }).catch(() => setField(p.field, v))
                    }}
                  />
                </div>
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }

          if (t === 'tech_agreement_review') {
            const tarProps = fieldProps as {
              filter_by_submitter_field?: string
              filter_by_department_field?: string
              tar_fill?: 'prod_card_sn'
            }
            const { applicantId, departmentId } = resolveTarFilterIds(
              mergedValues,
              tarProps.filter_by_submitter_field,
              tarProps.filter_by_department_field,
            )
            const fillMode = tarProps.tar_fill
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <div style={{ marginTop: 4 }}>
                  <TechAgreementReviewField
                    value={val}
                    applicantId={applicantId}
                    departmentId={departmentId}
                    placeholder={`请选择${label}`}
                    onChange={(v) => {
                      if (!fillMode) {
                        setField(p.field, v)
                        return
                      }
                      if (!v) {
                        const cleared: Record<string, unknown> = { [p.field]: undefined }
                        for (const k of PROD_CARD_TAR_FILL_CLEAR) cleared[k] = undefined
                        patchFields(cleared)
                        return
                      }
                      void fetchProdCardTarFill(v).then((fill) => {
                        patchFields({ [p.field]: v, ...fill })
                      }).catch(() => setField(p.field, v))
                    }}
                  />
                </div>
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }

          if (t === 'risk') {
            return (
              <div key={p.field}>
                <FieldLabel label={label} required={required} error={err} />
                <Radio.Group
                  value={val as string | undefined}
                  options={RISK_OPTS}
                  onChange={(e) => setField(p.field, e.target.value)}
                  style={{ display: 'block', marginTop: 4 }}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }
          if (t === 'yes_no') {
            return (
              <div key={p.field}>
                <FieldLabel label={label} required={required} error={err} />
                <Radio.Group
                  value={val as string | undefined}
                  options={YES_NO_OPTS}
                  onChange={(e) => setField(p.field, e.target.value)}
                  style={{ display: 'block', marginTop: 4 }}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }
          if ((t === 'radio' || t === 'select') && options.length > 0) {
            return (
              <div key={p.field}>
                <FieldLabel label={label} required={required} error={err} />
                <Radio.Group
                  value={val as string | undefined}
                  options={options.map((o) => ({ value: o.value, label: o.label }))}
                  onChange={(e) => setField(p.field, e.target.value)}
                  style={{ display: 'block', marginTop: 4 }}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }
          if (t === 'date' || t === 'datetime') {
            const parsed = val ? dayjs(val as string) : null
            const metaField = { type: t, props: fieldProps } as FieldDefinition
            const withTime = fieldShowsTime(metaField)
            const fmt = dateFieldFormat(metaField)
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <DatePicker
                  style={{ width: '100%', marginTop: 4 }}
                  status={status}
                  showTime={withTime}
                  value={parsed?.isValid() ? parsed : null}
                  placeholder={required ? `请选择${label}` : undefined}
                  onChange={(d) => setField(p.field, d ? d.format(fmt) : null)}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请选择{label}</Text>}
              </div>
            )
          }
          if (t === 'number' || t === 'amount') {
            const min = typeof fieldProps.min === 'number' ? fieldProps.min
              : (fieldProps.min != null ? Number(fieldProps.min) : undefined)
            const max = typeof fieldProps.max === 'number' ? fieldProps.max
              : (fieldProps.max != null ? Number(fieldProps.max) : undefined)
            const precision = typeof fieldProps.precision === 'number' ? fieldProps.precision : undefined
            const numVal = val === '' || val == null ? null : Number(val)
            return (
              <div key={p.field} className={err ? 'approve-field-error' : undefined}>
                <FieldLabel label={label} required={required} error={err} />
                <InputNumber
                  style={{ width: '100%', marginTop: 4 }}
                  status={status}
                  min={Number.isFinite(min as number) ? (min as number) : undefined}
                  max={Number.isFinite(max as number) ? (max as number) : undefined}
                  precision={precision}
                  value={Number.isFinite(numVal as number) ? (numVal as number) : null}
                  placeholder={required ? `请填写${label}` : undefined}
                  onChange={(v) => setField(p.field, v)}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请填写{label}</Text>}
              </div>
            )
          }
          if (t === 'textarea') {
            return (
              <div key={p.field}>
                <FieldLabel label={label} required={required} error={err} />
                <Input.TextArea
                  rows={2}
                  status={status}
                  value={(val as string) ?? ''}
                  onChange={(e) => setField(p.field, e.target.value)}
                  style={{ marginTop: 4 }}
                  placeholder={required ? `请填写${label}` : undefined}
                />
                {err && <Text type="danger" style={{ fontSize: 12 }}>请填写{label}</Text>}
              </div>
            )
          }
          return (
            <div key={p.field}>
              <FieldLabel label={label} required={required} error={err} />
              <Input
                size="small"
                status={status}
                value={(val as string) ?? ''}
                onChange={(e) => setField(p.field, e.target.value)}
                style={{ marginTop: 4 }}
                placeholder={required ? `请填写${label}` : undefined}
              />
              {err && <Text type="danger" style={{ fontSize: 12 }}>请填写{label}</Text>}
            </div>
          )
        })}
      </Space>
      <style>{`
        .approve-field-error .ant-select-selector,
        .approve-field-error .ant-select-selector:hover {
          border-color: #ff4d4f !important;
        }
      `}</style>
    </div>
  )
}
