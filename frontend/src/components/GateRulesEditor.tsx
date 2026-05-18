import { Button, Input, InputNumber, Select, Space, Tooltip } from 'antd'
import { PlusOutlined, DeleteOutlined, InfoCircleOutlined } from '@ant-design/icons'

export interface GateRule {
  code: string
  name: string
  message: string
  check: string
  field?: string
  entity?: string
  min_value?: number
  fix_action?: string
}

// Check types align with backend app/domains/project/service.py check_gate_rules()
const CHECK_TYPES: { value: string; label: string; desc: string }[] = [
  { value: 'field_required', label: '字段必填', desc: '商机的指定字段不能为空' },
  { value: 'json_not_empty', label: 'JSON 字段非空', desc: '商机的指定 JSON 字段必须有内容' },
  { value: 'has_related', label: '存在关联记录', desc: '商机下必须存在指定类型的关联记录' },
  { value: 'has_approved_solution', label: '存在已批方案', desc: '商机下必须有 status=approved 的方案' },
  { value: 'has_attachment', label: '已上传附件', desc: '商机下必须有至少一个附件' },
  { value: 'min_amount', label: '预期金额下限', desc: '商机预期金额必须高于设定值' },
]

// Fields on OpportunityProject usable in field_required / json_not_empty
const SCALAR_FIELDS = [
  { value: 'customer_id', label: '关联客户 (customer_id)' },
  { value: 'amount_expect', label: '预期金额 (amount_expect)' },
  { value: 'probability', label: '赢单概率 (probability)' },
  { value: 'close_date_expect', label: '预计成交日期 (close_date_expect)' },
  { value: 'risk_level', label: '风险等级 (risk_level)' },
  { value: 'owner_id', label: '负责人 (owner_id)' },
]

const JSON_FIELDS = [
  { value: 'competitors_json', label: '竞争对手 (competitors_json)' },
  { value: 'key_requirements_json', label: '关键需求 (key_requirements_json)' },
  { value: 'custom_fields_json', label: '自定义字段 (custom_fields_json)' },
]

const ENTITY_TYPES = [
  { value: 'solution', label: '方案 (solution)' },
  { value: 'quote', label: '报价 (quote)' },
  { value: 'contract', label: '合同 (contract)' },
]

interface Props {
  value: GateRule[]
  onChange: (rules: GateRule[]) => void
}

export default function GateRulesEditor({ value, onChange }: Props) {
  const rules = Array.isArray(value) ? value : []

  const update = (idx: number, patch: Partial<GateRule>) => {
    const next = rules.map((r, i) => (i === idx ? { ...r, ...patch } : r))
    onChange(next)
  }

  const remove = (idx: number) => onChange(rules.filter((_, i) => i !== idx))

  const add = () => onChange([
    ...rules,
    { code: '', name: '', message: '', check: 'field_required' },
  ])

  return (
    <div className="space-y-3">
      {rules.length === 0 && (
        <div className="text-center text-sm text-slate-400 py-6 bg-slate-50 rounded-lg border border-dashed border-slate-200">
          尚未配置任何 Gate 规则。该阶段将无门禁限制。
        </div>
      )}

      {rules.map((rule, idx) => {
        const checkCfg = CHECK_TYPES.find((c) => c.value === rule.check)
        return (
          <div key={idx} className="border border-slate-200 rounded-lg p-4 bg-white">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-primary/10 text-primary">规则 {idx + 1}</span>
                <span className="text-sm text-slate-500">{checkCfg?.label || rule.check}</span>
              </div>
              <Button danger size="small" type="text" icon={<DeleteOutlined />} onClick={() => remove(idx)} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">规则代码 *</label>
                <Input value={rule.code} placeholder="HAS_CUSTOMER"
                  onChange={(e) => update(idx, { code: e.target.value })} />
              </div>
              <div>
                <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">规则名称 *</label>
                <Input value={rule.name} placeholder="已关联客户"
                  onChange={(e) => update(idx, { name: e.target.value })} />
              </div>
              <div className="col-span-2">
                <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">
                  校验类型 *
                  {checkCfg && (
                    <Tooltip title={checkCfg.desc}>
                      <InfoCircleOutlined className="ml-1 text-slate-400" />
                    </Tooltip>
                  )}
                </label>
                <Select
                  className="w-full"
                  value={rule.check}
                  onChange={(v) => update(idx, { check: v, field: undefined, entity: undefined, min_value: undefined })}
                  options={CHECK_TYPES.map((c) => ({ label: c.label, value: c.value }))}
                />
              </div>

              {/* Conditional parameter row */}
              {rule.check === 'field_required' && (
                <div className="col-span-2">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">校验字段 *</label>
                  <Select
                    className="w-full"
                    value={rule.field}
                    placeholder="选择要校验的字段"
                    onChange={(v) => update(idx, { field: v })}
                    options={SCALAR_FIELDS}
                  />
                </div>
              )}

              {rule.check === 'json_not_empty' && (
                <div className="col-span-2">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">JSON 字段 *</label>
                  <Select
                    className="w-full"
                    value={rule.field}
                    placeholder="选择 JSON 字段"
                    onChange={(v) => update(idx, { field: v })}
                    options={JSON_FIELDS}
                  />
                </div>
              )}

              {rule.check === 'has_related' && (
                <div className="col-span-2">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">关联实体 *</label>
                  <Select
                    className="w-full"
                    value={rule.entity}
                    placeholder="选择必须存在的关联类型"
                    onChange={(v) => update(idx, { entity: v })}
                    options={ENTITY_TYPES}
                  />
                </div>
              )}

              {rule.check === 'min_amount' && (
                <div className="col-span-2">
                  <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">金额下限 (¥)</label>
                  <InputNumber
                    className="w-full"
                    value={rule.min_value}
                    min={0}
                    placeholder="预期金额超过此值才允许推进"
                    onChange={(v) => update(idx, { min_value: v ?? undefined })}
                  />
                </div>
              )}

              <div className="col-span-2">
                <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">不通过提示 *</label>
                <Input value={rule.message} placeholder="请先关联客户后再推进阶段"
                  onChange={(e) => update(idx, { message: e.target.value })} />
              </div>

              <div className="col-span-2">
                <label className="text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-1 block">修复链接（选填）</label>
                <Input value={rule.fix_action} placeholder="/customers/new — 用户点击提示时可跳转的地址"
                  onChange={(e) => update(idx, { fix_action: e.target.value || undefined })} />
              </div>
            </div>
          </div>
        )
      })}

      <Button block icon={<PlusOutlined />} type="dashed" onClick={add}>
        添加规则
      </Button>
    </div>
  )
}

export function validateGateRules(rules: GateRule[]): string | null {
  for (let i = 0; i < rules.length; i++) {
    const r = rules[i]
    if (!r.code?.trim()) return `规则 ${i + 1}: 规则代码不能为空`
    if (!r.name?.trim()) return `规则 ${i + 1}: 规则名称不能为空`
    if (!r.message?.trim()) return `规则 ${i + 1}: 不通过提示不能为空`
    if (!r.check) return `规则 ${i + 1}: 必须选择校验类型`
    if ((r.check === 'field_required' || r.check === 'json_not_empty') && !r.field) {
      return `规则 ${i + 1}: 必须选择要校验的字段`
    }
    if (r.check === 'has_related' && !r.entity) {
      return `规则 ${i + 1}: 必须选择关联实体类型`
    }
  }
  // Code uniqueness
  const codes = rules.map((r) => r.code.trim())
  const dup = codes.find((c, i) => codes.indexOf(c) !== i)
  if (dup) return `规则代码重复: ${dup}`
  return null
}
