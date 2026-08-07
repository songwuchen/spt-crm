// 动态表单渲染器 —— 按 FieldDefinition schema 渲染填报/只读表单。
// 移植/重写自 spt-lowcode FormRenderer,聚焦核心自足字段类型;人员/部门/附件等高级类型
// 暂以占位呈现(后续切片接入)。规则引擎(显隐/只读/必填)复用 RuleEngine。
import { useEffect, useMemo, useRef } from 'react'
import {
  Row, Col, Input, InputNumber, DatePicker, Select, Radio, Checkbox, Switch,
  Button, Table, Typography, Tag, Empty,
} from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
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
import ProjectField from './fields/ProjectField'
import ContractField from './fields/ContractField'
import CustomerField from './fields/CustomerField'
import FileField from './fields/FileField'
import AddressField from './fields/AddressField'
import CascadeField, { type CascadeOption } from './fields/CascadeField'
import RichTextField from './fields/RichTextField'
import SignatureField from './fields/SignatureField'
import BaseFormLookupField, { parseFormOptionsSource } from './fields/BaseFormLookupField'
import ContractSectionTitle from '@/components/ContractSectionTitle'

const { TextArea } = Input
const { Text } = Typography

// 已完整支持的字段类型;其余类型以占位呈现。
const SUPPORTED = new Set([
  'text', 'textarea', 'number', 'amount', 'date', 'datetime',
  'select', 'multi_select', 'radio', 'checkbox', 'switch',
  'formula', 'auto_number', 'detail_table',
  'person', 'person_multi', 'department', 'department_multi', 'file', 'image',
  'address', 'cascade', 'rich_text', 'signature', 'project', 'contract', 'customer',
])

// 这些类型自行渲染只读态(名称/URL 需异步解析或富媒体展示),不走通用 ReadonlyValue。
const SELF_RENDER_READONLY = new Set([
  'detail_table', 'person', 'person_multi', 'department', 'department_multi', 'file', 'image',
  'address', 'cascade', 'rich_text', 'signature', 'project', 'contract', 'customer',
])

const GROUP_TYPES = new Set(['tab_group', 'collapse_section'])

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
  /** 明细子表布局：手机端用 cards */
  detailLayout?: 'table' | 'cards'
}

// 由字段的 visible_roles/edit_roles + 当前用户角色，推导出规则引擎可用的 FieldPermission[]。
// 空/缺省 = 不限制；不可见→hidden；可见但不可编辑→readonly。
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

export default function FormRenderer({ fields, rules = [], mode = 'edit', value, onChange, applyFieldPerms = true, ruleContext, serialPreviews, detailLayout = 'table' }: Props) {
  const userRoles = useAuthStore((s) => s.user?.roles) || []
  const rolePerms = useMemo(
    () => (applyFieldPerms ? deriveRolePerms(fields, userRoles) : []),
    [applyFieldPerms, fields, userRoles],
  )
  // 本表单字段值优先于外部上下文（同名时以用户在本表单里填的为准）
  const ruleValues = useMemo(
    () => (ruleContext ? { ...ruleContext, ...value } : value),
    [ruleContext, value],
  )
  const states = useMemo(
    () => computeFieldStates(fields, ruleValues, rules, rolePerms),
    [fields, ruleValues, rules, rolePerms],
  )

  const setField = (id: string, v: unknown) => {
    onChange?.({ ...value, [id]: v })
  }

  const topFields = fields.filter((f) => !GROUP_TYPES.has(f.type))
  if (!topFields.length) return <Empty description="该表单暂无字段" />

  return (
    <Row gutter={16}>
      {topFields.map((field) => {
        if (field.type === 'section' || field.type === 'separator') {
          return (
            <Col span={24} key={field.id}>
              <ContractSectionTitle title={field.label} className="mt-2 mb-1" />
            </Col>
          )
        }
        // 审批阶段才填的字段：创建/编辑填报页不展示（详情只读仍展示）
        if (mode === 'edit' && field.available_on_create === false) return null
        const st = states[field.id]
        if (st && !st.visible) return null
        // detail_table 强制整行，避免明细列被挤扁
        const span = field.type === 'detail_table' ? 24 : (field.span || 24)
        return (
          <Col span={span} key={field.id}>
            <FieldItem
              field={field}
              state={st}
              mode={mode}
              value={value[field.id]}
              allValues={ruleValues}
              onChange={(v) => setField(field.id, v)}
              serialPreview={serialPreviews?.[field.id]}
              rules={rules}
              fields={fields}
              detailLayout={detailLayout}
            />
          </Col>
        )
      })}
    </Row>
  )
}

function FieldItem({
  field, state, mode, value, allValues, onChange, serialPreview, rules = [], fields = [], detailLayout = 'table',
}: {
  field: FieldDefinition
  state?: FieldState
  mode: 'edit' | 'readonly'
  value: unknown
  allValues: Record<string, unknown>
  onChange: (v: unknown) => void
  serialPreview?: string
  rules?: FormRule[]
  fields?: FieldDefinition[]
  detailLayout?: 'table' | 'cards'
}) {
  const readonly = mode === 'readonly' || state?.readonly
    || !!(field.props as { read_only?: boolean } | undefined)?.read_only
    || !!field.readonly
  const required = state?.required
  // 脱敏字段一律不渲染真实控件：后端已把值换成 "***"，但若值恰好没被裁到（如设计器预览），
  // 这里也不能把明文渲染出去。
  const masked = state?.masked || field.masked
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ marginBottom: 4, fontSize: 13, color: 'rgba(0,0,0,0.75)' }}>
        {required && <span style={{ color: '#ff4d4f', marginRight: 4 }}>*</span>}
        {field.label}
        {field.description && (
          <Text type="secondary" style={{ marginLeft: 8, fontSize: 12 }}>
            {field.description}
          </Text>
        )}
      </div>
      {masked
        ? <Text type="secondary" title="您所在角色无权查看该字段的明文">{MASK_VALUE}</Text>
        : (
          <FieldWidget
            field={field}
            readonly={!!readonly}
            value={value}
            allValues={allValues}
            onChange={onChange}
            serialPreview={serialPreview}
            rules={rules}
            fields={fields}
            detailLayout={detailLayout}
          />
        )}
    </div>
  )
}

function FieldWidget({
  field, readonly, value, allValues, onChange, serialPreview, rules = [], fields = [], detailLayout = 'table',
}: {
  field: FieldDefinition
  readonly: boolean
  value: unknown
  allValues: Record<string, unknown>
  onChange: (v: unknown) => void
  serialPreview?: string
  rules?: FormRule[]
  fields?: FieldDefinition[]
  detailLayout?: 'table' | 'cards'
}) {
  const opts = field.options || []
  const ph = field.placeholder

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
      const scopeCode = (field.props as { pickable_scope?: PickableScope } | undefined)?.pickable_scope?.scope_code
      return (
        <DeptField
          value={value}
          onChange={onChange}
          multi={field.type === 'department_multi'}
          readonly={readonly}
          placeholder={ph}
          scopeCode={scopeCode}
        />
      )
    }
    case 'project':
      return <ProjectField value={value} onChange={onChange} readonly={readonly} placeholder={ph} />
    case 'contract':
      return <ContractField value={value} onChange={onChange} readonly={readonly} placeholder={ph} />
    case 'customer':
      return <CustomerField value={value} onChange={onChange} readonly={readonly} placeholder={ph} />
    case 'file':
      return <FileField value={value} onChange={onChange} readonly={readonly} />
    case 'image':
      return <FileField value={value} onChange={onChange} image readonly={readonly} />
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
        <Radio.Group value={value} onChange={(e) => onChange(e.target.value)}>
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
      // 系统计算/生成字段: 只读展示。auto_number 优先已存值，否则展示预览号（提交时后端正式取号）
      const display = value != null && value !== ''
        ? String(value)
        : (field.type === 'auto_number' && serialPreview ? serialPreview : '')
      return (
        <Input
          value={display}
          disabled
          placeholder={field.type === 'auto_number' ? '提交后自动生成' : '自动计算'}
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
          formValues={allValues}
          rules={rules}
          fields={fields}
          layout={detailLayout}
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
  return <div style={{ paddingTop: 4, minHeight: 22 }}>{display}</div>
}

// ===== 明细子表 =====

function isBlankDetailRow(row: unknown): boolean {
  if (!row || typeof row !== 'object' || Array.isArray(row)) return true
  return Object.values(row as Record<string, unknown>).every(
    (v) => v == null || v === '' || (Array.isArray(v) && v.length === 0),
  )
}

function DetailTable({
  field, readonly, value, onChange, formValues = {}, rules = [], fields = [], layout = 'table',
}: {
  field: FieldDefinition
  readonly: boolean
  value: Record<string, unknown>[] | undefined
  onChange: (v: unknown) => void
  formValues?: Record<string, unknown>
  rules?: FormRule[]
  fields?: FieldDefinition[]
  layout?: 'table' | 'cards'
}) {
  const rows = Array.isArray(value) ? value : []
  const allCols = field.detail_table_columns || []
  const ensureMin = Math.max(0, Number(field.props?.ensure_min_rows ?? 0) || 0)
  // 挂载时：配置了 ensure_min_rows 则补空行；否则清掉误灌的「默认空行」
  const didMountInit = useRef(false)
  useEffect(() => {
    if (didMountInit.current || readonly) return
    didMountInit.current = true
    const cur = Array.isArray(value) ? value : []
    if (ensureMin > 0) {
      if (cur.length < ensureMin) {
        const next = [...cur]
        while (next.length < ensureMin) next.push({})
        onChange(next)
      }
      return
    }
    if (cur.length === 1 && isBlankDetailRow(cur[0])) onChange([])
    // eslint-disable-next-line react-hooks/exhaustive-deps -- 只处理初次挂载（显隐切换会重挂）
  }, [])

  const setCell = (rowIdx: number, colId: string, v: unknown) => {
    const next = rows.map((r, i) => {
      if (i !== rowIdx) return r
      const row = { ...r, [colId]: v }
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
      return row
    })
    onChange(next)
  }
  const addRow = () => onChange([...rows, {}])
  const delRow = (idx: number) => onChange(rows.filter((_, i) => i !== idx))

  const evalRows = rows.length ? rows : [{}]
  const ruleFields = fields.length ? fields : [field]
  const cols = allCols.filter((c) => evalRows.some((row) => isDetailColVisibleInRow(
    c.id, field.id, row, formValues, ruleFields, rules,
  )))

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
                <span className="text-sm font-bold text-slate-600">第 {idx + 1} 行</span>
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
          <Button type="dashed" block icon={<PlusOutlined />} onClick={addRow}>
            添加一行
          </Button>
        )}
      </div>
    )
  }

  const columns = [
    ...cols.map((c) => ({
      title: (<span>{c.required && <span style={{ color: '#ff4d4f' }}>*</span>}{c.label}</span>),
      dataIndex: c.id,
      key: c.id,
      minWidth: 140,
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
          />
        )
      },
    })),
    ...(readonly ? [] : [{
      title: '操作', key: '__op', width: 70,
      render: (_: unknown, _row: Record<string, unknown>, idx: number) => (
        <Button type="text" danger size="small" icon={<DeleteOutlined />} onClick={() => delRow(idx)} />
      ),
    }]),
  ]

  return (
    <div>
      <Table
        size="small" rowKey={(_, i) => String(i)} pagination={false}
        dataSource={rows} columns={columns as never}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: '暂无明细' }}
      />
      {!readonly && (
        <Button type="dashed" block icon={<PlusOutlined />} style={{ marginTop: 8 }} onClick={addRow}>
          添加一行
        </Button>
      )}
    </div>
  )
}

// 客户端必填校验(即时反馈;后端仍会二次校验)。返回首个错误或 null。
export function validateRequired(
  fields: FieldDefinition[],
  states: Record<string, FieldState>,
  values: Record<string, unknown>,
  rules: FormRule[] = [],
): string | null {
  const empty = (v: unknown) => v == null || v === '' || (Array.isArray(v) && v.length === 0)
  for (const f of fields) {
    if (f.type === 'formula' || f.type === 'auto_number') continue
    if (f.type === 'section' || f.type === 'separator') continue
    // 审批阶段字段：创建不必填
    if (f.available_on_create === false) continue
    const st = states[f.id]
    if (st && !st.visible) continue
    // 脱敏字段跳过必填：看不到明文就无法填写，脱敏+必填会让记录永远存不下去
    if (st?.masked) continue
    const req = st ? st.required : f.required
    if (req && empty(values[f.id])) return `「${f.label}」为必填项`
    if (f.type === 'detail_table') {
      const rows = values[f.id]
      if (!Array.isArray(rows) || !rows.length) continue
      for (let i = 0; i < rows.length; i++) {
        const row = (rows[i] && typeof rows[i] === 'object')
          ? (rows[i] as Record<string, unknown>)
          : {}
        const rowStates = computeFieldStates(fields, { ...values, [f.id]: [row] }, rules)
        for (const c of f.detail_table_columns || []) {
          const cst = rowStates[c.id]
          if (cst && !cst.visible) continue
          const colReq = cst ? cst.required : !!c.required
          if (colReq && empty(row[c.id])) {
            return `「${f.label}」第 ${i + 1} 行「${c.label}」为必填项`
          }
        }
      }
    }
  }
  return null
}
