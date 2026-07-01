import { useState, useEffect, useMemo, useRef } from 'react'
import { Modal, Select, Input, InputNumber, Button, Space, message, Typography } from 'antd'
import { PlusOutlined, DeleteOutlined, SwapOutlined } from '@ant-design/icons'
import { roleApi } from '@/api/user'
import client from '@/api/client'

const { Text, Link } = Typography

/* ------------------------------------------------------------------ types */

interface ConditionRow { field: string; operator: string; value: number | string | undefined }
interface ApproverRow { type: string; value: string }
interface EscalationRow { after_hours: number | undefined; action: string }

interface RoleOption { code: string; name: string }
interface UserOption { id: string; real_name: string }

interface FormData {
  biz_type: string
  name: string
  condition_json: string
  approver_rules_json: string
  approval_mode: string
  sla_hours: number | undefined
  escalation_json: string
}

interface Props {
  open: boolean
  editingId: string | null
  initialData: FormData
  onSave: (payload: Record<string, unknown>) => Promise<void>
  onCancel: () => void
}

/* ------------------------------------------------------------- constants */

interface FieldDef {
  value: string
  label: string
  type: 'number' | 'enum'
  options?: { value: string; label: string }[]
}

/**
 * Trigger-condition fields available per business type. Keep in sync with the
 * backend `_build_policy_context()` — every field here must be populated into
 * the match context there, or a configured condition can never match.
 */
const FIELD_CATALOG: Record<string, FieldDef[]> = {
  quote_version: [
    { value: 'amount', label: '金额', type: 'number' },
    { value: 'margin_rate', label: '毛利率', type: 'number' },
    { value: 'discount_total', label: '折扣金额', type: 'number' },
  ],
  contract_version: [
    { value: 'amount', label: '合同金额', type: 'number' },
    { value: 'risk_level', label: '风险等级', type: 'enum', options: [
      { value: 'L', label: '低' }, { value: 'M', label: '中' }, { value: 'H', label: '高' },
    ] },
  ],
  change_request: [
    { value: 'change_type', label: '变更类型', type: 'enum', options: [
      { value: 'requirement', label: '需求' }, { value: 'quote', label: '报价' },
      { value: 'contract', label: '合同' }, { value: 'delivery', label: '交付' },
    ] },
    { value: 'cost_impact', label: '成本影响', type: 'number' },
  ],
  service_ticket: [
    { value: 'priority', label: '优先级', type: 'enum', options: [
      { value: 'low', label: '低' }, { value: 'medium', label: '中' },
      { value: 'high', label: '高' }, { value: 'critical', label: '紧急' },
    ] },
    { value: 'type', label: '工单类型', type: 'enum', options: [
      { value: 'fault', label: '故障' }, { value: 'maintenance', label: '维保' },
      { value: 'training', label: '培训' }, { value: 'spare', label: '备件' },
      { value: 'upgrade', label: '升级' },
    ] },
  ],
  order: [
    { value: 'amount', label: '订单金额', type: 'number' },
  ],
  solution: [],
}

const NUMBER_OP_OPTIONS = [
  { value: 'gt', label: '大于' },
  { value: 'gte', label: '大于等于' },
  { value: 'lt', label: '小于' },
  { value: 'lte', label: '小于等于' },
  { value: 'eq', label: '等于' },
]

const ENUM_OP_OPTIONS = [
  { value: 'eq', label: '等于' },
  { value: 'ne', label: '不等于' },
]

const ALL_OPS = ['gt', 'gte', 'lt', 'lte', 'eq', 'ne']

function fieldsForBiz(bizType: string): FieldDef[] {
  return FIELD_CATALOG[bizType] || []
}

function getFieldDef(bizType: string, field: string): FieldDef | undefined {
  return fieldsForBiz(bizType).find(f => f.value === field)
}

function opsForField(def: FieldDef | undefined): { value: string; label: string }[] {
  return def?.type === 'enum' ? ENUM_OP_OPTIONS : NUMBER_OP_OPTIONS
}

const APPROVER_TYPE_OPTIONS = [
  { value: 'role', label: '按角色' },
  { value: 'user', label: '指定用户' },
  { value: 'department_leader', label: '部门领导' },
]

const ESCALATION_ACTION_OPTIONS = [
  { value: 'remind', label: '再次提醒' },
  { value: 'auto_approve', label: '自动通过' },
]

const BIZ_TYPE_OPTIONS = [
  { value: 'quote_version', label: '报价审批' },
  { value: 'contract_version', label: '合同审批' },
  { value: 'change_request', label: '变更审批' },
  { value: 'solution', label: '方案审批' },
  { value: 'service_ticket', label: '售后工单审批' },
  { value: 'order', label: '订单审批' },
]

const MODE_OPTIONS = [
  { value: 'sequential', label: '依次审批' },
  { value: 'parallel', label: '并行审批（全部通过）' },
  { value: 'any_one', label: '任一通过' },
]

/* ----------------------------------------------------------- serializers */

function conditionsToJson(rows: ConditionRow[]): Record<string, unknown> | null {
  if (rows.length === 0) return null
  const obj: Record<string, unknown> = {}
  for (const r of rows) {
    if (r.field && r.operator && r.value !== undefined) {
      obj[`${r.field}_${r.operator}`] = r.value
    }
  }
  return Object.keys(obj).length > 0 ? obj : null
}

function jsonToConditions(json: unknown): ConditionRow[] {
  if (!json || typeof json !== 'object' || Array.isArray(json)) return []
  const rows: ConditionRow[] = []
  for (const [key, val] of Object.entries(json as Record<string, unknown>)) {
    const lastUnderscore = key.lastIndexOf('_')
    if (lastUnderscore > 0) {
      const field = key.slice(0, lastUnderscore)
      const operator = key.slice(lastUnderscore + 1)
      if (ALL_OPS.includes(operator)) {
        const value = typeof val === 'number' || typeof val === 'string' ? val : undefined
        rows.push({ field, operator, value })
      }
    }
  }
  return rows
}

function approversToJson(rows: ApproverRow[]): unknown[] | null {
  const arr = rows.filter(r => r.type && (r.type === 'department_leader' || r.value))
    .map(r => r.type === 'department_leader' ? { type: r.type } : { type: r.type, value: r.value })
  return arr.length > 0 ? arr : null
}

function jsonToApprovers(json: unknown): ApproverRow[] {
  if (!Array.isArray(json)) return []
  return json.map((item: { type?: string; value?: string }) => ({
    type: item.type || '',
    value: item.value || '',
  }))
}

function escalationToJson(rows: EscalationRow[]): EscalationRow[] | null {
  const arr = rows.filter(r => r.after_hours !== undefined && r.action)
    .map(r => ({ after_hours: r.after_hours, action: r.action }))
  return arr.length > 0 ? arr : null
}

function jsonToEscalation(json: unknown): EscalationRow[] {
  if (!Array.isArray(json)) return []
  return json.map((item: { after_hours?: number; action?: string }) => ({
    after_hours: typeof item.after_hours === 'number' ? item.after_hours : undefined,
    action: item.action || 'remind',
  }))
}

/* --------------------------------------------------------------- helpers */

function safeParseJson(str: string): { ok: true; data: unknown } | { ok: false } {
  try { return { ok: true, data: JSON.parse(str) } } catch { return { ok: false } }
}

function Label({ children }: { children: React.ReactNode }) {
  return <label className="text-sm font-medium text-slate-700 mb-1 block">{children}</label>
}

/* --------------------------------------------------------- FlowPreview */

function FlowPreview({
  approverRows,
  approvalMode,
  roles,
  users,
}: {
  approverRows: ApproverRow[]
  approvalMode: string
  roles: RoleOption[]
  users: UserOption[]
}) {
  const resolvedNames = useMemo(() => {
    return approverRows.filter(r => r.type).map(r => {
      if (r.type === 'role') {
        const role = roles.find(ro => ro.code === r.value)
        return role ? role.name : r.value || '未选择'
      }
      if (r.type === 'user') {
        const user = users.find(u => u.id === r.value)
        return user ? user.real_name : r.value || '未选择'
      }
      if (r.type === 'department_leader') return '部门领导'
      return '未知'
    })
  }, [approverRows, roles, users])

  if (resolvedNames.length === 0) {
    return (
      <div className="mt-4 p-3 bg-slate-50 rounded-lg border border-slate-200">
        <Text type="secondary" className="text-sm">添加审批人后可预览审批流程</Text>
      </div>
    )
  }

  const isParallel = approvalMode === 'parallel' || approvalMode === 'any_one'

  return (
    <div className="mt-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
      <div className="text-sm font-medium text-slate-500 mb-3">流程预览</div>
      <div className="overflow-x-auto">
        {isParallel ? (
          /* Parallel / Any-one: fork-join layout */
          <div className="flex items-center gap-0 min-w-fit">
            {/* Start node */}
            <div className="flex-shrink-0 flex items-center justify-center w-14 h-7 rounded-full bg-blue-500 text-white text-sm font-bold">
              提交
            </div>
            {/* Fork arrow */}
            <div className="flex-shrink-0 w-6 flex items-center justify-center text-slate-400">
              <span className="text-sm">→</span>
            </div>
            {/* Parallel branch container */}
            <div className="flex-shrink-0 flex flex-col gap-1.5 border-l-2 border-r-2 border-blue-200 px-3 py-1.5 rounded-md bg-blue-50/50">
              {resolvedNames.map((name, i) => (
                <div key={i} className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
                  <span className="text-sm text-slate-700 whitespace-nowrap">{name}</span>
                </div>
              ))}
            </div>
            {/* Join arrow */}
            <div className="flex-shrink-0 w-6 flex items-center justify-center text-slate-400">
              <span className="text-sm">→</span>
            </div>
            {/* End node */}
            <div className="flex-shrink-0 flex flex-col items-center">
              <div className="flex items-center justify-center w-14 h-7 rounded-full bg-emerald-500 text-white text-sm font-bold">
                完成
              </div>
              <span className="text-[10px] text-slate-400 mt-0.5">
                {approvalMode === 'parallel' ? '全部通过' : '任一通过'}
              </span>
            </div>
          </div>
        ) : (
          /* Sequential: linear chain */
          <div className="flex items-center gap-0 min-w-fit">
            <div className="flex-shrink-0 flex items-center justify-center w-14 h-7 rounded-full bg-blue-500 text-white text-sm font-bold">
              提交
            </div>
            {resolvedNames.map((name, i) => (
              <div key={i} className="flex items-center gap-0 flex-shrink-0">
                <div className="w-6 flex items-center justify-center text-slate-400">
                  <span className="text-sm">→</span>
                </div>
                <div className="flex items-center gap-1.5 px-3 h-7 rounded-full bg-amber-100 border border-amber-300 text-sm text-slate-700 whitespace-nowrap">
                  <div className="w-2 h-2 rounded-full bg-amber-400 flex-shrink-0" />
                  {name}
                </div>
              </div>
            ))}
            <div className="w-6 flex items-center justify-center text-slate-400 flex-shrink-0">
              <span className="text-sm">→</span>
            </div>
            <div className="flex-shrink-0 flex items-center justify-center w-14 h-7 rounded-full bg-emerald-500 text-white text-sm font-bold">
              完成
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/* ============================================================ Component */

export default function ApprovalPolicyModal({ open, editingId, initialData, onSave, onCancel }: Props) {
  const [jsonMode, setJsonMode] = useState(false)

  // Basic fields
  const [bizType, setBizType] = useState(initialData.biz_type)
  const [name, setName] = useState(initialData.name)
  const [approvalMode, setApprovalMode] = useState(initialData.approval_mode)
  const [slaHours, setSlaHours] = useState(initialData.sla_hours)

  // Structured rows
  const [conditionRows, setConditionRows] = useState<ConditionRow[]>([])
  const [approverRows, setApproverRows] = useState<ApproverRow[]>([])
  const [escalationRows, setEscalationRows] = useState<EscalationRow[]>([])

  // JSON text fields (for JSON mode)
  const [condJson, setCondJson] = useState(initialData.condition_json)
  const [rulesJson, setRulesJson] = useState(initialData.approver_rules_json)
  const [escJson, setEscJson] = useState(initialData.escalation_json)

  // Option data
  const [roles, setRoles] = useState<RoleOption[]>([])
  const [users, setUsers] = useState<UserOption[]>([])
  const [saving, setSaving] = useState(false)

  const [userSearching, setUserSearching] = useState(false)
  const userSearchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 拉取用户（支持后端关键字搜索）；结果按 id 去重并入 users，避免已选用户回显丢失
  const fetchUsers = async (keyword?: string) => {
    try {
      const res = await client.get('/api/admin/v1/tenant/users', {
        params: { pageNo: 1, pageSize: 50, ...(keyword ? { keyword } : {}) },
      }) as { data: { items?: { id: string; real_name?: string; username: string }[] } }
      const list = res.data?.items || []
      const mapped = list.map((u) => ({ id: u.id, real_name: u.real_name || u.username }))
      setUsers((prev) => {
        const seen = new Map(prev.map((u) => [u.id, u]))
        mapped.forEach((u) => seen.set(u.id, u))
        return Array.from(seen.values())
      })
    } catch { /* keep existing options on error */ }
  }

  // 输入时防抖调用后端搜索（原来仅前端过滤已加载的 20 条，用户多时搜不到，#83）
  const handleUserSearch = (keyword: string) => {
    if (userSearchTimer.current) clearTimeout(userSearchTimer.current)
    setUserSearching(true)
    userSearchTimer.current = setTimeout(async () => {
      await fetchUsers(keyword.trim() || undefined)
      setUserSearching(false)
    }, 350)
  }

  // Load options when modal opens
  useEffect(() => {
    if (!open) return
    roleApi.list().then((res: { data: { code: string; name: string }[] }) => {
      const list = res.data || []
      setRoles(list.map((r) => ({ code: r.code, name: r.name })))
    }).catch(() => setRoles([]))

    fetchUsers()
  }, [open])

  // Sync initial data into state when modal opens / data changes
  useEffect(() => {
    if (!open) return
    setBizType(initialData.biz_type)
    setName(initialData.name)
    setApprovalMode(initialData.approval_mode)
    setSlaHours(initialData.sla_hours)
    setCondJson(initialData.condition_json)
    setRulesJson(initialData.approver_rules_json)
    setEscJson(initialData.escalation_json)
    setJsonMode(false)

    // Parse into structured rows
    const condParsed = initialData.condition_json ? safeParseJson(initialData.condition_json) : null
    setConditionRows(condParsed?.ok ? jsonToConditions(condParsed.data) : [])

    const rulesParsed = initialData.approver_rules_json ? safeParseJson(initialData.approver_rules_json) : null
    setApproverRows(rulesParsed?.ok ? jsonToApprovers(rulesParsed.data) : [])

    const escParsed = initialData.escalation_json ? safeParseJson(initialData.escalation_json) : null
    setEscalationRows(escParsed?.ok ? jsonToEscalation(escParsed.data) : [])
  }, [open, initialData])

  /* ----------- mode switching ----------- */

  const switchToJson = () => {
    setCondJson(JSON.stringify(conditionsToJson(conditionRows) || {}, null, 2))
    setRulesJson(JSON.stringify(approversToJson(approverRows) || [], null, 2))
    setEscJson(JSON.stringify(escalationToJson(escalationRows) || [], null, 2))
    setJsonMode(true)
  }

  const switchToVisual = () => {
    const cp = safeParseJson(condJson)
    const rp = safeParseJson(rulesJson)
    const ep = safeParseJson(escJson)
    if (condJson && !cp.ok) { message.warning('条件JSON解析失败，无法切换到可视化模式'); return }
    if (rulesJson && !rp.ok) { message.warning('审批人JSON解析失败，无法切换到可视化模式'); return }
    if (escJson && !ep.ok) { message.warning('升级链JSON解析失败，无法切换到可视化模式'); return }
    setConditionRows(cp?.ok ? jsonToConditions(cp.data) : [])
    setApproverRows(rp?.ok ? jsonToApprovers(rp.data) : [])
    setEscalationRows(ep?.ok ? jsonToEscalation(ep.data) : [])
    setJsonMode(false)
  }

  /* ----------- save ----------- */

  const handleSave = async () => {
    let condValue: unknown = null
    let rulesValue: unknown = null
    let escValue: unknown = null

    if (jsonMode) {
      if (condJson) {
        const p = safeParseJson(condJson)
        if (!p.ok) { message.error('条件JSON格式错误'); return }
        condValue = p.data
      }
      if (rulesJson) {
        const p = safeParseJson(rulesJson)
        if (!p.ok) { message.error('审批人规则JSON格式错误'); return }
        rulesValue = p.data
      }
      if (escJson) {
        const p = safeParseJson(escJson)
        if (!p.ok) { message.error('升级链JSON格式错误'); return }
        escValue = p.data
      }
    } else {
      condValue = conditionsToJson(conditionRows)
      rulesValue = approversToJson(approverRows)
      escValue = escalationToJson(escalationRows)
    }

    setSaving(true)
    try {
      await onSave({
        biz_type: bizType,
        name,
        condition_json: condValue,
        approver_rules_json: rulesValue,
        approval_mode: approvalMode,
        sla_hours: slaHours,
        escalation_json: escValue,
      })
    } finally {
      setSaving(false)
    }
  }

  /* ----------- condition row ops ----------- */

  const addCondition = () => {
    const fields = fieldsForBiz(bizType)
    if (fields.length === 0) return
    const first = fields[0]
    setConditionRows([...conditionRows, {
      field: first.value,
      operator: first.type === 'enum' ? 'eq' : 'gt',
      value: undefined,
    }])
  }
  const removeCondition = (i: number) => setConditionRows(conditionRows.filter((_, idx) => idx !== i))
  const updateCondition = (i: number, patch: Partial<ConditionRow>) => {
    setConditionRows(conditionRows.map((r, idx) => idx === i ? { ...r, ...patch } : r))
  }
  // Fields differ per business type, so drop conditions that no longer apply.
  const handleBizTypeChange = (v: string) => {
    setBizType(v)
    setConditionRows([])
  }

  /* ----------- approver row ops ----------- */

  const addApprover = () => setApproverRows([...approverRows, { type: 'role', value: '' }])
  const removeApprover = (i: number) => setApproverRows(approverRows.filter((_, idx) => idx !== i))
  const updateApprover = (i: number, patch: Partial<ApproverRow>) => {
    setApproverRows(approverRows.map((r, idx) => idx === i ? { ...r, ...patch } : r))
  }

  /* ----------- escalation row ops ----------- */

  const addEscalation = () => setEscalationRows([...escalationRows, { after_hours: 24, action: 'remind' }])
  const removeEscalation = (i: number) => setEscalationRows(escalationRows.filter((_, idx) => idx !== i))
  const updateEscalation = (i: number, patch: Partial<EscalationRow>) => {
    setEscalationRows(escalationRows.map((r, idx) => idx === i ? { ...r, ...patch } : r))
  }

  /* ------------------------------------------------------------- render */

  return (
    <Modal
      title={editingId ? '编辑审批策略' : '新增审批策略'}
      open={open}
      onOk={handleSave}
      onCancel={onCancel}
      confirmLoading={saving}
      width={680}
      destroyOnClose
    >
      {/* Mode toggle */}
      <div className="flex justify-end mb-2">
        <Link onClick={jsonMode ? switchToVisual : switchToJson} className="text-sm flex items-center gap-1">
          <SwapOutlined />
          {jsonMode ? '切换到可视化编辑' : '切换到JSON模式'}
        </Link>
      </div>

      <div className="space-y-4">
        {/* Basic fields — always shown */}
        <div>
          <Label>业务类型</Label>
          <Select className="w-full" value={bizType} onChange={handleBizTypeChange} options={BIZ_TYPE_OPTIONS} />
        </div>
        <div>
          <Label>策略名称</Label>
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="高金额报价审批" />
        </div>

        {jsonMode ? (
          /* ========================== JSON Mode ========================== */
          <>
            <div>
              <Label>触发条件 (JSON)</Label>
              <Input.TextArea rows={3} value={condJson} onChange={e => setCondJson(e.target.value)}
                placeholder='{"amount_gt": 100000, "margin_rate_lt": 0.25}' />
            </div>
            <div>
              <Label>审批人规则 (JSON)</Label>
              <Input.TextArea rows={3} value={rulesJson} onChange={e => setRulesJson(e.target.value)}
                placeholder='[{"type":"role","value":"admin"}]' />
            </div>
          </>
        ) : (
          /* ======================== Visual Mode ========================= */
          <>
            {/* --- Condition Builder --- */}
            <div>
              <Label>触发条件</Label>
              {fieldsForBiz(bizType).length === 0 ? (
                <div className="text-sm text-slate-400">该业务类型暂无可配置的触发字段，审批将对所有提交生效</div>
              ) : (
                <>
                  {conditionRows.map((row, i) => {
                    const def = getFieldDef(bizType, row.field)
                    return (
                      <div key={i} className="flex items-center gap-2 mb-2">
                        <Select className="w-32" value={row.field}
                          onChange={v => {
                            const newDef = getFieldDef(bizType, v)
                            const validOps = opsForField(newDef).map(o => o.value)
                            const nextOp = validOps.includes(row.operator) ? row.operator : validOps[0]
                            updateCondition(i, { field: v, operator: nextOp, value: undefined })
                          }}
                          options={fieldsForBiz(bizType).map(f => ({ value: f.value, label: f.label }))} />
                        <Select className="w-24" value={row.operator}
                          onChange={v => updateCondition(i, { operator: v })}
                          options={opsForField(def)} />
                        {def?.type === 'enum' ? (
                          <Select className="w-40" value={typeof row.value === 'string' ? row.value : undefined}
                            onChange={v => updateCondition(i, { value: v })}
                            placeholder="值" options={def.options} />
                        ) : (
                          <InputNumber className="w-32" value={typeof row.value === 'number' ? row.value : undefined}
                            onChange={v => updateCondition(i, { value: v ?? undefined })} placeholder="值" />
                        )}
                        <Button type="text" danger icon={<DeleteOutlined />} size="small" onClick={() => removeCondition(i)} />
                      </div>
                    )
                  })}
                  <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={addCondition}>
                    添加条件
                  </Button>
                  {conditionRows.length === 0 && (
                    <div className="text-sm text-slate-400 mt-1">未设置条件，表示所有情况都匹配</div>
                  )}
                </>
              )}
            </div>

            {/* --- Approver Rules Builder --- */}
            <div>
              <Label>审批人规则</Label>
              {approverRows.map((row, i) => (
                <div key={i} className="flex items-center gap-2 mb-2">
                  <Select className="w-28" value={row.type} onChange={v => updateApprover(i, { type: v, value: '' })}
                    options={APPROVER_TYPE_OPTIONS} />
                  {row.type === 'role' && (
                    <Select className="flex-1" value={row.value || undefined} onChange={v => updateApprover(i, { value: v })}
                      placeholder="选择角色" showSearch optionFilterProp="label"
                      options={roles.map(r => ({ value: r.code, label: r.name }))} />
                  )}
                  {row.type === 'user' && (
                    <Select className="flex-1" value={row.value || undefined} onChange={v => updateApprover(i, { value: v })}
                      placeholder="输入姓名/用户名搜索" showSearch filterOption={false}
                      onSearch={handleUserSearch} loading={userSearching} notFoundContent={userSearching ? '搜索中...' : '无匹配用户'}
                      options={users.map(u => ({ value: u.id, label: u.real_name }))} />
                  )}
                  {row.type === 'department_leader' && (
                    <Text type="secondary" className="flex-1 text-sm">自动解析提交人的部门领导</Text>
                  )}
                  <Button type="text" danger icon={<DeleteOutlined />} size="small" onClick={() => removeApprover(i)} />
                </div>
              ))}
              <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={addApprover}>
                添加审批人
              </Button>
            </div>
          </>
        )}

        {/* Approval mode & SLA — always shown */}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Label>审批模式</Label>
            <Select className="w-full" value={approvalMode} onChange={setApprovalMode} options={MODE_OPTIONS} />
          </div>
          <div>
            <Label>SLA (小时)</Label>
            <InputNumber className="w-full" value={slaHours} onChange={v => setSlaHours(v || undefined)}
              min={1} placeholder="无限制" />
          </div>
        </div>

        {/* Escalation */}
        {jsonMode ? (
          <div>
            <Label>SLA 升级链 (JSON, 选填)</Label>
            <Input.TextArea rows={3} value={escJson} onChange={e => setEscJson(e.target.value)}
              placeholder='[{"after_hours":24,"action":"remind"}]' />
          </div>
        ) : (
          <div>
            <Label>SLA 升级链</Label>
            {escalationRows.map((row, i) => (
              <div key={i} className="flex items-center gap-2 mb-2">
                <Text className="text-sm whitespace-nowrap">超过</Text>
                <InputNumber className="w-20" value={row.after_hours} onChange={v => updateEscalation(i, { after_hours: v ?? undefined })}
                  min={1} placeholder="小时" />
                <Text className="text-sm whitespace-nowrap">小时后</Text>
                <Select className="w-28" value={row.action} onChange={v => updateEscalation(i, { action: v })}
                  options={ESCALATION_ACTION_OPTIONS} />
                <Button type="text" danger icon={<DeleteOutlined />} size="small" onClick={() => removeEscalation(i)} />
              </div>
            ))}
            <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={addEscalation}>
              添加升级步骤
            </Button>
          </div>
        )}

        {/* Flow Preview — only in visual mode */}
        {!jsonMode && (
          <FlowPreview
            approverRows={approverRows}
            approvalMode={approvalMode}
            roles={roles}
            users={users}
          />
        )}
      </div>
    </Modal>
  )
}
