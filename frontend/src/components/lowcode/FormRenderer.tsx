// 动态表单渲染器 —— 按 FieldDefinition schema 渲染填报/只读表单。
// 移植/重写自 spt-lowcode FormRenderer,聚焦核心自足字段类型;人员/部门/附件等高级类型
// 暂以占位呈现(后续切片接入)。规则引擎(显隐/只读/必填)复用 RuleEngine。
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  Row, Col, Input, InputNumber, DatePicker, Select, Radio, Checkbox, Switch,
  Button, Typography, Tag, Empty, Space, Tooltip, message,
} from 'antd'
import { PlusOutlined, DeleteOutlined, ReloadOutlined, ThunderboltOutlined } from '@ant-design/icons'
import DetailQuickFillModal from '@/components/DetailQuickFillModal'
import { PROD_CARD_QUICK_FILL_FIELD_IDS, prodCardDetailShowsRowIndex, pruneProdCardDetailColumns } from '@/constants/prodCardLegacyFields'
import { detailColumnsToQuickFillSpecs } from '@/utils/detailQuickFill'
import { applyDetailRowDefaults, buildDetailRowDefaults } from '@/utils/lowcodeFormDefaults'
import dayjs from 'dayjs'
import type { FieldDefinition, FormRule, FieldState, FieldPermission } from '@/types/lowcode'
import { computeFieldStates, isDetailColVisibleInRow } from './RuleEngine'
import { dateFieldDisplayFormat, dateFieldFormat, fieldShowsTime } from './dateField'
import { MASK_VALUE } from '@/utils/mask'
import { useAuthStore } from '@/stores/useAuthStore'
import PersonField, {
  filterDeptIdsFromValues, shouldFilterByDeptFields, type PickableScope,
} from './fields/PersonField'
import DeptField from './fields/DeptField'
import ProjectField, {
  fetchInstallNoticeProjectFill, INSTALL_NOTICE_PROJECT_FILL_CLEAR,
} from './fields/ProjectField'
import ContractField, {
  fetchProdCardContractFill, PROD_CARD_FILL_CLEAR, warnPriorInvoicesAfterFill,
} from './fields/ContractField'
import { contractPickDepartments } from '@/utils/contractPickDepartments'
import TechAgreementReviewField, {
  fetchProdCardTarFill, PROD_CARD_TAR_FILL_CLEAR, resolveTarFilterIds,
} from './fields/TechAgreementReviewField'
import CustomerField from './fields/CustomerField'
import FileField from './fields/FileField'
import AddressField from './fields/AddressField'
import CascadeField, { type CascadeOption } from './fields/CascadeField'
import RichTextField from './fields/RichTextField'
import SignatureField from './fields/SignatureField'
import BaseFormLookupField, { parseFormOptionsSource } from './fields/BaseFormLookupField'
import FormInstanceLookupField from './fields/FormInstanceLookupField'
import { linkFillClearKeys } from '@/constants/prodCardInstallLinks'
import ContractSectionTitle from '@/components/ContractSectionTitle'
import { applyProdCardOrderTypeMerged, applySimpleFormulas, recomputeDetailRowOnColChange } from '@/utils/lowcodeSimpleFormulas'
import { PRICING_CHECKLIST_LINKS, pricingChecklistAllClearKeys } from '@/constants/pricingChecklistLinks'
import { fetchCustomerFormFill, needsCustomerFormFill, clearCustomerFormFillPatch, pickShipAddressFill } from '@/utils/customerFormFill'
import FillHeightTable from '@/components/list/FillHeightTable'
import type { ColumnType } from 'antd/es/table'

const { TextArea } = Input
const { Text } = Typography

// 已完整支持的字段类型;其余类型以占位呈现。
const SUPPORTED = new Set([
  'text', 'textarea', 'number', 'amount', 'date', 'datetime',
  'select', 'multi_select', 'radio', 'checkbox', 'switch',
  'formula', 'auto_number', 'detail_table',
  'person', 'person_multi', 'department', 'department_multi', 'file', 'image',
  'address', 'cascade', 'rich_text', 'signature', 'project', 'contract', 'customer',
  'tech_agreement_review', 'select_data',
])

// 这些类型自行渲染只读态(名称/URL 需异步解析或富媒体展示),不走通用 ReadonlyValue。
// auto_number / formula 必须自渲：否则 form_editable=false 时会掉进 ReadonlyValue，
// 流水号预览（serialPreview）永远显示成「—」。
const SELF_RENDER_READONLY = new Set([
  'detail_table', 'person', 'person_multi', 'department', 'department_multi', 'file', 'image',
  'address', 'cascade', 'rich_text', 'signature', 'project', 'contract', 'customer',
  'tech_agreement_review', 'auto_number', 'formula', 'select_data',
])

const GROUP_TYPES = new Set(['tab_group', 'collapse_section'])

/** 发起填报：审批阶段字段不展示、不必填 */
function isCreateHiddenField(field: FieldDefinition): boolean {
  return field.available_on_create === false || field.fill_stage === 'approver'
}

interface Props {
  fields: FieldDefinition[]
  rules?: FormRule[]
  mode?: 'edit' | 'readonly'
  value: Record<string, unknown>
  onChange?: (value: Record<string, unknown>) => void
  // 设计器预览传 false，让管理员始终看到全部字段(设计态不受字段级权限约束)。
  applyFieldPerms?: boolean
  // 仅参与规则求值、不参与渲染与 onChange 的外部字段值（业务表单里的原生字段值）。
  // 使得「当国别=国外时显示某扩展字段」这类跨原生/扩展的条件能正确判定。
  ruleContext?: Record<string, unknown>
  /** 填报页流水号预览（未落库）；有已存值时仍优先展示 value */
  serialPreviews?: Record<string, string>
  /** 可手改流水号：重新取号 */
  onRefreshSerial?: (fieldId: string) => void
  refreshingSerialId?: string | null
  /** 明细子表布局：手机端用 cards */
  detailLayout?: 'table' | 'cards'
  /** 发起填报：隐藏 available_on_create=false 的明细列；审批填表传 false */
  detailCreateFill?: boolean
  /**
   * 流程通过后整单编辑：展示并可改审批才填字段（设计单分派/科室/下单日期等）。
   * 默认 false，避免创建/草稿编辑页露出审批字段。
   */
  includeApproverFields?: boolean
  /** 已办节点处理人补改：流程继续后仍可编辑本节点曾可填字段 */
  retroactiveFieldPerms?: { field: string; access: string; node_name?: string }[]
  /** 明细「选择数据」等联动回填父级字段时的旁路回调（审批抽屉与 value 结构解耦时使用） */
  onPatch?: (patch: Record<string, unknown>) => void
  /**
   * default：按字段 span 单列/设计器布局；
   * adaptive：宽屏/全屏下短字段自动 2～3 列，明细/富文本仍整行。
   */
  gridLayout?: 'default' | 'adaptive'
}

const ADAPTIVE_FULL_ROW = new Set(['detail_table'])
const ADAPTIVE_HALF_ROW = new Set([
  'file', 'image', 'rich_text', 'textarea', 'address', 'cascade', 'signature', 'project', 'contract', 'customer',
])

function colPropsForField(
  field: FieldDefinition,
  span: number,
  gridLayout: 'default' | 'adaptive',
): { span?: number; xs?: number; sm?: number; md?: number; lg?: number; xl?: number } {
  if (gridLayout !== 'adaptive') {
    return { span }
  }
  if (ADAPTIVE_FULL_ROW.has(field.type)) {
    return { xs: 24, span: 24 }
  }
  if (span < 24) {
    return { xs: 24, lg: span }
  }
  if (ADAPTIVE_HALF_ROW.has(field.type)) {
    return { xs: 24, lg: 12, xl: 12 }
  }
  return { xs: 24, sm: 12, xl: 8 }
}

export function deriveRolePerms(fields: FieldDefinition[], userRoles: string[]): FieldPermission[] {
  const roles = new Set(userRoles || [])
  const out: FieldPermission[] = []
  for (const f of fields) {
    const vr = f.visible_roles
    if (vr && vr.length && !vr.some((r) => roles.has(r))) {
      out.push({ fieldId: f.id, access: 'hidden' })
      continue
    }
    const ur = f.unmask_roles
    if (ur && ur.length && !ur.some((r) => roles.has(r))) {
      // 脱敏即隐含只读：看不到明文的人不该覆盖真实值
      out.push({ fieldId: f.id, access: 'masked' })
      continue
    }
    const er = f.edit_roles
    if (er && er.length && !er.some((r) => roles.has(r))) {
      out.push({ fieldId: f.id, access: 'readonly' })
    }
  }
  return out
}

/** 后端/简道云同步可能把 form_editable 落成字符串 "false"。 */
export function isFieldFormReadonly(field: FieldDefinition): boolean {
  if (field.readonly) return true
  const fe = field.form_editable as boolean | string | number | undefined
  return fe === false || fe === 'false' || fe === 0
}

export default function FormRenderer({ fields, rules = [], mode = 'edit', value, onChange, applyFieldPerms = true, ruleContext, serialPreviews, onRefreshSerial, refreshingSerialId, detailLayout = 'table', detailCreateFill = true, includeApproverFields = false, retroactiveFieldPerms = [], onPatch: onPatchExternal, gridLayout = 'default' }: Props) {
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const valueRef = useRef(value)
  valueRef.current = value
  const rolePerms = useMemo(
    () => (applyFieldPerms ? deriveRolePerms(fields, userRoles) : []),
    [applyFieldPerms, fields, userRoles],
  )
  const retroFieldIds = useMemo(
    () => new Set((retroactiveFieldPerms || []).map((p) => p.field).filter(Boolean)),
    [retroactiveFieldPerms],
  )
  const mergedPerms = useMemo(() => {
    if (!retroactiveFieldPerms?.length) return rolePerms
    const byId = new Map(rolePerms.map((p) => [p.fieldId, p]))
    for (const p of retroactiveFieldPerms) {
      if (!p.field) continue
      const prev = byId.get(p.field)
      if (prev?.access === 'hidden' || prev?.access === 'masked') continue
      byId.set(p.field, {
        fieldId: p.field,
        access: p.access === 'required' ? 'required' : 'editable',
      })
    }
    return [...byId.values()]
  }, [rolePerms, retroactiveFieldPerms])
  // 本表单字段值优先于外部上下文（同名时以用户在本表单里填的为准）
  const ruleValues = useMemo(
    () => (ruleContext ? { ...ruleContext, ...value } : value),
    [ruleContext, value],
  )
  const states = useMemo(
    () => computeFieldStates(fields, ruleValues, rules, mergedPerms),
    [fields, ruleValues, rules, mergedPerms],
  )

  const applyFormulas = (values: Record<string, unknown>, changedField?: string) => {
    let out = applySimpleFormulas(fields, values)
    out = applyProdCardOrderTypeMerged(out, { skipField: changedField === 'field' })
    return out
  }

  const setField = (id: string, v: unknown) => {
    onChange?.(applyFormulas({ ...valueRef.current, [id]: v }, id))
  }
  const patchFields = (patch: Record<string, unknown>) => {
    onChange?.(applyFormulas({ ...valueRef.current, ...patch }))
    onPatchExternal?.(patch)
  }

  const topFields = fields.filter((f) => !GROUP_TYPES.has(f.type))
  if (!topFields.length) return <Empty description="该表单暂无字段" />

  const hideApproverOnEdit = mode === 'edit' && !includeApproverFields && retroFieldIds.size === 0

  const isShown = (field: FieldDefinition): boolean => {
    if (field.type === 'section' || field.type === 'separator') return false
    if (hideApproverOnEdit && isCreateHiddenField(field)) return false
    if (mode === 'edit' && isCreateHiddenField(field) && retroFieldIds.has(field.id)) return true
    const st = states[field.id]
    if (mode === 'edit' && retroFieldIds.has(field.id)) {
      if (st?.masked) return false
      return true
    }
    if (st && !st.visible) return false
    return true
  }

  return (
    <Row gutter={[16, 8]} className={gridLayout === 'adaptive' ? 'lc-form-grid-adaptive' : undefined}>
      {topFields.map((field, idx) => {
        // 布局误挂同一 field.id 多次时，用 index 保证 React key 唯一
        const rowKey = `${field.id}__${idx}`
        if (field.type === 'section' || field.type === 'separator') {
          // 分区下若创建页全部是审批才填字段，则整段标题一并隐藏
          let hasVisibleChild = false
          for (let j = idx + 1; j < topFields.length; j++) {
            const next = topFields[j]
            if (next.type === 'section' || next.type === 'separator') break
            if (isShown(next)) { hasVisibleChild = true; break }
          }
          if (!hasVisibleChild) return null
          return (
            <Col span={24} key={rowKey}>
              <ContractSectionTitle title={field.label} className="mt-2 mb-1" />
            </Col>
          )
        }
        if (!isShown(field)) return null
        const st = states[field.id]
        // detail_table 强制整行；附件/图片按 layout span 与简道云 lineWidth 同排
        const span = field.type === 'detail_table' ? 24 : (field.span || 24)
        const narrowCol = field.type === 'file' || field.type === 'image' || field.type === 'radio'
        const colLayout = colPropsForField(field, span, gridLayout)
        return (
          <Col
            {...colLayout}
            key={rowKey}
            className={narrowCol ? 'min-w-0 max-w-full overflow-hidden' : undefined}
          >
            <FieldItem
              field={field}
              state={st}
              mode={mode}
              value={value[field.id]}
              allValues={ruleValues}
              onChange={(v) => setField(field.id, v)}
              onPatch={patchFields}
              serialPreview={serialPreviews?.[field.id]}
              onRefreshSerial={onRefreshSerial}
              refreshingSerial={refreshingSerialId === field.id}
              rules={rules}
              fields={fields}
              detailLayout={detailLayout}
              detailCreateFill={includeApproverFields || retroFieldIds.size > 0 ? false : detailCreateFill}
              fieldSpan={span}
              retroEditable={retroFieldIds.has(field.id)}
            />
          </Col>
        )
      })}
    </Row>
  )
}

function FieldItem({
  field, state, mode, value, allValues, onChange, onPatch, serialPreview, onRefreshSerial, refreshingSerial, rules = [], fields = [], detailLayout = 'table', detailCreateFill = true, fieldSpan, retroEditable = false,
}: {
  field: FieldDefinition
  state?: FieldState
  mode: 'edit' | 'readonly'
  value: unknown
  allValues: Record<string, unknown>
  onChange: (v: unknown) => void
  onPatch?: (patch: Record<string, unknown>) => void
  serialPreview?: string
  onRefreshSerial?: (fieldId: string) => void
  refreshingSerial?: boolean
  rules?: FormRule[]
  fields?: FieldDefinition[]
  detailLayout?: 'table' | 'cards'
  detailCreateFill?: boolean
  fieldSpan?: number
  /** 已办节点补改：忽略 form_editable / 字段级 readonly 标记 */
  retroEditable?: boolean
}) {
  const readonly = mode === 'readonly' || (
    !retroEditable && (
      !!state?.readonly
      || !!(field.props as { read_only?: boolean } | undefined)?.read_only
      || isFieldFormReadonly(field)
    )
  )
  const required = state?.required
  // 脱敏字段一律不渲染真实控件：后端已把值换成 "***"，但若值恰好没被裁到（如设计器预览），
  // 这里也不能把明文渲染出去。
  const masked = state?.masked || field.masked
  return (
    <div className="mb-4 min-w-0 max-w-full overflow-hidden" data-lc-field={field.id}>
      {(field.label || required) ? (
      <div style={{ marginBottom: 4, fontSize: 13, color: 'rgba(0,0,0,0.75)' }}>
        {required && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
        {field.label}
        {field.description && (
          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
            {field.description}
          </Text>
        )}
      </div>
      ) : null}
      {masked
        ? <Text type="secondary" title="您所在角色无权查看该字段的明文">{MASK_VALUE}</Text>
        : (
          <FieldWidget
            field={field}
            readonly={!!readonly}
            value={value}
            allValues={allValues}
            onChange={onChange}
            onPatch={onPatch}
            serialPreview={serialPreview}
            onRefreshSerial={onRefreshSerial}
            refreshingSerial={refreshingSerial}
            rules={rules}
            fields={fields}
            detailLayout={detailLayout}
            detailCreateFill={detailCreateFill}
            fieldSpan={fieldSpan}
          />
        )}
    </div>
  )
}

function FieldWidget({
  field, readonly, value, allValues, onChange, onPatch, serialPreview, onRefreshSerial, refreshingSerial, rules = [], fields = [], detailLayout = 'table', detailCreateFill = true, fieldSpan, inlineCell,
}: {
  field: FieldDefinition
  readonly: boolean
  value: unknown
  allValues: Record<string, unknown>
  onChange: (v: unknown) => void
  onPatch?: (patch: Record<string, unknown>) => void
  serialPreview?: string
  onRefreshSerial?: (fieldId: string) => void
  refreshingSerial?: boolean
  rules?: FormRule[]
  fields?: FieldDefinition[]
  detailLayout?: 'table' | 'cards'
  detailCreateFill?: boolean
  fieldSpan?: number
  /** 明细子表单元格内的 file/image：简道云 Popover 模式 */
  inlineCell?: boolean
}) {
  const currentUser = useAuthStore((s) => s.user)
  const opts = field.options || []
  const ph = field.placeholder
  const downloadDenied = !!field.download_denied

  if (!SUPPORTED.has(field.type)) {
    // 高级字段类型占位(后续切片接入): 只读展示已有值
    return (
      <div>
        {readonly ? <ReadonlyValue field={field} value={value} /> : (
          <Tag color="default">该字段类型「{field.type}」即将支持</Tag>
        )}
      </div>
    )
  }

  // 本库基础资料选项（如物料名称）：options_source = form:material_name:name
  const lookupCode = parseFormOptionsSource(field.options_source)
  if (lookupCode && (field.type === 'multi_select' || field.type === 'checkbox' || field.type === 'select')) {
    return (
      <BaseFormLookupField
        formCode={lookupCode}
        value={value}
        onChange={onChange}
        multiple={field.type === 'multi_select' || field.type === 'checkbox'}
        readonly={readonly}
        placeholder={ph || '请选择'}
      />
    )
  }

  if (readonly && !SELF_RENDER_READONLY.has(field.type)) {
    return <ReadonlyValue field={field} value={value} />
  }

  switch (field.type) {
    case 'person':
    case 'person_multi': {
      const scope = (field.props as { pickable_scope?: PickableScope } | undefined)?.pickable_scope
      const useDeptFilter = !readonly && shouldFilterByDeptFields(scope, field.id)
      return (
        <PersonField
          value={value}
          onChange={onChange}
          multi={field.type === 'person_multi'}
          readonly={readonly}
          placeholder={ph}
          pickableScope={scope}
          deptIds={useDeptFilter ? filterDeptIdsFromValues(allValues, scope?.filter_by_fields) : undefined}
        />
      )
    }
    case 'department':
    case 'department_multi': {
      const scope = (field.props as { pickable_scope?: PickableScope } | undefined)?.pickable_scope
      // 方案管理「科室」历史版本曾标成单选 department，但共同场景值为 id 数组
      const asMulti = field.type === 'department_multi' || Array.isArray(value)
      return (
        <DeptField
          value={value}
          onChange={onChange}
          multi={asMulti}
          readonly={readonly}
          placeholder={ph}
          scopeCode={scope?.scope_code}
          rangeDeptIds={scope?.scope_code ? undefined : scope?.dept_ids}
          includeChildren={scope?.include_children}
        />
      )
    }
    case 'project': {
      const props = (field.props || {}) as {
        prefer_code?: boolean
        project_fill?: 'install_notice'
      }
      const fillMode = props.project_fill
      return (
        <ProjectField
          value={value}
          readonly={readonly}
          placeholder={ph}
          preferCode={!!props.prefer_code}
          onChange={(v) => {
            if (!fillMode || !onPatch) {
              onChange(v)
              return
            }
            if (!v) {
              const cleared: Record<string, unknown> = { [field.id]: undefined }
              for (const k of INSTALL_NOTICE_PROJECT_FILL_CLEAR) cleared[k] = undefined
              onPatch(cleared)
              return
            }
            void fetchInstallNoticeProjectFill(v).then((fill) => {
              onPatch({ [field.id]: v, ...fill })
            }).catch(() => onChange(v))
          }}
        />
      )
    }
    case 'contract': {
      const props = (field.props || {}) as {
        filter_by_department_field?: string
        contract_fill?: 'drawing_no_query' | 'contract_no_select' | 'invoice_application' | 'shipment_notice' | 'biz_bonus_transfer' | 'biz_bonus_biz_initiate' | 'commission_database' | 'payment_allocation'
      }
      const deptField = props.filter_by_department_field
      let formDepartmentId: string | undefined
      if (deptField) {
        const rawDept = allValues[deptField]
        if (Array.isArray(rawDept) && rawDept[0] != null && rawDept[0] !== '') {
          formDepartmentId = String(rawDept[0])
        } else if (rawDept != null && rawDept !== '') {
          formDepartmentId = String(rawDept)
        }
      }
      const pickDepts = contractPickDepartments(currentUser, formDepartmentId)
      const fillMode = props.contract_fill
      const invoicePick = fillMode === 'invoice_application' || fillMode === 'payment_allocation'
      return (
        <ContractField
          value={value}
          readonly={readonly}
          placeholder={ph}
          departmentId={invoicePick ? undefined : pickDepts.departmentId}
          departmentIds={invoicePick ? undefined : pickDepts.departmentIds}
          purpose={invoicePick ? 'invoice_application' : undefined}
          onChange={(v) => {
            if (!fillMode || !onPatch) {
              onChange(v)
              return
            }
            if (!v) {
              const cleared: Record<string, unknown> = { [field.id]: undefined }
              for (const k of PROD_CARD_FILL_CLEAR[fillMode] || []) cleared[k] = undefined
              onPatch(cleared)
              return
            }
            void fetchProdCardContractFill(v, fillMode).then((pack) => {
              onPatch({ [field.id]: v, ...pack.fill })
              warnPriorInvoicesAfterFill(fillMode, pack)
            }).catch((err: unknown) => {
              onChange(v)
              const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
              message.warning(msg || '合同信息带出失败，请刷新后重试或联系管理员')
            })
          }}
        />
      )
    }
    case 'tech_agreement_review': {
      const props = (field.props || {}) as {
        filter_by_submitter_field?: string
        filter_by_department_field?: string
        tar_fill?: 'prod_card_sn'
      }
      const { applicantId, departmentId } = resolveTarFilterIds(
        allValues,
        props.filter_by_submitter_field,
        props.filter_by_department_field,
      )
      const fillMode = props.tar_fill
      return (
        <TechAgreementReviewField
          value={value}
          readonly={readonly}
          placeholder={ph}
          applicantId={applicantId}
          departmentId={departmentId}
          onChange={(v) => {
            if (!fillMode || !onPatch) {
              onChange(v)
              return
            }
            if (!v) {
              const cleared: Record<string, unknown> = { [field.id]: undefined }
              for (const k of PROD_CARD_TAR_FILL_CLEAR) cleared[k] = undefined
              onPatch(cleared)
              return
            }
            void fetchProdCardTarFill(v).then((fill) => {
              onPatch({ [field.id]: v, ...fill })
            }).catch(() => onChange(v))
          }}
        />
      )
    }
    case 'customer': {
      const csFill = !readonly && onPatch && needsCustomerFormFill(fields)
      return (
        <CustomerField
          value={value}
          readonly={readonly}
          placeholder={ph}
          onChange={(v) => {
            if (!csFill) {
              onChange(v)
              return
            }
            if (!v) {
              onPatch!({
                [field.id]: undefined,
                ...clearCustomerFormFillPatch(fields),
              })
              return
            }
            void fetchCustomerFormFill(v).then((fill) => {
              onPatch!({ [field.id]: v, ...pickShipAddressFill(fields, fill) })
            }).catch(() => onChange(v))
          }}
        />
      )
    }
    case 'select_data': {
      const props = (field.props || {}) as {
        source_form_code?: string
        link_fill?: string
        link_field?: string
      }
      const formCode = String(props.source_form_code || '').trim()
      if (!formCode) {
        return <Input value={(value as string) || ''} onChange={(e) => onChange(e.target.value)} placeholder={ph} disabled={readonly} />
      }
      const fillMode = props.link_fill
      const apiLinkField = String(props.link_field || '').trim() || field.id
      return (
        <FormInstanceLookupField
          formCode={formCode}
          linkField={apiLinkField}
          value={value}
          readonly={readonly}
          placeholder={ph || '请选择'}
          onChange={(v) => {
            if (!fillMode || !onPatch) {
              onChange(v)
              return
            }
            const id = v != null && v !== '' ? String(v) : undefined
            if (!id) {
              onChange(undefined)
              const cleared: Record<string, unknown> = inlineCell
                ? {}
                : { [field.id]: undefined }
              for (const k of linkFillClearKeys(field.id, fillMode)) cleared[k] = undefined
              if (Object.keys(cleared).length) onPatch(cleared)
              return
            }
            // 选中时由 onFill 一次性写入 id + 带出字段，避免明细行两次 onChange 竞态
          }}
          onFill={(id, fill) => {
            if (!fillMode || !onPatch) return
            if (!id) {
              const cleared: Record<string, unknown> = inlineCell
                ? { [field.id]: undefined }
                : { [field.id]: undefined }
              for (const k of linkFillClearKeys(field.id, fillMode)) cleared[k] = undefined
              onPatch(cleared)
              return
            }
            onPatch({ [field.id]: id, ...fill })
          }}
        />
      )
    }
    case 'file': {
      const compact = !!(field.props as { compact_upload?: boolean } | undefined)?.compact_upload
        || (fieldSpan != null && fieldSpan <= 8 && !inlineCell)
      const maxCount = Number((field.props as { max_file_count?: number } | undefined)?.max_file_count) || undefined
      return (
        <FileField
          value={value}
          onChange={onChange}
          readonly={readonly}
          downloadDenied={downloadDenied}
          compact={compact}
          displayMode={inlineCell ? 'popover' : 'full'}
          maxCount={maxCount}
        />
      )
    }
    case 'image': {
      const compact = !!(field.props as { compact_upload?: boolean } | undefined)?.compact_upload
        || (fieldSpan != null && fieldSpan <= 8 && !inlineCell)
      const maxCount = Number((field.props as { max_file_count?: number } | undefined)?.max_file_count) || undefined
      return (
        <FileField
          value={value}
          onChange={onChange}
          image
          readonly={readonly}
          downloadDenied={downloadDenied}
          compact={compact}
          displayMode={inlineCell ? 'popover' : 'full'}
          maxCount={maxCount}
        />
      )
    }
    case 'address':
      return (
        <AddressField
          value={value as never} onChange={onChange} readonly={readonly}
          placeholder={ph} showDetail={field.props?.show_detail !== false}
        />
      )
    case 'cascade':
      return (
        <CascadeField
          value={value as string[]} onChange={onChange} readonly={readonly} placeholder={ph}
          options={(field.props?.cascade_options as CascadeOption[]) || []}
        />
      )
    case 'rich_text':
      return <RichTextField value={value as string} onChange={onChange} readonly={readonly} placeholder={ph} />
    case 'signature':
      return (
        <SignatureField
          value={value as string} onChange={onChange} readonly={readonly}
          width={(field.props?.sign_width as number) || 360} height={(field.props?.sign_height as number) || 140}
        />
      )
    case 'text':
      return <Input value={value as string} placeholder={ph} onChange={(e) => onChange(e.target.value)} />
    case 'textarea':
      return <TextArea rows={3} value={value as string} placeholder={ph} onChange={(e) => onChange(e.target.value)} />
    case 'number':
      return <InputNumber style={{ width: '100%' }} value={value as number} placeholder={ph} onChange={(v) => onChange(v)} />
    case 'amount':
      return (
        <InputNumber
          style={{ width: '100%' }} value={value as number} placeholder={ph}
          precision={2} prefix="¥" min={0} onChange={(v) => onChange(v)}
        />
      )
    case 'date':
    case 'datetime': {
      const withTime = fieldShowsTime(field)
      const fmt = dateFieldFormat(field)
      return (
        <DatePicker
          style={{ width: '100%' }}
          showTime={withTime}
          value={value ? dayjs(value as string) : null}
          onChange={(d) => onChange(d ? d.format(fmt) : null)}
        />
      )
    }
    case 'select':
      return (
        <Select
          style={{ width: '100%' }} allowClear value={(value as string) ?? undefined} placeholder={ph}
          options={opts} onChange={(v) => onChange(v)}
        />
      )
    case 'multi_select':
      return (
        <Select
          style={{ width: '100%' }} mode="multiple" allowClear value={(value as string[]) ?? []} placeholder={ph}
          options={opts} onChange={(v) => onChange(v)}
        />
      )
    case 'radio':
      return (
        <Radio.Group
          value={value}
          onChange={(e) => {
            const v = e.target.value
            const isPricing = field.id === 'process_name'
              && onPatch
              && fields.some((f) => f.id in PRICING_CHECKLIST_LINKS)
            if (isPricing) {
              const cleared: Record<string, unknown> = { [field.id]: v }
              for (const k of pricingChecklistAllClearKeys()) cleared[k] = undefined
              cleared[field.id] = v
              onPatch(cleared)
              return
            }
            onChange(v)
          }}
        >
          {opts.map((o) => <Radio key={o.value} value={o.value}>{o.label}</Radio>)}
        </Radio.Group>
      )
    case 'checkbox':
      return (
        <Checkbox.Group
          value={(value as string[]) ?? []}
          options={opts.map((o) => ({ label: o.label, value: o.value }))}
          onChange={(v) => onChange(v)}
        />
      )
    case 'switch':
      return <Switch checked={!!value} onChange={(v) => onChange(v)} />
    case 'formula':
    case 'auto_number': {
      // 默认只读展示；form_editable=true 时可手改（合同图纸对应表图纸编号对齐简道云）
      const preview = field.type === 'auto_number' && serialPreview ? serialPreview : ''
      const display = value != null && value !== '' ? String(value) : preview
      const allowEdit = field.type === 'auto_number'
        && !readonly
        && (field.form_editable === true
          || !!(field.props as { manual_edit?: boolean } | undefined)?.manual_edit)
      if (!allowEdit) {
        return (
          <Input
            value={display}
            disabled
            placeholder={field.type === 'auto_number' ? '提交后自动生成' : '自动计算'}
          />
        )
      }
      const refreshBtn = onRefreshSerial ? (
        <Tooltip title="重新取号">
          <Button
            icon={<ReloadOutlined />}
            loading={!!refreshingSerial}
            onClick={() => onRefreshSerial(field.id)}
          />
        </Tooltip>
      ) : null
      if (refreshBtn) {
        return (
          <Space.Compact className="w-full max-w-full">
            <Input
              value={display}
              placeholder={preview || '可手改；若已占用请点右侧刷新重新取号'}
              onChange={(e) => onChange(e.target.value)}
            />
            {refreshBtn}
          </Space.Compact>
        )
      }
      return (
        <Input
          value={display}
          placeholder={preview || '可手改；若已占用请点右侧刷新重新取号'}
          onChange={(e) => onChange(e.target.value)}
        />
      )
    }
    case 'detail_table':
      return (
        <DetailTable
          field={field}
          readonly={readonly}
          value={value as Record<string, unknown>[]}
          onChange={onChange}
          onPatch={onPatch}
          formValues={allValues}
          rules={rules}
          fields={fields}
          layout={detailLayout}
          createFill={detailCreateFill}
        />
      )
    default:
      return <Input value={value as string} onChange={(e) => onChange(e.target.value)} />
  }
}

function ReadonlyValue({ field, value }: { field: FieldDefinition; value: unknown }) {
  const opts = field.options || []
  const labelOf = (v: unknown) => opts.find((o) => o.value === v)?.label ?? String(v ?? '')
  let display: React.ReactNode = ''
  if (value == null || value === '') display = <Text type="secondary">—</Text>
  else if (field.type === 'switch') display = value ? '是' : '否'
  else if (field.type === 'date' || field.type === 'datetime') {
    const d = dayjs(String(value))
    display = d.isValid() ? d.format(dateFieldDisplayFormat(field)) : String(value)
  }
  else if (Array.isArray(value)) display = value.map(labelOf).join('，')
  else if (field.type === 'select' || field.type === 'radio') display = labelOf(value)
  else if (field.type === 'amount') display = `¥${Number(value).toFixed(2)}`
  else display = String(value)
  // 长文本（如发货明细「公司型号」）审批只读时需换行，避免 ellipsis 截断看不到全文
  const wrapLong = field.type === 'text' || field.type === 'textarea'
    || field.id === 'company_model'
    || (field.label || '').includes('公司型号')
  return (
    <div
      style={{
        paddingTop: 4,
        minHeight: 22,
        ...(wrapLong
          ? { whiteSpace: 'pre-wrap', wordBreak: 'break-word', lineHeight: 1.5 }
          : undefined),
      }}
    >
      {display}
    </div>
  )
}

// ===== 明细子表 =====

function isBlankDetailRow(row: unknown): boolean {
  if (!row || typeof row !== 'object' || Array.isArray(row)) return true
  return Object.values(row as Record<string, unknown>).every(
    (v) => v == null || v === '' || (Array.isArray(v) && v.length === 0),
  )
}

function DetailTable({
  field, readonly, value, onChange, onPatch, formValues = {}, rules = [], fields = [], layout = 'table', createFill = true,
}: {
  field: FieldDefinition
  readonly: boolean
  value: Record<string, unknown>[] | undefined
  onChange: (v: unknown) => void
  onPatch?: (patch: Record<string, unknown>) => void
  formValues?: Record<string, unknown>
  rules?: FormRule[]
  fields?: FieldDefinition[]
  layout?: 'table' | 'cards'
  /** 发起填报：隐藏 available_on_create=false 的明细列 */
  createFill?: boolean
}) {
  const rows = Array.isArray(value) ? value : []
  const [qfOpen, setQfOpen] = useState(false)
  const allCols = (pruneProdCardDetailColumns(field.id, field.detail_table_columns) || []).filter((c) => {
    // 发起填报：隐藏审批阶段列（简道云 optAuth 未授权给发起节点）
    if (createFill && !readonly && (c.available_on_create === false || c.fill_stage === 'approver')) {
      return false
    }
    return true
  })
  const ensureMin = Math.max(0, Number(field.props?.ensure_min_rows ?? 0) || 0)
  const showRowIndex = prodCardDetailShowsRowIndex(field.id)
  // 挂载时：配置了 ensure_min_rows 则补空行；否则清掉误灌的「默认空行」
  const didMountInit = useRef(false)
  useEffect(() => {
    if (didMountInit.current || readonly) return
    didMountInit.current = true
    const cur = Array.isArray(value) ? value : []
    let next = [...cur]
    if (ensureMin > 0 && next.length < ensureMin) {
      while (next.length < ensureMin) next.push(buildDetailRowDefaults(allCols))
    } else if (ensureMin === 0 && next.length === 1 && isBlankDetailRow(next[0])) {
      onChange([])
      return
    }
    const withDefaults = applyDetailRowDefaults(next, allCols)
    if (withDefaults !== next || (ensureMin > 0 && cur.length < ensureMin)) onChange(withDefaults)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 只处理初次挂载（显隐切换会重挂）
  }, [])

  const setCell = (rowIdx: number, colId: string, v: unknown) => {
    const next = rows.map((r, i) => {
      if (i !== rowIdx) return r
      let row: Record<string, unknown> = { ...r, [colId]: v }
      // 筛分效率是否有要求改为否时，清空其后条件字段，避免隐藏值残留
      if (
        (colId === 'need_screening_eff_star' || colId === 'need_screening_eff' || colId === 'need_screening_eff_2')
        && v !== '是'
      ) {
        for (const k of [
          'particle_dist_star', 'particle_dist', 'particle_dist_2',
          'screening_eff_star', 'screening_eff', 'screening_eff_2',
          'moisture_star', 'moisture', 'moisture_2',
          'particle_composition', 'particle_composition_2',
        ]) {
          if (k in row) delete row[k]
        }
      }
      row = recomputeDetailRowOnColChange(row, allCols, colId)
      return row
    })
    onChange(next)
  }
  const colIdSet = useMemo(() => new Set(allCols.map((c) => c.id)), [allCols])
  const patchRow = (rowIdx: number, patch: Record<string, unknown>) => {
    const rowPatch: Record<string, unknown> = {}
    const parentPatch: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(patch)) {
      if (colIdSet.has(k)) rowPatch[k] = v
      else parentPatch[k] = v
    }
    if (!Object.keys(rowPatch).length) {
      if (Object.keys(parentPatch).length) onPatch?.(parentPatch)
      return
    }
    const nextRows = rows.map((r, i) => (i === rowIdx ? { ...r, ...rowPatch } : r))
    if (Object.keys(parentPatch).length && onPatch) {
      onPatch({ ...parentPatch, [field.id]: nextRows })
      return
    }
    onChange(nextRows)
    if (Object.keys(parentPatch).length) onPatch?.(parentPatch)
  }
  const addRow = () => onChange([...rows, buildDetailRowDefaults(allCols)])
  const delRow = (idx: number) => onChange(rows.filter((_, i) => i !== idx))

  const evalRows = rows.length ? rows : [{}]
  const ruleFields = fields.length ? fields : [field]
  const cols = allCols.filter((c) => evalRows.some((row) => isDetailColVisibleInRow(
    c.id, field.id, row, formValues, ruleFields, rules,
  )))
  const quickFillEnabled = !readonly && (
    (field.props as { quick_fill?: boolean } | undefined)?.quick_fill === true
    || PROD_CARD_QUICK_FILL_FIELD_IDS.has(field.id)
  )
  const quickFillFields = useMemo(
    () => detailColumnsToQuickFillSpecs(cols.length ? cols : allCols),
    [allCols, cols],
  )

  const defaultColWidth = (c: FieldDefinition) => {
    if (c.type === 'contract') return 220
    if (c.type === 'image' || c.type === 'file') return 200
    if (c.id === 'company_model' || (c.label || '').includes('公司型号')) return 320
    if ((c.label || '').includes('货物') || (c.label || '').includes('名称')) return 180
    return 140
  }
  /** 长文本列关闭 ellipsis，单元格内自动换行（审批人要看全「公司型号」等） */
  const detailColWraps = (c: FieldDefinition) => {
    if (c.type === 'textarea') return true
    if (c.id === 'company_model' || (c.label || '').includes('公司型号')) return true
    if (c.type === 'text' && /备注|说明|型号|描述|要求|内容/.test(c.label || '')) return true
    return false
  }
  const [colWidths, setColWidths] = useState<Record<string, number>>({})
  const widthOf = (c: FieldDefinition) => colWidths[c.id] ?? defaultColWidth(c)

  if (layout === 'cards') {
    return (
      <div className="space-y-3">
        {rows.map((row, idx) => {
          const visibleCols = allCols.filter((c) => isDetailColVisibleInRow(
            c.id, field.id, row, formValues, ruleFields, rules,
          ))
          return (
            <div key={idx} className="rounded-xl border border-slate-200 bg-slate-50/80 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-bold text-slate-600">{showRowIndex ? `序号 ${idx + 1}` : `第 ${idx + 1} 行`}</span>
                {!readonly && (
                  <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => delRow(idx)}>
                    删除
                  </Button>
                )}
              </div>
              <div className="space-y-3">
                {visibleCols.map((c) => (
                  <div key={c.id}>
                    <div className="text-xs text-slate-500 mb-1">
                      {c.required ? <span style={{ color: '#ff4d4f' }}>*</span> : null}
                      {c.label}
                    </div>
                    <FieldWidget
                      field={c}
                      readonly={readonly}
                      value={row[c.id]}
                      allValues={row}
                      onChange={(v) => setCell(idx, c.id, v)}
                      onPatch={(patch) => patchRow(idx, patch)}
                      inlineCell={c.type === 'file' || c.type === 'image' || c.type === 'select_data'}
                    />
                  </div>
                ))}
              </div>
            </div>
          )
        })}
        {!rows.length && (
          <div className="text-sm text-slate-400 text-center py-4">暂无明细</div>
        )}
        {!readonly && (
          <Space>
            <Button type="dashed" block icon={<PlusOutlined />} onClick={addRow}>
              添加一行
            </Button>
            {quickFillEnabled && quickFillFields.length > 0 && (
              <Button type="link" icon={<ThunderboltOutlined />} onClick={() => setQfOpen(true)}>
                快速填报
              </Button>
            )}
          </Space>
        )}
        {quickFillEnabled && quickFillFields.length > 0 && (
          <DetailQuickFillModal
            open={qfOpen}
            title={`快速填报 · ${field.label || ''}`}
            fields={quickFillFields}
            existingRows={rows}
            onClose={() => setQfOpen(false)}
            onConfirm={(incoming, mode) => {
              const base = mode === 'replace' ? [] : rows
              onChange(applyDetailRowDefaults([...base, ...incoming], allCols))
            }}
          />
        )}
      </div>
    )
  }

  const opColumn: ColumnType<Record<string, unknown>>[] = readonly ? [] : [{
    title: '操作', key: '__op', width: 70, fixed: 'left' as const,
    render: (_: unknown, _row: Record<string, unknown>, idx: number) => (
      <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => delRow(idx)} />
    ),
  }]

  const rowIndexColumn: ColumnType<Record<string, unknown>>[] = showRowIndex ? [{
    title: '序号',
    key: '__row_index',
    width: 56,
    fixed: 'left' as const,
    align: 'center' as const,
    render: (_: unknown, _row: Record<string, unknown>, idx: number) => (
      <span className="text-slate-600">{idx + 1}</span>
    ),
  }] : []

  const columns: ColumnType<Record<string, unknown>>[] = [
    ...opColumn,
    ...rowIndexColumn,
    ...cols.map((c) => {
      const w = widthOf(c)
      const wrap = detailColWraps(c)
      return {
        title: (<span>{c.required && <span style={{ color: '#ff4d4f' }}>*</span>}{c.label}</span>),
        dataIndex: c.id,
        key: c.id,
        width: w,
        // 长文本列禁止截断，否则审批抽屉里「公司型号」只显示半截
        ellipsis: wrap ? false : true,
        onHeaderCell: () => ({
          width: w,
          colKey: c.id,
        }),
        onCell: wrap ? () => ({ className: 'detail-cell-wrap' }) : undefined,
        render: (_: unknown, _row: Record<string, unknown>, idx: number) => {
          const row = rows[idx] || {}
          const visible = isDetailColVisibleInRow(
            c.id, field.id, row, formValues, ruleFields, rules,
          )
          if (!visible) return null
          return (
            <FieldWidget
              field={c} readonly={readonly}
              value={row[c.id]} allValues={row}
              onChange={(v) => setCell(idx, c.id, v)}
              onPatch={(patch) => patchRow(idx, patch)}
              inlineCell={c.type === 'file' || c.type === 'image' || c.type === 'select_data'}
            />
          )
        },
      }
    }),
  ]

  return (
    <div>
      <div className="detail-table-resizable-wrap">
        <FillHeightTable
          size="small"
          rowKey={(_, i) => String(i)}
          pagination={false}
          dataSource={rows}
          columns={columns}
          bodyHeight={false}
          resizableColumns
          onColumnWidthChange={(colKey, width) => {
            setColWidths((prev) => ({ ...prev, [colKey]: width }))
          }}
          scroll={{ x: 'max-content' }}
          locale={{ emptyText: '暂无明细' }}
        />
      </div>
      {!readonly && (
        <Space style={{ marginTop: 8 }}>
          <Button type="dashed" icon={<PlusOutlined />} onClick={addRow}>
            添加一行
          </Button>
          {quickFillEnabled && quickFillFields.length > 0 && (
            <Button type="link" icon={<ThunderboltOutlined />} onClick={() => setQfOpen(true)}>
              快速填报
            </Button>
          )}
        </Space>
      )}
      {quickFillEnabled && quickFillFields.length > 0 && (
        <DetailQuickFillModal
          open={qfOpen}
          title={`快速填报 · ${field.label || ''}`}
          fields={quickFillFields}
          existingRows={rows}
          onClose={() => setQfOpen(false)}
          onConfirm={(incoming, mode) => {
            const base = mode === 'replace' ? [] : rows
            onChange(applyDetailRowDefaults([...base, ...incoming], allCols))
          }}
        />
      )}
    </div>
  )
}

// 客户端必填校验(即时反馈;后端仍会二次校验)。
export type RequiredFieldError = { message: string; fieldId: string }

export function findRequiredError(
  fields: FieldDefinition[],
  states: Record<string, FieldState>,
  values: Record<string, unknown>,
  rules: FormRule[] = [],
): RequiredFieldError | null {
    const empty = (v: unknown) => {
      if (v == null || v === '') return true
      if (Array.isArray(v) && v.length === 0) return true
      if (typeof v === 'object') {
        const o = v as Record<string, unknown>
        if ('id' in o || 'value' in o) {
          const id = o.id ?? o.value
          return id == null || id === ''
        }
      }
      return false
    }
  for (const f of fields) {
    if (f.type === 'formula' || f.type === 'auto_number') continue
    if (f.type === 'section' || f.type === 'separator') continue
    // 审批阶段字段：创建不必填
    if (isCreateHiddenField(f)) continue
    const st = states[f.id]
    if (st && !st.visible) continue
    // 脱敏字段跳过必填：看不到明文就无法填写，脱敏+必填会让记录永远存不下去
    if (st?.masked) continue
    const label = f.label || f.id
    const req = st ? st.required : f.required
    if (req && empty(values[f.id])) return { message: `「${label}」为必填项`, fieldId: f.id }
    if (f.type === 'detail_table') {
      const rows = values[f.id]
      if (!Array.isArray(rows) || !rows.length) continue
      for (let i = 0; i < rows.length; i++) {
        const row = (rows[i] && typeof rows[i] === 'object')
          ? (rows[i] as Record<string, unknown>)
          : {}
        const rowStates = computeFieldStates(fields, { ...values, [f.id]: [row] }, rules)
        for (const c of f.detail_table_columns || []) {
          if (c.type === 'formula') continue
          if (c.available_on_create === false || c.fill_stage === 'approver') continue
          const cst = rowStates[c.id]
          if (cst && !cst.visible) continue
          const colReq = cst ? cst.required : !!c.required
          if (colReq && empty(row[c.id])) {
            return {
              message: `「${label}」第 ${i + 1} 行「${c.label || c.id}」为必填项`,
              fieldId: f.id,
            }
          }
        }
      }
    }
  }
  return null
}

/** 滚到低代码字段锚点并短暂高亮，便于提交校验失败时定位。 */
export function scrollToLcField(fieldId: string) {
  if (!fieldId || typeof document === 'undefined') return
  const el = document.querySelector(`[data-lc-field="${CSS.escape(fieldId)}"]`) as HTMLElement | null
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  const prevOutline = el.style.outline
  const prevOffset = el.style.outlineOffset
  el.style.outline = '2px solid #ff4d4f'
  el.style.outlineOffset = '4px'
  window.setTimeout(() => {
    el.style.outline = prevOutline
    el.style.outlineOffset = prevOffset
  }, 1600)
  const focusable = el.querySelector(
    'input:not([disabled]),textarea:not([disabled]),select:not([disabled]),button:not([disabled]),[tabindex]:not([tabindex="-1"])',
  ) as HTMLElement | null
  try {
    focusable?.focus({ preventScroll: true })
  } catch { /* ignore */ }
}

export function validateRequired(
  fields: FieldDefinition[],
  states: Record<string, FieldState>,
  values: Record<string, unknown>,
  rules: FormRule[] = [],
): string | null {
  return findRequiredError(fields, states, values, rules)?.message ?? null
}
