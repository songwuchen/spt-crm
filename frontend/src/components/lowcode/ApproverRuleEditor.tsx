/** 流程节点审批人/抄送人规则编辑（含组合选人 mixed）。 */
import { useEffect, useState } from 'react'
import { Button, Checkbox, Input, Select, Space, Typography } from 'antd'
import { DeleteOutlined, PlusOutlined, TeamOutlined } from '@ant-design/icons'
import PersonField from '@/components/lowcode/fields/PersonField'
import DeptField from '@/components/lowcode/fields/DeptField'
import { pickableScopeApi } from '@/api/pickableScope'
import { lowcodeApi } from '@/api/lowcode'
import type { ApproverType, FieldDefinition, WfApproverRule } from '@/types/lowcode'
import {
  applyDeptHeadToApproverRule,
  approverRuleHasDeptHead,
  stripDeptHeadFromApproverRule,
} from '@/utils/wfApproverRuleMix'

const { Text } = Typography

type NeedValue = 'user' | 'field_person' | 'field_dept' | 'dept_fixed' | 'role' | 'pickable_scope' | 'mixed'

export type ApproverTypeMeta = {
  value: ApproverType
  label: string
  needValue?: NeedValue
}

/** 单一选人规则（可嵌进 mixed；不可再嵌套 mixed） */
export const ATOMIC_APPROVER_TYPES: ApproverTypeMeta[] = [
  { value: 'specified_user', label: '指定人员', needValue: 'user' },
  { value: 'creator', label: '发起人本人' },
  { value: 'direct_supervisor', label: '直接上级' },
  { value: 'dept_head', label: '部门负责人' },
  { value: 'dept_members', label: '指定部门·全体成员', needValue: 'dept_fixed' },
  { value: 'multi_level_superior', label: '逐级上级' },
  { value: 'form_field_person', label: '表单人员字段', needValue: 'field_person' },
  { value: 'form_field_person_dept_head', label: '表单人员·部门负责人', needValue: 'field_person' },
  { value: 'form_field_dept', label: '表单部门·负责人', needValue: 'field_dept' },
  { value: 'form_field_dept_members', label: '表单部门·全体成员', needValue: 'field_dept' },
  { value: 'pickable_scope', label: '可选范围', needValue: 'pickable_scope' },
  { value: 'specified_role', label: '指定角色', needValue: 'role' },
]

export const APPROVER_TYPES: ApproverTypeMeta[] = [
  ...ATOMIC_APPROVER_TYPES,
  { value: 'mixed', label: '组合选人', needValue: 'mixed' },
]

function personFieldOptions(formFields: FieldDefinition[], currents: string[] = [], deptHead = false) {
  const opts = formFields
    .filter((f) => f.type === 'person' || f.type === 'person_multi')
    .map((f) => ({
      value: f.id,
      label: deptHead ? `${f.label || f.id}·部门负责人` : (f.label || f.id),
    }))
  for (const current of currents) {
    if (current && !opts.some((o) => o.value === current)) {
      opts.unshift({ value: current, label: current })
    }
  }
  return opts
}

function deptFieldOptions(formFields: FieldDefinition[], currents: string[] = []) {
  const opts = formFields
    .filter((f) => f.type === 'department' || f.type === 'department_multi')
    .map((f) => ({ value: f.id, label: f.label || f.id }))
  for (const current of currents) {
    if (current && !opts.some((o) => o.value === current)) {
      opts.unshift({ value: current, label: current })
    }
  }
  return opts
}

function asFieldIds(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean)
  if (typeof value === 'string' && value.trim()) return [value.trim()]
  return []
}

function asDeptIds(value: unknown): string[] {
  return asFieldIds(value)
}

/** 单字段存 string，多字段存 string[]（对齐后端 form_field_person 解析） */
function normalizeFieldIds(ids: string[]): string | string[] | undefined {
  if (ids.length <= 1) return ids[0] || undefined
  return ids
}

function asSubRules(value: unknown): WfApproverRule[] {
  if (!Array.isArray(value)) return []
  return value.filter((x): x is WfApproverRule => !!x && typeof x === 'object' && !!(x as WfApproverRule).type)
}

function PickableScopeSelect({
  value,
  onChange,
}: {
  value: unknown
  onChange: (value: unknown) => void
}) {
  const [opts, setOpts] = useState<{ value: string; label: string }[]>([])
  useEffect(() => {
    pickableScopeApi.listForPicker({ kind: 'person' }).then((r) => {
      const list = Array.isArray(r.data) ? r.data : []
      setOpts(list.map((s) => ({ value: s.code, label: `${s.name} (${s.code})` })))
    }).catch(() => setOpts([]))
  }, [])
  const cur = typeof value === 'string' ? value : Array.isArray(value) ? String(value[0] || '') : undefined
  const options = [...opts]
  if (cur && !options.some((o) => o.value === cur)) {
    options.unshift({ value: cur, label: cur })
  }
  return (
    <Select
      size="small"
      style={{ width: '100%' }}
      placeholder="选择可选范围"
      value={cur || undefined}
      options={options}
      optionFilterProp="label"
      showSearch
      onChange={onChange}
    />
  )
}

/** 指定角色：从角色管理列表点选，展示中文名（对齐简道云） */
function RoleSelect({
  value,
  onChange,
}: {
  value: unknown
  onChange: (value: unknown) => void
}) {
  const [opts, setOpts] = useState<{ value: string; label: string; name: string; member_count: number }[]>([])
  const selected = Array.isArray(value)
    ? value.map(String).filter(Boolean)
    : (typeof value === 'string' && value ? [value] : [])

  useEffect(() => {
    lowcodeApi.pickableRoles({ codes: selected.join(',') || undefined }).then((r) => {
      const list = Array.isArray(r.data) ? r.data : []
      setOpts(list.map((role) => ({
        value: role.code,
        name: role.name || role.code,
        member_count: role.member_count ?? 0,
        label: `${role.name || role.code}${typeof role.member_count === 'number' ? `（${role.member_count}人）` : ''}`,
      })))
    }).catch(() => setOpts([]))
  // 仅挂载时拉全量；回显靠 options 补全
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const options = [...opts]
  for (const code of selected) {
    if (!options.some((o) => o.value === code)) {
      options.unshift({ value: code, name: code, member_count: 0, label: code })
    }
  }

  return (
    <Select
      size="small"
      mode="multiple"
      allowClear
      style={{ width: '100%' }}
      placeholder="选择角色（显示中文名）"
      value={selected}
      options={options}
      optionFilterProp="label"
      showSearch
      optionRender={(opt) => (
        <div className="flex items-center gap-2 py-0.5">
          <TeamOutlined className="text-blue-500" />
          <div className="min-w-0 flex-1">
            <div className="truncate text-slate-800">{String(opt.data?.name || opt.label)}</div>
            <div className="text-xs text-slate-400 truncate">
              {String(opt.value)}
              {typeof opt.data?.member_count === 'number' ? ` · ${opt.data.member_count} 人` : ''}
            </div>
          </div>
        </div>
      )}
      tagRender={({ value: code, closable, onClose }) => {
        const opt = options.find((o) => o.value === code)
        return (
          <span className="ant-select-selection-item inline-flex items-center gap-1 !me-1 !ps-1.5">
            <TeamOutlined className="text-blue-500 text-xs" />
            <span className="max-w-[160px] truncate">{opt?.name || String(code)}</span>
            {closable ? (
              <span className="ant-select-selection-item-remove cursor-pointer" onClick={onClose}>×</span>
            ) : null}
          </span>
        )
      }}
      onChange={(codes) => onChange(codes.length <= 1 ? (codes[0] || undefined) : codes)}
    />
  )
}

/** 单一规则的取值区（不含 type 选择） */
function AtomicValueEditor({
  rule,
  formFields,
  onChange,
}: {
  rule: WfApproverRule
  formFields: FieldDefinition[]
  onChange: (value: unknown) => void
}) {
  const meta = ATOMIC_APPROVER_TYPES.find((a) => a.value === rule.type)
  if (!meta?.needValue) {
    return <Text type="secondary" style={{ fontSize: 12 }}>无需指定</Text>
  }
  if (meta.needValue === 'user') {
    return <PersonField value={rule.value} onChange={onChange} multi />
  }
  if (meta.needValue === 'field_person') {
    const selected = asFieldIds(rule.value)
    const isPersonDeptHead = rule.type === 'form_field_person_dept_head'
    return (
      <Select
        size="small"
        mode="multiple"
        allowClear
        style={{ width: '100%' }}
        placeholder={isPersonDeptHead ? '选择人员字段（取其所属部门负责人）' : '选择人员字段（可多选，取并集）'}
        value={selected}
        options={personFieldOptions(formFields, selected, isPersonDeptHead)}
        optionFilterProp="label"
        showSearch
        onChange={(ids) => onChange(normalizeFieldIds(ids))}
      />
    )
  }
  if (meta.needValue === 'field_dept') {
    const selected = asFieldIds(rule.value)
    const hint = rule.type === 'form_field_dept_members'
      ? '选择部门字段（抄送该部门全部成员）'
      : '选择部门字段（取各部门负责人）'
    return (
      <Select
        size="small"
        mode="multiple"
        allowClear
        style={{ width: '100%' }}
        placeholder={hint}
        value={selected}
        options={deptFieldOptions(formFields, selected)}
        optionFilterProp="label"
        showSearch
        onChange={(ids) => onChange(normalizeFieldIds(ids))}
      />
    )
  }
  if (meta.needValue === 'dept_fixed') {
    const selected = asDeptIds(rule.value)
    return (
      <DeptField
        multi
        value={selected}
        onChange={(nv) => onChange(Array.isArray(nv) ? nv : nv ? [nv] : [])}
        placeholder="选择部门（可多选，抄送各部门全部成员）"
      />
    )
  }
  if (meta.needValue === 'pickable_scope') {
    return <PickableScopeSelect value={rule.value} onChange={onChange} />
  }
  if (meta.needValue === 'role') {
    return <RoleSelect value={rule.value} onChange={onChange} />
  }
  return (
    <Input
      size="small"
      placeholder="角色码，逗号分隔"
      value={Array.isArray(rule.value) ? (rule.value as string[]).join(',') : (rule.value as string) || ''}
      onChange={(e) => onChange(e.target.value.split(',').map((s) => s.trim()).filter(Boolean))}
    />
  )
}

function MixedEditor({
  value,
  formFields,
  onChange,
}: {
  value: unknown
  formFields: FieldDefinition[]
  onChange: (subs: WfApproverRule[]) => void
}) {
  const subs = asSubRules(value)

  const patchAt = (idx: number, patch: Partial<WfApproverRule>) => {
    const next = subs.map((s, i) => (i === idx ? { ...s, ...patch } : s))
    onChange(next)
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={6}>
      <Text type="secondary" style={{ fontSize: 12 }}>
        组合多条规则，运行时取人员并集（去重）
      </Text>
      {subs.map((sub, idx) => (
        <div
          key={idx}
          style={{
            border: '1px solid var(--ant-color-border-secondary, #f0f0f0)',
            borderRadius: 6,
            padding: 8,
            background: 'var(--ant-color-fill-quaternary, #fafafa)',
          }}
        >
          <Space direction="vertical" style={{ width: '100%' }} size={4}>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <Select
                size="small"
                style={{ flex: 1 }}
                value={sub.type}
                options={ATOMIC_APPROVER_TYPES.map((t) => ({ label: t.label, value: t.value }))}
                onChange={(t) => patchAt(idx, { type: t, value: undefined })}
              />
              <Button
                size="small"
                type="text"
                danger
                icon={<DeleteOutlined />}
                disabled={subs.length <= 1}
                onClick={() => onChange(subs.filter((_, i) => i !== idx))}
              />
            </div>
            <AtomicValueEditor
              rule={sub}
              formFields={formFields}
              onChange={(v) => patchAt(idx, { value: v })}
            />
          </Space>
        </div>
      ))}
      <Button
        size="small"
        type="dashed"
        block
        icon={<PlusOutlined />}
        onClick={() => onChange([...subs, { type: 'creator' }])}
      >
        添加选人规则
      </Button>
    </Space>
  )
}

export function ApproverRuleEditor({
  rule,
  formFields,
  onChange,
  roleLabel = '审批人',
  deptHeadAddon = false,
}: {
  rule?: WfApproverRule
  formFields: FieldDefinition[]
  /** 整份规则变更（切换类型时会重置 value） */
  onChange: (next: WfApproverRule) => void
  roleLabel?: string
  /** 抄送场景：勾选后额外抄送表单部门/发起人部门的部门负责人 */
  deptHeadAddon?: boolean
}) {
  const current = rule || { type: 'creator' as ApproverType }
  const mainRule = deptHeadAddon ? stripDeptHeadFromApproverRule(current) : current
  const meta = APPROVER_TYPES.find((a) => a.value === mainRule.type)
  const typeValue = APPROVER_TYPES.some((t) => t.value === mainRule.type)
    ? mainRule.type
    : mainRule.type

  const emitMain = (nextMain: WfApproverRule) => {
    onChange(deptHeadAddon && approverRuleHasDeptHead(current)
      ? applyDeptHeadToApproverRule(nextMain, true)
      : nextMain)
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="small">
      <div>
        <Text type="secondary" style={{ fontSize: 12 }}>{roleLabel}</Text>
        <Select
          size="small"
          style={{ width: '100%' }}
          value={typeValue}
          options={APPROVER_TYPES.map((t) => ({ label: t.label, value: t.value }))}
          onChange={(t) => {
            if (t === 'mixed') {
              emitMain({
                type: 'mixed',
                value: asSubRules(mainRule.value).length
                  ? asSubRules(mainRule.value)
                  : [{ type: 'creator' }],
              })
              return
            }
            emitMain({ type: t, value: undefined })
          }}
        />
      </div>
      {meta?.needValue === 'mixed' ? (
        <MixedEditor
          value={mainRule.value}
          formFields={formFields}
          onChange={(subs) => emitMain({ type: 'mixed', value: subs })}
        />
      ) : meta?.needValue ? (
        <>
          <AtomicValueEditor
            rule={mainRule}
            formFields={formFields}
            onChange={(v) => emitMain({ ...mainRule, value: v })}
          />
          {(mainRule.type === 'dept_members' || mainRule.type === 'form_field_dept_members') && (
            <Checkbox
              checked={!!mainRule.include_sub}
              onChange={(e) => emitMain({ ...mainRule, include_sub: e.target.checked })}
            >
              含下级部门成员
            </Checkbox>
          )}
        </>
      ) : null}
      {deptHeadAddon && mainRule.type !== 'mixed' && (
        <Checkbox
          checked={approverRuleHasDeptHead(current)}
          onChange={(e) => onChange(applyDeptHeadToApproverRule(mainRule, e.target.checked))}
        >
          同时抄送部门负责人
        </Checkbox>
      )}
      {deptHeadAddon && approverRuleHasDeptHead(current) && (
        <Text type="secondary" style={{ fontSize: 11 }}>
          部门负责人取自表单「部门/所在部门」；未填时取发起人所属部门。
        </Text>
      )}
    </Space>
  )
}
