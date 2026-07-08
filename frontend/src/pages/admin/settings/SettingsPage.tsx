import { useState, useEffect } from 'react'
import { Tabs, Table, Button, Modal, Input, InputNumber, Select, Switch, Space, Progress, Tag, message } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, CloudDownloadOutlined, UploadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import DOMPurify from 'dompurify'
import { settingsApi } from '@/api/settings'
import { dashboardApi } from '@/api/dashboard'
import { roleApi } from '@/api/user'
import client from '@/api/client'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import ApprovalPolicyModal from './ApprovalPolicyModal'
import FileStorageTab from './FileStorageTab'
import UiSettingsTab from './UiSettingsTab'
import GateRulesEditor, { type GateRule, validateGateRules } from '@/components/GateRulesEditor'
import DataView from '@/components/DataView'

const sanitizeHtml = (html: string) => DOMPurify.sanitize(html, { ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'span', 'div', 'table', 'tr', 'td', 'th', 'thead', 'tbody', 'img', 'hr'], ALLOWED_ATTR: ['href', 'src', 'alt', 'class', 'style', 'target'] })

const { TextArea } = Input

// ---- Reusable visual editors (replace raw-JSON textareas) ----

// Editable list of plain strings — used for 自定义字段选项 / 合同关键条款 etc.
function StringListEditor({ value, onChange, placeholder, addText = '添加一项' }: {
  value: string[]; onChange: (v: string[]) => void; placeholder?: string; addText?: string
}) {
  const list = value || []
  return (
    <div className="space-y-2">
      {list.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input value={item} placeholder={placeholder}
            onChange={(e) => onChange(list.map((v, idx) => (idx === i ? e.target.value : v)))} />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(list.filter((_, idx) => idx !== i))} />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...list, ''])} block>{addText}</Button>
    </div>
  )
}

interface KvRow { k: string; v: string }
// Editable key/value pairs — used for 条款摘要 / 付款条款 / 交付条款 (stored as JSON objects).
function KeyValueEditor({ value, onChange, keyPlaceholder = '名称', valPlaceholder = '值', addText = '添加条款' }: {
  value: KvRow[]; onChange: (v: KvRow[]) => void; keyPlaceholder?: string; valPlaceholder?: string; addText?: string
}) {
  const rows = value || []
  return (
    <div className="space-y-2">
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input className="!w-1/3" value={row.k} placeholder={keyPlaceholder}
            onChange={(e) => onChange(rows.map((r, idx) => (idx === i ? { ...r, k: e.target.value } : r)))} />
          <Input className="flex-1" value={row.v} placeholder={valPlaceholder}
            onChange={(e) => onChange(rows.map((r, idx) => (idx === i ? { ...r, v: e.target.value } : r)))} />
          <Button type="text" danger icon={<DeleteOutlined />} onClick={() => onChange(rows.filter((_, idx) => idx !== i))} />
        </div>
      ))}
      <Button type="dashed" size="small" icon={<PlusOutlined />} onClick={() => onChange([...rows, { k: '', v: '' }])} block>{addText}</Button>
    </div>
  )
}

interface AuthFieldDef { key: string; label: string; placeholder?: string; secret?: boolean }
// Which credential inputs to render for an integration, by system / auth type — replaces the raw auth_config JSON textarea.
function getAuthFields(systemCode: string, authType: string): AuthFieldDef[] {
  if (systemCode === 'dingtalk') return [
    { key: 'app_key', label: '企业应用 AppKey', placeholder: '企业内部应用 AppKey' },
    { key: 'app_secret', label: '企业应用 AppSecret', placeholder: '企业内部应用 AppSecret', secret: true },
    { key: 'agent_id', label: '应用 AgentId', placeholder: '应用 AgentId' },
    { key: 'crm_base_url', label: 'CRM 访问地址', placeholder: 'https://192.168.0.42:8410' },
    { key: 'secret', label: '群机器人加签 Secret（可选）', placeholder: '加签 secret，可留空', secret: true },
  ]
  switch (authType) {
    case 'apikey': return [
      { key: 'api_key', label: 'API Key', placeholder: 'your-key', secret: true },
      { key: 'header_name', label: '请求头名称', placeholder: 'X-API-Key' },
    ]
    case 'basic': return [
      { key: 'username', label: '用户名', placeholder: 'user' },
      { key: 'password', label: '密码', placeholder: 'pass', secret: true },
    ]
    case 'oauth2': return [
      { key: 'token_url', label: 'Token URL', placeholder: 'https://...' },
      { key: 'client_id', label: 'Client ID', placeholder: 'xxx' },
      { key: 'client_secret', label: 'Client Secret', placeholder: 'xxx', secret: true },
    ]
    default: return []
  }
}

interface StageConfig { id: string; stage_code: string; name: string; gate_rules_json?: Record<string, unknown>[]; enabled: boolean }
interface MarginPolicy { id: string; policy_code: string; redline_rate: number; action: string; scope_json?: Record<string, unknown>; enabled: boolean }
interface AiPolicy { id: string; task_type: string; model_route_json?: Record<string, unknown>; budget_json?: Record<string, unknown>; enabled: boolean }
interface Integration { id: string; system_code: string; name: string; base_url: string; auth_type: string; auth_config_json?: Record<string, unknown>; status: string }
interface FeatureToggle { id: string; feature_code: string; enabled: boolean; config_json?: Record<string, unknown> }
interface AiBudget { id: string; period: string; budget_cost?: number; used_cost?: number; budget_tokens?: number; used_tokens?: number; hard_limit: boolean }
interface ApprovalPolicyItem { id: string; biz_type: string; name: string; condition_json?: Record<string, unknown>; approver_rules_json?: Record<string, unknown>; approval_mode: string; sla_hours?: number; escalation_json?: Record<string, unknown>[]; priority: number; enabled: boolean }
interface DocTemplateItem { id: string; doc_type: string; name: string; description?: string; content_json?: Record<string, unknown>; is_default: boolean; created_by_name?: string; created_at: string }
interface EmailTemplateItem { id: string; code: string; name: string; subject?: string; body_html?: string; variables_json?: unknown; enabled: boolean; created_at: string }
interface CustomFieldItem { id: string; entity_type: string; field_key: string; field_label: string; field_type: string; options_json?: string[]; required: boolean; sort_order: number; enabled: boolean }

function JsonCell({ value }: { value: unknown }) {
  if (!value) return <span className="text-slate-300">-</span>
  return <div className="max-w-xs"><DataView value={value} /></div>
}

const APPROVER_TYPE_LABEL: Record<string, string> = { role: '角色', user: '用户', department_leader: '部门领导' }

// Friendly render of approver_rules_json: resolves role code / user id to names instead
// of dumping raw JSON (was unreadable in the policy list).
function ApproverRulesCell({ value, nameMap }: { value: unknown; nameMap: Record<string, string> }) {
  const rules = Array.isArray(value) ? value : value ? [value] : []
  if (rules.length === 0) return <span className="text-slate-300">-</span>
  return (
    <Space size={[4, 4]} wrap>
      {rules.map((r: any, i: number) => {
        if (r?.type === 'department_leader') return <Tag key={i} color="geekblue">部门领导</Tag>
        const label = APPROVER_TYPE_LABEL[r?.type] || r?.type || '?'
        const name = r?.value ? nameMap[r.value] || r.value : '未指定'
        return <Tag key={i} color="blue">{label}: {name}</Tag>
      })}
    </Space>
  )
}

export default function SettingsPage() {
  usePageTitle('系统设置')
  const [stages, setStages] = useState<StageConfig[]>([])
  const [margins, setMargins] = useState<MarginPolicy[]>([])
  const [aiPolicies, setAiPolicies] = useState<AiPolicy[]>([])
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [features, setFeatures] = useState<FeatureToggle[]>([])
  const [aiBudget, setAiBudget] = useState<AiBudget | null>(null)
  const [budgetForm, setBudgetForm] = useState({ budget_cost: 100, budget_tokens: 10000000, hard_limit: false })
  const [budgetModal, setBudgetModal] = useState(false)
  const [approvalPolicies, setApprovalPolicies] = useState<ApprovalPolicyItem[]>([])
  const [approverNameMap, setApproverNameMap] = useState<Record<string, string>>({})
  const [docTemplates, setDocTemplates] = useState<DocTemplateItem[]>([])
  const [emailTemplates, setEmailTemplates] = useState<EmailTemplateItem[]>([])
  const [customFields, setCustomFields] = useState<CustomFieldItem[]>([])
  const [backupStats, setBackupStats] = useState<Record<string, number>>({})
  const [backupLoading, setBackupLoading] = useState(false)
  const [auditResult, setAuditResult] = useState<{ total_checked: number; no_hash: number; tampered_count: number; tampered: { id: string; created_at: string; summary: string }[] } | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  // Custom field
  const [cfModal, setCfModal] = useState(false)
  const [cfEditingId, setCfEditingId] = useState<string | null>(null)
  const defaultCfForm = { entity_type: 'customer', field_key: '', field_label: '', field_type: 'text', options_json: [] as string[], required: false, sort_order: 0, enabled: true }
  const [cfForm, setCfForm] = useState(defaultCfForm)

  // Doc template
  const [dtModal, setDtModal] = useState(false)
  const [dtEditingId, setDtEditingId] = useState<string | null>(null)
  const defaultDtForm = {
    doc_type: 'quote' as string, name: '', description: '', is_default: false,
    title: '',
    tax_rate: 0.13 as number | null,
    validity_days: 30 as number | null,
    terms: [] as KvRow[],            // quote: terms_summary_json
    lines: [] as { item_name: string; qty: number; unit: string; unit_price: number }[],
    payment_terms: [] as KvRow[],    // contract: payment_terms_json
    delivery_terms: [] as KvRow[],   // contract: delivery_terms_json
    key_clauses: [] as string[],     // contract: key_clauses_json
  }
  const [dtForm, setDtForm] = useState(defaultDtForm)

  // Email template
  const [etModal, setEtModal] = useState(false)
  const [etEditingId, setEtEditingId] = useState<string | null>(null)
  const defaultEtForm = { code: '', name: '', subject: '', body_html: '', variables_json: [] as { name: string; label: string }[], enabled: true }
  const [etForm, setEtForm] = useState(defaultEtForm)

  // Stage edit
  const [stageModal, setStageModal] = useState(false)
  const [stageForm, setStageForm] = useState<{ stage_code: string; name: string; gate_rules: GateRule[] }>({ stage_code: '', name: '', gate_rules: [] })

  // Margin create
  const [marginModal, setMarginModal] = useState(false)
  const [marginForm, setMarginForm] = useState({ policy_code: '', redline_rate: 0.2, action: 'warn' })

  // Integration create/edit
  const [intModal, setIntModal] = useState(false)
  const [intEditingId, setIntEditingId] = useState<string | null>(null)
  const defaultIntForm = { system_code: '', name: '', base_url: '', auth_type: 'apikey', auth_config_json: {} as Record<string, string>, status: 'active' }
  const [intForm, setIntForm] = useState(defaultIntForm)

  // Notification templates
  const [ntTemplates, setNtTemplates] = useState<{ id: string; event_type: string; title_template: string; content_template?: string; is_active: boolean }[]>([])
  const [ntVariables, setNtVariables] = useState<{ key: string; label: string }[]>([])
  const [ntModal, setNtModal] = useState(false)
  const [ntEditingId, setNtEditingId] = useState<string | null>(null)
  const [ntForm, setNtForm] = useState({ event_type: '', title_template: '', content_template: '', is_active: true })

  // Approval policy create/edit
  const [apModal, setApModal] = useState(false)
  const [apEditingId, setApEditingId] = useState<string | null>(null)
  const defaultApForm = { biz_type: 'quote_version', name: '', condition_json: '', approver_rules_json: '', approval_mode: 'sequential', sla_hours: undefined as number | undefined, escalation_json: '' }
  const [apForm, setApForm] = useState(defaultApForm)

  // Pool rules
  const [poolRules, setPoolRules] = useState({ enabled: false, idle_days: { A: 90, B: 60, C: 30, D: 15 }, default_idle_days: 30 })
  const [poolSaving, setPoolSaving] = useState(false)

  const currentPeriod = new Date().toISOString().slice(0, 7)

  const fetchAll = () => {
    // Fire all requests in parallel for faster loading
    Promise.allSettled([
      settingsApi.listStages().then((r: { data: StageConfig[] }) => r.data && setStages(r.data)),
      settingsApi.listMargins().then((r: { data: MarginPolicy[] }) => r.data && setMargins(r.data)),
      settingsApi.listAiPolicies().then((r: { data: AiPolicy[] }) => r.data && setAiPolicies(r.data)),
      settingsApi.listIntegrations().then((r: { data: Integration[] }) => r.data && setIntegrations(r.data)),
      settingsApi.listFeatures().then((r: { data: FeatureToggle[] }) => r.data && setFeatures(r.data)),
      settingsApi.getAiBudget(currentPeriod).then((r: { data: AiBudget | null }) => r.data && setAiBudget(r.data)),
      settingsApi.listApprovalPolicies().then((r: { data: ApprovalPolicyItem[] }) => r.data && setApprovalPolicies(r.data)),
      settingsApi.listDocTemplates().then((r: { data: DocTemplateItem[] }) => r.data && setDocTemplates(r.data)),
      settingsApi.listEmailTemplates().then((r: { data: EmailTemplateItem[] }) => r.data && setEmailTemplates(r.data)),
      settingsApi.listCustomFields().then((r: { data: CustomFieldItem[] }) => r.data && setCustomFields(r.data)),
      settingsApi.backupStats().then((r: { data: Record<string, number> }) => r.data && setBackupStats(r.data)),
      settingsApi.getPoolRules().then((r: any) => { if (r.data && typeof r.data === 'object') setPoolRules({ enabled: false, idle_days: { A: 90, B: 60, C: 30, D: 15 }, default_idle_days: 30, ...r.data }) }),
      client.get('/api/v1/notification_templates').then((r: any) => {
        if (r.data) { setNtTemplates(r.data.items || []); setNtVariables(r.data.variables || []) }
      }),
    ])
  }

  const handleSaveBudget = async () => {
    try {
      await settingsApi.updateAiBudget({ period: currentPeriod, ...budgetForm })
      message.success('AI 预算已更新')
      setBudgetModal(false)
      fetchAll()
    } catch { message.error('更新预算失败') }
  }
  useEffect(() => { fetchAll() }, [])

  // Load role/user name maps once, to render approver rules readably.
  useEffect(() => {
    Promise.all([
      roleApi.list().catch(() => ({ data: [] as { code: string; name: string }[] })),
      client.get('/api/admin/v1/tenant/users').catch(() => ({ data: { items: [] as { id: string; real_name?: string; username: string }[] } })),
    ]).then(([rolesRes, usersRes]: any) => {
      const map: Record<string, string> = {}
      for (const r of rolesRes.data || []) map[r.code] = r.name
      for (const u of usersRes.data?.items || []) map[u.id] = u.real_name || u.username
      setApproverNameMap(map)
    })
  }, [])

  const handleSaveStage = async () => {
    const err = validateGateRules(stageForm.gate_rules)
    if (err) { message.error(err); return }
    try {
      await settingsApi.updateStage(stageForm.stage_code, {
        name: stageForm.name,
        gate_rules_json: stageForm.gate_rules.length > 0 ? stageForm.gate_rules : null,
      })
      message.success('阶段已保存')
      setStageModal(false)
      fetchAll()
    } catch {
      message.error('保存阶段失败')
    }
  }

  const handleCreateMargin = async () => {
    try {
      await settingsApi.createMargin(marginForm)
      message.success('红线策略已创建')
      setMarginModal(false)
      setMarginForm({ policy_code: '', redline_rate: 0.2, action: 'warn' })
      fetchAll()
    } catch {
      message.error('创建红线策略失败')
    }
  }

  const handleSaveInt = async () => {
    try {
      const payload: Record<string, unknown> = {
        system_code: intForm.system_code, name: intForm.name,
        base_url: intForm.base_url, auth_type: intForm.auth_type, status: intForm.status,
      }
      const cfg: Record<string, string> = {}
      Object.entries(intForm.auth_config_json || {}).forEach(([k, v]) => { if (v != null && String(v).trim()) cfg[k] = String(v).trim() })
      payload.auth_config_json = Object.keys(cfg).length ? cfg : null
      if (intEditingId) {
        await settingsApi.updateIntegration(intEditingId, payload)
        message.success('集成端点已更新')
      } else {
        await settingsApi.createIntegration(payload)
        message.success('集成端点已创建')
      }
      setIntModal(false)
      setIntEditingId(null)
      setIntForm(defaultIntForm)
      fetchAll()
    } catch {
      message.error(intEditingId ? '更新集成端点失败' : '创建集成端点失败')
    }
  }

  const handleSaveAp = async (payload: Record<string, unknown>) => {
    try {
      if (apEditingId) {
        await settingsApi.updateApprovalPolicy(apEditingId, payload)
        message.success('审批策略已更新')
      } else {
        await settingsApi.createApprovalPolicy(payload)
        message.success('审批策略已创建')
      }
      setApModal(false)
      setApEditingId(null)
      setApForm(defaultApForm)
      fetchAll()
    } catch { message.error(apEditingId ? '更新审批策略失败' : '创建审批策略失败') }
  }

  const kvToObj = (rows: KvRow[]) => rows.reduce((o, { k, v }) => { if (k.trim()) o[k.trim()] = v; return o }, {} as Record<string, string>)
  const dtUpdateLine = (i: number, field: 'item_name' | 'unit', val: string) =>
    setDtForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, [field]: val } : l)) }))
  const dtUpdateLineNum = (i: number, field: 'qty' | 'unit_price', val: number) =>
    setDtForm((f) => ({ ...f, lines: f.lines.map((l, idx) => (idx === i ? { ...l, [field]: val } : l)) }))

  const handleSaveDt = async () => {
    if (!dtForm.name.trim()) { message.error('请填写模板名称'); return }
    let contentJson: Record<string, unknown>
    if (dtForm.doc_type === 'quote') {
      const terms = kvToObj(dtForm.terms)
      contentJson = {
        title: dtForm.title || undefined,
        tax_rate: dtForm.tax_rate ?? undefined,
        validity_days: dtForm.validity_days ?? undefined,
        ...(Object.keys(terms).length ? { terms_summary_json: terms } : {}),
        lines: (dtForm.lines || []).filter((l) => l.item_name.trim())
          .map((l) => ({ item_name: l.item_name.trim(), qty: l.qty, unit: l.unit, unit_price: l.unit_price })),
      }
    } else {
      const pay = kvToObj(dtForm.payment_terms)
      const del = kvToObj(dtForm.delivery_terms)
      const clauses = (dtForm.key_clauses || []).map((c) => c.trim()).filter(Boolean)
      contentJson = {
        title: dtForm.title || undefined,
        ...(Object.keys(pay).length ? { payment_terms_json: pay } : {}),
        ...(Object.keys(del).length ? { delivery_terms_json: del } : {}),
        ...(clauses.length ? { key_clauses_json: clauses } : {}),
      }
    }
    try {
      const payload = { doc_type: dtForm.doc_type, name: dtForm.name, description: dtForm.description || undefined, content_json: contentJson, is_default: dtForm.is_default }
      if (dtEditingId) {
        await settingsApi.updateDocTemplate(dtEditingId, payload)
        message.success('模板已更新')
      } else {
        await settingsApi.createDocTemplate(payload)
        message.success('模板已创建')
      }
      setDtModal(false); setDtEditingId(null); setDtForm(defaultDtForm); fetchAll()
    } catch { message.error('保存模板失败') }
  }

  const handleSaveEt = async () => {
    try {
      const vars = (etForm.variables_json || [])
        .filter((v) => v.name.trim())
        .map((v) => ({ name: v.name.trim(), label: v.label.trim() }))
      const payload = { code: etForm.code, name: etForm.name, subject: etForm.subject || undefined, body_html: etForm.body_html || undefined, variables_json: vars.length ? vars : null, enabled: etForm.enabled }
      if (etEditingId) {
        await settingsApi.updateEmailTemplate(etEditingId, payload)
        message.success('邮件模板已更新')
      } else {
        await settingsApi.createEmailTemplate(payload)
        message.success('邮件模板已创建')
      }
      setEtModal(false); setEtEditingId(null); setEtForm(defaultEtForm); fetchAll()
    } catch { message.error('保存邮件模板失败') }
  }

  const handleSaveCf = async () => {
    try {
      const opts = (cfForm.options_json || []).map((o) => o.trim()).filter(Boolean)
      if ((cfForm.field_type === 'select' || cfForm.field_type === 'multiselect') && opts.length === 0) {
        message.error('单选/多选字段请至少添加一个选项'); return
      }
      const payload = { ...cfForm, options_json: opts.length ? opts : null }
      if (cfEditingId) {
        await settingsApi.updateCustomField(cfEditingId, payload)
        message.success('自定义字段已更新')
      } else {
        await settingsApi.createCustomField(payload)
        message.success('自定义字段已创建')
      }
      setCfModal(false); setCfEditingId(null); setCfForm(defaultCfForm); fetchAll()
    } catch { message.error('保存自定义字段失败') }
  }

  const entityTypeLabels: Record<string, string> = {
    customer: '客户', project: '商机', lead: '线索', contact: '联系人', service_ticket: '工单',
  }
  const fieldTypeLabels: Record<string, string> = {
    text: '文本', number: '数字', date: '日期', select: '单选', multiselect: '多选', boolean: '开关',
  }

  const openApEdit = (r: ApprovalPolicyItem) => {
    setApEditingId(r.id)
    setApForm({
      biz_type: r.biz_type,
      name: r.name || '',
      condition_json: r.condition_json ? JSON.stringify(r.condition_json, null, 2) : '',
      approver_rules_json: r.approver_rules_json ? JSON.stringify(r.approver_rules_json, null, 2) : '',
      approval_mode: r.approval_mode || 'sequential',
      sla_hours: r.sla_hours,
      escalation_json: r.escalation_json ? JSON.stringify(r.escalation_json, null, 2) : '',
    })
    setApModal(true)
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">系统配置</h1>
        <p className="text-sm text-slate-500 mt-1">管理阶段Gate、毛利红线、审批策略、AI策略、集成端点和功能开关</p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <Tabs className="px-6 pt-2" items={[
          {
            key: 'stages', label: '阶段Gate',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-3">
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
                    setStageForm({ stage_code: '', name: '', gate_rules: [] }); setStageModal(true)
                  }}>配置阶段</Button>
                </div>
                <Table rowKey="id" dataSource={stages} size="small" pagination={false} columns={[
                  { title: '阶段', dataIndex: 'stage_code', width: 80, render: (v: string) => <span className="font-mono font-bold text-primary">{v}</span> },
                  { title: '名称', dataIndex: 'name', width: 120 },
                  { title: 'Gate规则', dataIndex: 'gate_rules_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '启用', dataIndex: 'enabled', width: 80, render: (v: boolean) => v ? <span className="text-emerald-500 font-bold">是</span> : <span className="text-slate-400">否</span> },
                  { title: '', width: 80, render: (_: unknown, r: StageConfig) => (
                    <a className="text-primary text-sm font-bold" onClick={() => {
                      const rules = Array.isArray(r.gate_rules_json) ? (r.gate_rules_json as unknown as GateRule[]) : []
                      setStageForm({ stage_code: r.stage_code, name: r.name, gate_rules: rules })
                      setStageModal(true)
                    }}>编辑</a>
                  )},
                ]} />
              </div>
            ),
          },
          {
            key: 'ui_settings', label: '界面设置',
            children: <UiSettingsTab />,
          },
          {
            key: 'margin', label: '毛利红线',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-3">
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setMarginModal(true)}>新增红线</Button>
                </div>
                <Table rowKey="id" dataSource={margins} size="small" pagination={false} columns={[
                  { title: '策略编码', dataIndex: 'policy_code', width: 150 },
                  { title: '红线比例', dataIndex: 'redline_rate', width: 100, render: (v: number) => `${(v * 100).toFixed(1)}%` },
                  { title: '动作', dataIndex: 'action', width: 120, render: (v: string) => ({ block: '阻断', need_approval: '需审批', warn: '警告' }[v] || v) },
                  { title: '范围', dataIndex: 'scope_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '启用', dataIndex: 'enabled', width: 80, render: (v: boolean) => v ? '是' : '否' },
                ]} />
              </div>
            ),
          },
          {
            key: 'approval', label: '审批策略',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-3">
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => { setApEditingId(null); setApForm(defaultApForm); setApModal(true) }}>新增策略</Button>
                </div>
                <Table rowKey="id" dataSource={approvalPolicies} size="small" pagination={false} columns={[
                  { title: '业务类型', dataIndex: 'biz_type', width: 130, render: (v: string) => ({
                    quote_version: '报价审批', contract_version: '合同审批', change_request: '变更审批', solution: '方案审批',
                    service_ticket: '售后工单审批', order: '订单审批',
                  }[v] || v) },
                  { title: '策略名称', dataIndex: 'name', width: 150 },
                  { title: '触发条件', dataIndex: 'condition_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '审批人规则', dataIndex: 'approver_rules_json', render: (v: unknown) => <ApproverRulesCell value={v} nameMap={approverNameMap} /> },
                  { title: '模式', dataIndex: 'approval_mode', width: 80, render: (v: string) => ({
                    sequential: '依次', parallel: '并行', any_one: '任一',
                  }[v] || v) },
                  { title: 'SLA(时)', dataIndex: 'sla_hours', width: 70 },
                  { title: '升级链', dataIndex: 'escalation_json', width: 100, render: (v: unknown) => v ? <JsonCell value={v} /> : <span className="text-slate-300">-</span> },
                  { title: '启用', dataIndex: 'enabled', width: 60, render: (v: boolean, r: ApprovalPolicyItem) => (
                    <Switch size="small" checked={v} onChange={async (checked) => {
                      try {
                        await settingsApi.updateApprovalPolicy(r.id, { enabled: checked })
                        fetchAll()
                      } catch { message.error('更新失败') }
                    }} />
                  )},
                  { title: '', width: 100, render: (_: unknown, r: ApprovalPolicyItem) => (
                    <Space size="middle">
                      <a className="text-primary text-sm font-bold" onClick={() => openApEdit(r)}>编辑</a>
                      <a className={`text-rose-500 text-sm font-bold ${deletingId === r.id ? 'opacity-50 pointer-events-none' : ''}`} onClick={async () => {
                        setDeletingId(r.id)
                        try {
                          await settingsApi.deleteApprovalPolicy(r.id)
                          message.success('已删除')
                          fetchAll()
                        } catch { message.error('删除失败') }
                        finally { setDeletingId(null) }
                      }}>删除</a>
                    </Space>
                  )},
                ]} />
                {approvalPolicies.length === 0 && <div className="text-center py-8 text-slate-400 text-sm">暂无审批策略，点击"新增策略"创建</div>}
              </div>
            ),
          },
          {
            key: 'doc_templates', label: '文档模板',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-3">
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
                    setDtEditingId(null); setDtForm(defaultDtForm); setDtModal(true)
                  }}>新增模板</Button>
                </div>
                <Table rowKey="id" dataSource={docTemplates} size="small" pagination={false} columns={[
                  { title: '类型', dataIndex: 'doc_type', width: 80, render: (v: string) => v === 'quote' ? '报价' : '合同' },
                  { title: '名称', dataIndex: 'name', width: 180 },
                  { title: '说明', dataIndex: 'description', ellipsis: true },
                  { title: '默认', dataIndex: 'is_default', width: 60, render: (v: boolean) => v ? <span className="text-emerald-600 font-bold">是</span> : '-' },
                  { title: '创建人', dataIndex: 'created_by_name', width: 100 },
                  { title: '', width: 100, render: (_: unknown, r: DocTemplateItem) => (
                    <Space size="middle">
                      <a className="text-primary text-sm font-bold" onClick={() => {
                        setDtEditingId(r.id)
                        const c = (r.content_json || {}) as Record<string, any>
                        const objToKv = (o: any): KvRow[] => (o && typeof o === 'object' && !Array.isArray(o))
                          ? Object.entries(o).map(([k, v]) => ({ k, v: typeof v === 'string' ? v : JSON.stringify(v) })) : []
                        setDtForm({
                          doc_type: r.doc_type, name: r.name, description: r.description || '', is_default: r.is_default,
                          title: c.title || '',
                          tax_rate: typeof c.tax_rate === 'number' ? c.tax_rate : (r.doc_type === 'quote' ? 0.13 : null),
                          validity_days: typeof c.validity_days === 'number' ? c.validity_days : (r.doc_type === 'quote' ? 30 : null),
                          terms: objToKv(c.terms_summary_json),
                          lines: Array.isArray(c.lines) ? c.lines.map((l: any) => ({ item_name: l.item_name || '', qty: l.qty ?? 1, unit: l.unit || '', unit_price: l.unit_price ?? 0 })) : [],
                          payment_terms: objToKv(c.payment_terms_json),
                          delivery_terms: objToKv(c.delivery_terms_json),
                          key_clauses: Array.isArray(c.key_clauses_json) ? c.key_clauses_json.map((x: any) => String(x)) : [],
                        })
                        setDtModal(true)
                      }}>编辑</a>
                      <a className={`text-rose-500 text-sm font-bold ${deletingId === r.id ? 'opacity-50 pointer-events-none' : ''}`} onClick={async () => {
                        setDeletingId(r.id); try { await settingsApi.deleteDocTemplate(r.id); message.success('已删除'); fetchAll() } catch { message.error('删除失败') } finally { setDeletingId(null) }
                      }}>删除</a>
                    </Space>
                  )},
                ]} />
                {docTemplates.length === 0 && <div className="text-center py-8 text-slate-400 text-sm">暂无文档模板</div>}
              </div>
            ),
          },
          {
            key: 'email_templates', label: '邮件模板',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-3">
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
                    setEtEditingId(null); setEtForm(defaultEtForm); setEtModal(true)
                  }}>新增模板</Button>
                </div>
                <Table rowKey="id" dataSource={emailTemplates} size="small" pagination={false} columns={[
                  { title: '编码', dataIndex: 'code', width: 140, render: (v: string) => <span className="font-mono text-sm">{v}</span> },
                  { title: '名称', dataIndex: 'name', width: 160 },
                  { title: '主题', dataIndex: 'subject', ellipsis: true },
                  { title: '启用', dataIndex: 'enabled', width: 60, render: (v: boolean, r: EmailTemplateItem) => (
                    <Switch size="small" checked={v} onChange={async (checked) => {
                      try { await settingsApi.updateEmailTemplate(r.id, { code: r.code, name: r.name, enabled: checked }); fetchAll() } catch { message.error('更新失败') }
                    }} />
                  )},
                  { title: '', width: 100, render: (_: unknown, r: EmailTemplateItem) => (
                    <Space size="middle">
                      <a className="text-primary text-sm font-bold" onClick={() => {
                        setEtEditingId(r.id)
                        setEtForm({ code: r.code, name: r.name, subject: r.subject || '',
                          body_html: r.body_html || '',
                          variables_json: Array.isArray(r.variables_json)
                            ? (r.variables_json as { name: string; label: string }[]).map((v) => ({ name: v.name || '', label: v.label || '' }))
                            : [],
                          enabled: r.enabled })
                        setEtModal(true)
                      }}>编辑</a>
                      <a className={`text-rose-500 text-sm font-bold ${deletingId === r.id ? 'opacity-50 pointer-events-none' : ''}`} onClick={async () => {
                        setDeletingId(r.id); try { await settingsApi.deleteEmailTemplate(r.id); message.success('已删除'); fetchAll() } catch { message.error('删除失败') } finally { setDeletingId(null) }
                      }}>删除</a>
                    </Space>
                  )},
                ]} />
                {emailTemplates.length === 0 && <div className="text-center py-8 text-slate-400 text-sm">暂无邮件模板</div>}
              </div>
            ),
          },
          {
            key: 'notification_templates', label: '通知模板',
            children: (
              <div className="pb-6">
                <div className="flex justify-between mb-3">
                  <div className="text-sm text-slate-400">
                    可用变量: {ntVariables.map(v => <Tag key={v.key} className="text-[12px]">{`{{${v.key}}}`} {v.label}</Tag>)}
                  </div>
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
                    setNtEditingId(null); setNtForm({ event_type: '', title_template: '', content_template: '', is_active: true }); setNtModal(true)
                  }}>新增模板</Button>
                </div>
                <Table rowKey="id" dataSource={ntTemplates} size="small" pagination={false} columns={[
                  { title: '事件类型', dataIndex: 'event_type', width: 140 },
                  { title: '标题模板', dataIndex: 'title_template', ellipsis: true },
                  { title: '内容模板', dataIndex: 'content_template', ellipsis: true },
                  { title: '启用', dataIndex: 'is_active', width: 60, render: (v: boolean, r: any) => (
                    <Switch size="small" checked={v} onChange={async (checked) => {
                      try { await client.put(`/api/v1/notification_templates/${r.id}`, { is_active: checked }); fetchAll() } catch { message.error('更新失败') }
                    }} />
                  )},
                  { title: '', width: 100, render: (_: unknown, r: any) => (
                    <Space size="middle">
                      <a className="text-primary text-sm font-bold" onClick={() => {
                        setNtEditingId(r.id)
                        setNtForm({ event_type: r.event_type, title_template: r.title_template, content_template: r.content_template || '', is_active: r.is_active })
                        setNtModal(true)
                      }}>编辑</a>
                      <a className={`text-rose-500 text-sm font-bold ${deletingId === r.id ? 'opacity-50 pointer-events-none' : ''}`} onClick={async () => {
                        setDeletingId(r.id); try { await client.delete(`/api/v1/notification_templates/${r.id}`); message.success('已删除'); fetchAll() } catch { message.error('删除失败') } finally { setDeletingId(null) }
                      }}>删除</a>
                    </Space>
                  )},
                ]} />
              </div>
            ),
          },
          {
            key: 'ai', label: 'AI策略',
            children: (
              <div className="pb-6">
                <Table rowKey="id" dataSource={aiPolicies} size="small" pagination={false} columns={[
                  { title: '任务类型', dataIndex: 'task_type', width: 150 },
                  { title: '模型路由', dataIndex: 'model_route_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '预算', dataIndex: 'budget_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '启用', dataIndex: 'enabled', width: 80, render: (v: boolean) => v ? '是' : '否' },
                ]} />
                {aiPolicies.length === 0 && <div className="text-center py-8 text-slate-400 text-sm">暂无AI策略，可通过API添加</div>}
              </div>
            ),
          },
          {
            key: 'integration', label: '集成配置',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-3">
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
                    setIntEditingId(null); setIntForm(defaultIntForm); setIntModal(true)
                  }}>新增集成</Button>
                </div>
                <Table rowKey="id" dataSource={integrations} size="small" pagination={false} columns={[
                  { title: '系统', dataIndex: 'system_code', width: 120, render: (v: string) => <span className="font-mono text-sm">{v}</span> },
                  { title: '名称', dataIndex: 'name', width: 150 },
                  { title: 'URL', dataIndex: 'base_url', ellipsis: true },
                  { title: '认证', dataIndex: 'auth_type', width: 100 },
                  { title: '状态', dataIndex: 'status', width: 80, render: (v: string) => (
                    <Tag color={v === 'active' ? 'green' : 'default'}>{v === 'active' ? '启用' : '停用'}</Tag>
                  )},
                  { title: '', width: 180, render: (_: unknown, r: Integration) => (
                    <Space size="middle">
                      <a className="text-emerald-600 text-sm font-bold" onClick={async () => {
                        try {
                          const res = await settingsApi.testIntegration(r.id) as { data: { connected: boolean; error?: string } }
                          if (res.data?.connected) { message.success('连接成功') } else { message.warning(`连接失败: ${res.data?.error || '无法连接'}`) }
                        } catch { message.error('测试连接失败') }
                      }}>测试</a>
                      <a className="text-primary text-sm font-bold" onClick={() => {
                        setIntEditingId(r.id)
                        setIntForm({
                          system_code: r.system_code, name: r.name || '', base_url: r.base_url || '',
                          auth_type: r.auth_type || 'apikey', status: r.status || 'active',
                          auth_config_json: (r.auth_config_json as Record<string, string>) || {},
                        })
                        setIntModal(true)
                      }}>编辑</a>
                      <a className={`text-rose-500 text-sm font-bold ${deletingId === r.id ? 'opacity-50 pointer-events-none' : ''}`} onClick={async () => {
                        setDeletingId(r.id); try { await settingsApi.deleteIntegration(r.id); message.success('已删除'); fetchAll() } catch { message.error('删除失败') } finally { setDeletingId(null) }
                      }}>删除</a>
                    </Space>
                  )},
                ]} />
              </div>
            ),
          },
          {
            key: 'file_storage', label: '文件存储',
            children: <FileStorageTab />,
          },
          {
            key: 'ai_budget', label: 'AI用量',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-4">
                  <Button type="primary" size="small" onClick={() => {
                    if (aiBudget) setBudgetForm({
                      budget_cost: aiBudget.budget_cost || 100,
                      budget_tokens: aiBudget.budget_tokens || 10000000,
                      hard_limit: aiBudget.hard_limit,
                    })
                    setBudgetModal(true)
                  }}>设置预算</Button>
                </div>
                <div className="grid grid-cols-2 gap-6">
                  {/* Cost Progress */}
                  <div className="bg-slate-50 rounded-xl p-5 border border-slate-200">
                    <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">费用预算 ({currentPeriod})</div>
                    {aiBudget ? (
                      <>
                        <Progress
                          percent={aiBudget.budget_cost ? Math.min(100, Math.round(((aiBudget.used_cost || 0) / aiBudget.budget_cost) * 100)) : 0}
                          status={aiBudget.budget_cost && (aiBudget.used_cost || 0) >= aiBudget.budget_cost ? 'exception' : 'active'}
                          strokeColor={aiBudget.budget_cost && (aiBudget.used_cost || 0) >= aiBudget.budget_cost * 0.8 ? '#ef4444' : '#135bec'}
                        />
                        <div className="flex justify-between mt-2">
                          <span className="text-sm text-slate-600">已用: <b>${(aiBudget.used_cost || 0).toFixed(2)}</b></span>
                          <span className="text-sm text-slate-600">预算: <b>${(aiBudget.budget_cost || 0).toFixed(2)}</b></span>
                        </div>
                      </>
                    ) : (
                      <div className="text-sm text-slate-400">暂未设置预算</div>
                    )}
                  </div>
                  {/* Token Progress */}
                  <div className="bg-slate-50 rounded-xl p-5 border border-slate-200">
                    <div className="text-sm font-bold text-slate-400 uppercase tracking-wider mb-3">Token 配额 ({currentPeriod})</div>
                    {aiBudget ? (
                      <>
                        <Progress
                          percent={aiBudget.budget_tokens ? Math.min(100, Math.round(((aiBudget.used_tokens || 0) / aiBudget.budget_tokens) * 100)) : 0}
                          status={aiBudget.budget_tokens && (aiBudget.used_tokens || 0) >= aiBudget.budget_tokens ? 'exception' : 'active'}
                          strokeColor={aiBudget.budget_tokens && (aiBudget.used_tokens || 0) >= aiBudget.budget_tokens * 0.8 ? '#ef4444' : '#135bec'}
                        />
                        <div className="flex justify-between mt-2">
                          <span className="text-sm text-slate-600">已用: <b>{((aiBudget.used_tokens || 0) / 1000000).toFixed(2)}M</b></span>
                          <span className="text-sm text-slate-600">配额: <b>{((aiBudget.budget_tokens || 0) / 1000000).toFixed(2)}M</b></span>
                        </div>
                      </>
                    ) : (
                      <div className="text-sm text-slate-400">暂未设置配额</div>
                    )}
                  </div>
                </div>
                {aiBudget && (
                  <div className="mt-4 flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full ${aiBudget.hard_limit ? 'bg-red-500' : 'bg-emerald-500'}`} />
                    <span className="text-sm text-slate-500">
                      {aiBudget.hard_limit ? '硬限制模式：超出预算将阻止 AI 请求' : '软限制模式：超出预算仅记录，不阻止'}
                    </span>
                  </div>
                )}
              </div>
            ),
          },
          {
            key: 'features', label: '功能开关',
            children: (
              <div className="pb-6">
                {features.length === 0 ? (
                  <div className="text-center py-8 text-slate-400 text-sm">暂无功能开关配置</div>
                ) : (
                  <Table rowKey="id" dataSource={features} size="small" pagination={false} columns={[
                    { title: '功能', dataIndex: 'feature_code', width: 200 },
                    { title: '启用', dataIndex: 'enabled', width: 100, render: (v: boolean, r: FeatureToggle) => (
                      <Switch checked={v} onChange={async (checked) => {
                        try {
                          await settingsApi.updateFeature(r.feature_code, { enabled: checked })
                          fetchAll()
                        } catch {
                          message.error('更新功能开关失败')
                        }
                      }} />
                    )},
                    { title: '配置', dataIndex: 'config_json', render: (v: unknown) => <JsonCell value={v} /> },
                  ]} />
                )}
              </div>
            ),
          },
          {
            key: 'custom_fields', label: '自定义字段',
            children: (
              <div className="pb-6">
                <div className="flex justify-end mb-3">
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => { setCfForm(defaultCfForm); setCfEditingId(null); setCfModal(true) }}>新增字段</Button>
                </div>
                <Table rowKey="id" dataSource={customFields} size="small" pagination={false} columns={[
                  { title: '实体', dataIndex: 'entity_type', width: 80, render: (v: string) => entityTypeLabels[v] || v },
                  { title: '字段Key', dataIndex: 'field_key', width: 120 },
                  { title: '标签', dataIndex: 'field_label', width: 100 },
                  { title: '类型', dataIndex: 'field_type', width: 80, render: (v: string) => fieldTypeLabels[v] || v },
                  { title: '选项', dataIndex: 'options_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '必填', dataIndex: 'required', width: 60, render: (v: boolean) => v ? '是' : '-' },
                  { title: '排序', dataIndex: 'sort_order', width: 60 },
                  { title: '启用', dataIndex: 'enabled', width: 60, render: (v: boolean) => v ? '是' : '否' },
                  { title: '操作', key: 'actions', width: 120, render: (_: unknown, r: CustomFieldItem) => (
                    <Space size={4}>
                      <a onClick={() => {
                        setCfEditingId(r.id)
                        setCfForm({ entity_type: r.entity_type, field_key: r.field_key, field_label: r.field_label, field_type: r.field_type, options_json: Array.isArray(r.options_json) ? r.options_json : [], required: r.required, sort_order: r.sort_order, enabled: r.enabled })
                        setCfModal(true)
                      }} className="text-primary text-sm font-bold">编辑</a>
                      <a className={`text-rose-500 text-sm font-bold ${deletingId === r.id ? 'opacity-50 pointer-events-none' : ''}`} onClick={async () => {
                        setDeletingId(r.id); try { await settingsApi.deleteCustomField(r.id); message.success('已删除'); fetchAll() } catch { message.error('删除失败') } finally { setDeletingId(null) }
                      }}>删除</a>
                    </Space>
                  )},
                ]} />
                {customFields.length === 0 && <div className="text-center py-8 text-slate-400 text-sm">暂无自定义字段</div>}
              </div>
            ),
          },
          {
            key: 'backup', label: '数据备份',
            children: (
              <div className="pb-6">
                <div className="mb-4">
                  <p className="text-sm text-slate-500 mb-4">导出当前租户的全部业务数据为 JSON 文件，可用于数据备份或迁移。</p>
                  <Space>
                    <Button type="primary" icon={<CloudDownloadOutlined />} loading={backupLoading} onClick={() => {
                      setBackupLoading(true)
                      downloadFile(settingsApi.backupDownloadUrl(), `backup_${new Date().toISOString().slice(0, 10)}.json`)
                      setTimeout(() => setBackupLoading(false), 3000)
                    }}>下载备份</Button>
                    <Button icon={<UploadOutlined />} onClick={() => {
                      const input = document.createElement('input')
                      input.type = 'file'
                      input.accept = '.json'
                      input.onchange = async (e) => {
                        const file = (e.target as HTMLInputElement).files?.[0]
                        if (!file) return
                        try {
                          const text = await file.text()
                          const data = JSON.parse(text)
                          Modal.confirm({
                            title: '确认恢复数据',
                            content: '将从备份文件导入数据，已存在的记录会跳过。确定继续吗？',
                            onOk: async () => {
                              const res = await settingsApi.restoreBackup(data) as any
                              message.success(`恢复完成: 导入 ${res.data?.total_restored || 0} 条，跳过 ${res.data?.total_skipped || 0} 条`)
                              fetchAll()
                            },
                          })
                        } catch { message.error('文件解析失败，请确认为有效的备份JSON文件') }
                      }
                      input.click()
                    }}>从备份恢复</Button>
                  </Space>
                </div>
                <h3 className="text-sm font-bold text-slate-700 mb-3">数据统计</h3>
                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
                  {Object.entries(backupStats).map(([table, count]) => {
                    const labelMap: Record<string, string> = {
                      customers: '客户', contacts: '联系人', leads: '线索',
                      opportunities: '商机', quotes: '报价', quote_lines: '报价行',
                      contracts: '合同', solutions: '方案', delivery_milestones: '里程碑',
                      payment_plans: '回款计划', invoices: '发票', payment_records: '收款记录',
                      change_requests: '变更', service_tickets: '工单',
                      renewal_opportunities: '续约', activities: '动态', products: '产品',
                      approval_flows: '审批流', approval_tasks: '审批任务',
                      notifications: '通知', sales_targets: '销售目标',
                    }
                    return (
                      <div key={table} className="flex items-center justify-between px-3 py-2 bg-slate-50 rounded-lg border border-slate-100">
                        <span className="text-sm text-slate-500">{labelMap[table] || table}</span>
                        <span className="text-sm font-black text-slate-800">{count.toLocaleString()}</span>
                      </div>
                    )
                  })}
                </div>
                {Object.keys(backupStats).length === 0 && (
                  <div className="text-center py-8 text-slate-400 text-sm">暂无统计数据</div>
                )}
              </div>
            ),
          },
          {
            key: 'data_dict', label: '数据字典',
            children: <DataDictTab />,
          },
          {
            key: 'recycle_bin', label: '回收站',
            children: <RecycleBinTab />,
          },
          {
            key: 'health', label: '系统健康',
            children: <HealthCheckTab />,
          },
          {
            key: 'rate_limit', label: '限流监控',
            children: <RateLimitTab />,
          },
          {
            key: 'pool_rules', label: '公海规则',
            children: (
              <div className="pb-6 max-w-lg">
                <p className="text-sm text-slate-500 mb-4">配置客户自动释放到公海的规则。系统每5分钟检查一次，将超过闲置天数未跟进的客户自动释放。</p>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">启用自动释放</span>
                    <Switch checked={poolRules.enabled} onChange={(v) => setPoolRules({ ...poolRules, enabled: v })} />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-2 block">按客户级别设置闲置天数</label>
                    <div className="grid grid-cols-2 gap-3">
                      {['A', 'B', 'C', 'D'].map((level) => (
                        <div key={level} className="flex items-center gap-2">
                          <Tag className="w-8 text-center font-bold">{level}</Tag>
                          <InputNumber className="flex-1" min={1} max={365}
                            value={(poolRules.idle_days as Record<string, number>)[level]}
                            onChange={(v) => setPoolRules({ ...poolRules, idle_days: { ...poolRules.idle_days, [level]: v || 30 } })}
                            addonAfter="天" />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-slate-700 mb-1 block">默认闲置天数（未设级别时）</label>
                    <InputNumber min={1} max={365} value={poolRules.default_idle_days}
                      onChange={(v) => setPoolRules({ ...poolRules, default_idle_days: v || 30 })}
                      addonAfter="天" />
                  </div>
                  <Button type="primary" loading={poolSaving} onClick={async () => {
                    setPoolSaving(true)
                    try {
                      await settingsApi.updatePoolRules(poolRules)
                      message.success('公海规则已保存')
                    } catch { message.error('保存失败') }
                    finally { setPoolSaving(false) }
                  }}>保存规则</Button>
                </div>
              </div>
            ),
          },
          {
            key: 'field_rules', label: '字段权限',
            children: <FieldRulesTab />,
          },
          {
            key: 'report_schedules', label: '报表推送',
            children: <ReportScheduleTab />,
          },
          {
            key: 'audit_verify', label: '审计校验',
            children: (
              <div className="pb-6">
                <p className="text-sm text-slate-500 mb-4">验证审计日志完整性，检测是否存在篡改记录。系统会重新计算每条日志的内容哈希并与存储值比对。</p>
                <Button type="primary" icon={<SafetyCertificateOutlined />} loading={auditLoading} onClick={async () => {
                  setAuditLoading(true)
                  try {
                    const r = await settingsApi.auditVerify()
                    setAuditResult(r.data)
                  } catch { message.error('校验失败') }
                  finally { setAuditLoading(false) }
                }}>开始校验</Button>

                {auditResult && (
                  <div className="mt-6">
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 text-center">
                        <div className="text-2xl font-black text-slate-900">{auditResult.total_checked}</div>
                        <div className="text-sm text-slate-500 mt-1">检查总数</div>
                      </div>
                      <div className={`rounded-xl p-4 border text-center ${auditResult.tampered_count === 0 ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
                        <div className={`text-2xl font-black ${auditResult.tampered_count === 0 ? 'text-emerald-700' : 'text-red-600'}`}>{auditResult.tampered_count}</div>
                        <div className={`text-sm mt-1 ${auditResult.tampered_count === 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                          {auditResult.tampered_count === 0 ? '无异常' : '疑似篡改'}
                        </div>
                      </div>
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 text-center">
                        <div className="text-2xl font-black text-slate-900">{auditResult.no_hash}</div>
                        <div className="text-sm text-slate-500 mt-1">无哈希记录</div>
                      </div>
                    </div>

                    {auditResult.tampered_count > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-red-600 mb-2">异常记录 (前50条)</h4>
                        <Table rowKey="id" dataSource={auditResult.tampered} size="small" pagination={false} columns={[
                          { title: 'ID', dataIndex: 'id', width: 280, render: (v: string) => <span className="font-mono text-sm">{v}</span> },
                          { title: '时间', dataIndex: 'created_at', width: 180 },
                          { title: '摘要', dataIndex: 'summary' },
                        ]} />
                      </div>
                    )}

                    {auditResult.tampered_count === 0 && (
                      <div className="text-center py-4">
                        <span className="text-emerald-600 font-bold text-lg">
                          <SafetyCertificateOutlined className="mr-2" />
                          审计日志完整性验证通过
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ),
          },
        ]} />
      </div>

      {/* Stage Modal */}
      <Modal title="配置阶段 Gate" open={stageModal} onOk={handleSaveStage} onCancel={() => setStageModal(false)} width={720}>
        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">阶段代码</label>
              <Input value={stageForm.stage_code} onChange={(e) => setStageForm({ ...stageForm, stage_code: e.target.value })} placeholder="S1" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">阶段名称</label>
              <Input value={stageForm.name} onChange={(e) => setStageForm({ ...stageForm, name: e.target.value })} placeholder="线索确认" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-2 block">
              Gate 规则
              <span className="text-[13px] text-slate-400 ml-2 font-normal">推进到该阶段时执行的检查列表，全部通过才允许推进。</span>
            </label>
            <GateRulesEditor
              value={stageForm.gate_rules}
              onChange={(rules) => setStageForm({ ...stageForm, gate_rules: rules })}
            />
          </div>
        </div>
      </Modal>

      {/* Margin Modal */}
      <Modal title="新增毛利红线" open={marginModal} onOk={handleCreateMargin} onCancel={() => setMarginModal(false)}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">策略编码</label>
            <Input value={marginForm.policy_code} onChange={(e) => setMarginForm({ ...marginForm, policy_code: e.target.value })} placeholder="MARGIN_DEFAULT" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">红线比例</label>
            <InputNumber className="w-full" value={marginForm.redline_rate} onChange={(v) => setMarginForm({ ...marginForm, redline_rate: v || 0.2 })}
              min={0} max={1} step={0.01} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">动作</label>
            <Select className="w-full" value={marginForm.action} onChange={(v) => setMarginForm({ ...marginForm, action: v })}
              options={[{ value: 'warn', label: '警告' }, { value: 'need_approval', label: '需审批' }, { value: 'block', label: '阻断' }]} />
          </div>
        </div>
      </Modal>

      {/* AI Budget Modal */}
      <Modal title="设置 AI 预算" open={budgetModal} onOk={handleSaveBudget} onCancel={() => setBudgetModal(false)}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">月度费用预算 ($)</label>
            <InputNumber className="w-full" value={budgetForm.budget_cost} onChange={(v) => setBudgetForm({ ...budgetForm, budget_cost: v || 100 })}
              min={0} step={10} precision={2} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">月度 Token 配额</label>
            <InputNumber className="w-full" value={budgetForm.budget_tokens} onChange={(v) => setBudgetForm({ ...budgetForm, budget_tokens: v || 10000000 })}
              min={0} step={1000000} formatter={(v) => `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')} />
          </div>
          <div className="flex items-center gap-3">
            <Switch checked={budgetForm.hard_limit} onChange={(v) => setBudgetForm({ ...budgetForm, hard_limit: v })} />
            <span className="text-sm text-slate-700">硬限制（超出预算阻止请求）</span>
          </div>
        </div>
      </Modal>

      {/* Approval Policy Modal */}
      <ApprovalPolicyModal
        open={apModal}
        editingId={apEditingId}
        initialData={apForm}
        onSave={handleSaveAp}
        onCancel={() => { setApModal(false); setApEditingId(null) }}
      />

      {/* Doc Template Modal */}
      <Modal title={dtEditingId ? '编辑文档模板' : '新增文档模板'} open={dtModal} onOk={handleSaveDt} onCancel={() => { setDtModal(false); setDtEditingId(null) }} width={600}>
        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">类型</label>
              <Select className="w-full" value={dtForm.doc_type} onChange={(v) => setDtForm({ ...dtForm, doc_type: v })}
                options={[{ value: 'quote', label: '报价模板' }, { value: 'contract', label: '合同模板' }]} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">名称</label>
              <Input value={dtForm.name} onChange={(e) => setDtForm({ ...dtForm, name: e.target.value })} placeholder="标准报价模板" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">说明</label>
            <Input value={dtForm.description} onChange={(e) => setDtForm({ ...dtForm, description: e.target.value })} placeholder="模板说明（可选）" />
          </div>

          <div className="rounded-lg border border-slate-200 p-3 space-y-3 bg-slate-50/50">
            <div className="text-sm font-bold text-slate-500">模板内容</div>
            <div>
              <label className="text-[12px] text-slate-500 mb-1 block">标题</label>
              <Input value={dtForm.title} onChange={(e) => setDtForm({ ...dtForm, title: e.target.value })}
                placeholder={dtForm.doc_type === 'quote' ? '标准报价' : '标准合同'} />
            </div>

            {dtForm.doc_type === 'quote' ? (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-[12px] text-slate-500 mb-1 block">税率（如 0.13 表示 13%）</label>
                    <InputNumber className="w-full" min={0} max={1} step={0.01} value={dtForm.tax_rate}
                      onChange={(v) => setDtForm({ ...dtForm, tax_rate: v })} />
                  </div>
                  <div>
                    <label className="text-[12px] text-slate-500 mb-1 block">有效期（天）</label>
                    <InputNumber className="w-full" min={0} value={dtForm.validity_days}
                      onChange={(v) => setDtForm({ ...dtForm, validity_days: v })} />
                  </div>
                </div>
                <div>
                  <label className="text-[12px] text-slate-500 mb-1 block">条款摘要</label>
                  <KeyValueEditor value={dtForm.terms} keyPlaceholder="条款名，如 付款" valPlaceholder="内容，如 预付30%"
                    addText="添加条款" onChange={(v) => setDtForm({ ...dtForm, terms: v })} />
                </div>
                <div>
                  <label className="text-[12px] text-slate-500 mb-1 block">报价明细</label>
                  <div className="space-y-2">
                    {dtForm.lines.map((l, i) => (
                      <div key={i} className="flex items-center gap-2">
                        <Input className="flex-1" placeholder="项目名称" value={l.item_name} onChange={(e) => dtUpdateLine(i, 'item_name', e.target.value)} />
                        <InputNumber className="!w-20" placeholder="数量" min={0} value={l.qty} onChange={(v) => dtUpdateLineNum(i, 'qty', v ?? 0)} />
                        <Input className="!w-16" placeholder="单位" value={l.unit} onChange={(e) => dtUpdateLine(i, 'unit', e.target.value)} />
                        <InputNumber className="!w-28" placeholder="单价" min={0} value={l.unit_price} onChange={(v) => dtUpdateLineNum(i, 'unit_price', v ?? 0)} />
                        <Button type="text" danger icon={<DeleteOutlined />} onClick={() => setDtForm({ ...dtForm, lines: dtForm.lines.filter((_, idx) => idx !== i) })} />
                      </div>
                    ))}
                    <Button type="dashed" size="small" icon={<PlusOutlined />} block
                      onClick={() => setDtForm({ ...dtForm, lines: [...dtForm.lines, { item_name: '', qty: 1, unit: '', unit_price: 0 }] })}>添加明细行</Button>
                  </div>
                </div>
              </>
            ) : (
              <>
                <div>
                  <label className="text-[12px] text-slate-500 mb-1 block">付款条款</label>
                  <KeyValueEditor value={dtForm.payment_terms} keyPlaceholder="条款名，如 付款方式" valPlaceholder="内容，如 分期"
                    addText="添加付款条款" onChange={(v) => setDtForm({ ...dtForm, payment_terms: v })} />
                </div>
                <div>
                  <label className="text-[12px] text-slate-500 mb-1 block">交付条款</label>
                  <KeyValueEditor value={dtForm.delivery_terms} keyPlaceholder="条款名，如 交付地址" valPlaceholder="内容，如 客户指定"
                    addText="添加交付条款" onChange={(v) => setDtForm({ ...dtForm, delivery_terms: v })} />
                </div>
                <div>
                  <label className="text-[12px] text-slate-500 mb-1 block">关键条款</label>
                  <StringListEditor value={dtForm.key_clauses} placeholder="如：验收条款"
                    addText="添加关键条款" onChange={(v) => setDtForm({ ...dtForm, key_clauses: v })} />
                </div>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            <Switch checked={dtForm.is_default} onChange={(v) => setDtForm({ ...dtForm, is_default: v })} />
            <span className="text-sm text-slate-700">设为默认模板</span>
          </div>
        </div>
      </Modal>

      {/* Email Template Modal — with live preview */}
      <Modal title={etEditingId ? '编辑邮件模板' : '新增邮件模板'} open={etModal} onOk={handleSaveEt}
        onCancel={() => { setEtModal(false); setEtEditingId(null) }} width={900}>
        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">编码</label>
              <Input value={etForm.code} onChange={(e) => setEtForm({ ...etForm, code: e.target.value })} placeholder="follow_up_reminder" disabled={!!etEditingId} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">名称</label>
              <Input value={etForm.name} onChange={(e) => setEtForm({ ...etForm, name: e.target.value })} placeholder="跟进提醒" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">邮件主题</label>
            <Input value={etForm.subject} onChange={(e) => setEtForm({ ...etForm, subject: e.target.value })}
              placeholder="【提醒】{{customer_name}} 需要跟进" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">邮件内容</label>
            <div className="flex gap-0 border border-slate-200 rounded-lg overflow-hidden" style={{ height: 280 }}>
              <div className="flex-1 flex flex-col">
                <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200 text-sm font-bold text-slate-500">HTML 编辑</div>
                <div className="flex gap-1 px-2 py-1 bg-slate-50 border-b border-slate-200">
                  {[
                    { label: 'B', tag: '<strong>', end: '</strong>' },
                    { label: 'I', tag: '<em>', end: '</em>' },
                    { label: 'H2', tag: '<h2>', end: '</h2>' },
                    { label: 'P', tag: '<p>', end: '</p>' },
                    { label: 'Link', tag: '<a href="">', end: '</a>' },
                    { label: 'Img', tag: '<img src="" alt="" />', end: '' },
                  ].map((btn) => (
                    <button key={btn.label} type="button" className="px-2 py-0.5 text-sm rounded border border-slate-200 hover:bg-slate-100 text-slate-600"
                      onClick={() => {
                        const ins = btn.end ? `${btn.tag}文本${btn.end}` : btn.tag
                        setEtForm({ ...etForm, body_html: (etForm.body_html || '') + ins })
                      }}>
                      {btn.label}
                    </button>
                  ))}
                </div>
                <TextArea
                  className="flex-1 !border-0 !rounded-none !shadow-none !resize-none"
                  value={etForm.body_html}
                  onChange={(e) => setEtForm({ ...etForm, body_html: e.target.value })}
                  placeholder="<p>{{user_name}} 你好，</p><p>客户 {{customer_name}} 已 {{days}} 天未跟进。</p>"
                  style={{ fontFamily: 'monospace', fontSize: 12 }}
                />
              </div>
              <div className="flex-1 flex flex-col border-l border-slate-200">
                <div className="px-3 py-1.5 bg-slate-50 border-b border-slate-200 text-sm font-bold text-slate-500">预览</div>
                <div className="flex-1 p-3 overflow-auto text-sm"
                  dangerouslySetInnerHTML={{ __html: sanitizeHtml(etForm.body_html || '<span class="text-slate-300">邮件预览区域</span>') }} />
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Switch checked={etForm.enabled} onChange={(v) => setEtForm({ ...etForm, enabled: v })} />
            <span className="text-sm text-slate-700">启用</span>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">变量定义</label>
            <div className="space-y-2">
              {etForm.variables_json.map((v, i) => (
                <div key={i} className="flex items-center gap-2">
                  <Input className="!w-1/3" value={v.name} placeholder="变量名，如 customer_name"
                    onChange={(e) => setEtForm({ ...etForm, variables_json: etForm.variables_json.map((x, idx) => (idx === i ? { ...x, name: e.target.value } : x)) })} />
                  <Input className="flex-1" value={v.label} placeholder="说明，如 客户名称"
                    onChange={(e) => setEtForm({ ...etForm, variables_json: etForm.variables_json.map((x, idx) => (idx === i ? { ...x, label: e.target.value } : x)) })} />
                  <Button type="text" danger icon={<DeleteOutlined />}
                    onClick={() => setEtForm({ ...etForm, variables_json: etForm.variables_json.filter((_, idx) => idx !== i) })} />
                </div>
              ))}
              <Button type="dashed" size="small" icon={<PlusOutlined />}
                onClick={() => setEtForm({ ...etForm, variables_json: [...etForm.variables_json, { name: '', label: '' }] })} block>添加变量</Button>
            </div>
            {etForm.variables_json.some((v) => v.name) && (
              <div className="text-sm text-slate-400 mt-2">可用变量：{etForm.variables_json.filter((v) => v.name).map((v) => <Tag key={v.name} className="text-[12px]">{`{{${v.name}}}`}</Tag>)}</div>
            )}
          </div>
        </div>
      </Modal>

      {/* Notification Template Modal */}
      <Modal title={ntEditingId ? '编辑通知模板' : '新增通知模板'} open={ntModal}
        onCancel={() => { setNtModal(false); setNtEditingId(null) }} width={560}
        onOk={async () => {
          if (!ntForm.event_type || !ntForm.title_template) { message.error('事件类型和标题模板必填'); return }
          try {
            if (ntEditingId) {
              await client.put(`/api/v1/notification_templates/${ntEditingId}`, ntForm)
            } else {
              await client.post('/api/v1/notification_templates', ntForm)
            }
            message.success('保存成功'); setNtModal(false); setNtEditingId(null); fetchAll()
          } catch { message.error('保存失败') }
        }}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">事件类型</label>
            <Select value={ntForm.event_type || undefined} onChange={(v) => setNtForm({ ...ntForm, event_type: v })}
              placeholder="选择事件类型" style={{ width: '100%' }}
              options={[
                { label: '待审批', value: 'approval_pending' },
                { label: '审批结果', value: 'approval_decided' },
                { label: '阶段变更', value: 'stage_change' },
                { label: '回款逾期', value: 'payment_overdue' },
                { label: 'AI任务完成', value: 'ai_task_complete' },
                { label: '合同到期', value: 'contract_expiry' },
                { label: '系统通知', value: 'system' },
              ]} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">标题模板</label>
            <Input value={ntForm.title_template} onChange={(e) => setNtForm({ ...ntForm, title_template: e.target.value })}
              placeholder="例: {{user_name}} 提交了 {{project_name}} 的审批" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">内容模板（可选）</label>
            <Input.TextArea rows={4} value={ntForm.content_template}
              onChange={(e) => setNtForm({ ...ntForm, content_template: e.target.value })}
              placeholder="详细内容，可使用 {{variable}} 变量" />
          </div>
          <div className="text-sm text-slate-400">
            可用变量: {ntVariables.map(v => <Tag key={v.key} className="text-[12px]">{`{{${v.key}}}`} {v.label}</Tag>)}
          </div>
        </div>
      </Modal>

      {/* Integration Modal */}
      <Modal title={intEditingId ? '编辑集成端点' : '新增集成端点'} open={intModal} onOk={handleSaveInt}
        onCancel={() => { setIntModal(false); setIntEditingId(null) }} width={560}>
        <div className="space-y-4 py-2">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">系统代码</label>
              <Select className="w-full" value={intForm.system_code} onChange={(v) => setIntForm({ ...intForm, system_code: v })}
                showSearch allowClear={false}
                options={[
                  { value: 'erp_k3', label: '金蝶K3 (ERP)' }, { value: 'erp_sap', label: 'SAP (ERP)' },
                  { value: 'erp_yonyou', label: '用友 (ERP)' }, { value: 'mes', label: 'MES' },
                  { value: 'dingtalk', label: '钉钉' }, { value: 'wecom', label: '企业微信' },
                ]} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">名称</label>
              <Input value={intForm.name} onChange={(e) => setIntForm({ ...intForm, name: e.target.value })} placeholder="金蝶K3 生产环境" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">
              {['dingtalk', 'wecom'].includes(intForm.system_code) ? 'Webhook URL' : 'Base URL'}
            </label>
            <Input value={intForm.base_url} onChange={(e) => setIntForm({ ...intForm, base_url: e.target.value })}
              placeholder={['dingtalk', 'wecom'].includes(intForm.system_code)
                ? 'https://oapi.dingtalk.com/robot/send?access_token=xxx'
                : 'https://erp.example.com/api'} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">认证方式</label>
              <Select className="w-full" value={intForm.auth_type} onChange={(v) => setIntForm({ ...intForm, auth_type: v })}
                options={[{ value: 'apikey', label: 'API Key' }, { value: 'oauth2', label: 'OAuth2' }, { value: 'basic', label: 'Basic Auth' }]} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">状态</label>
              <Select className="w-full" value={intForm.status} onChange={(v) => setIntForm({ ...intForm, status: v })}
                options={[{ value: 'active', label: '启用' }, { value: 'inactive', label: '停用' }]} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">认证配置</label>
            {getAuthFields(intForm.system_code, intForm.auth_type).length === 0 ? (
              <div className="text-[12px] text-slate-400">该集成无需额外认证配置。</div>
            ) : (
              <div className="space-y-3">
                {getAuthFields(intForm.system_code, intForm.auth_type).map((f) => {
                  const InputComp = f.secret ? Input.Password : Input
                  return (
                    <div key={f.key}>
                      <div className="text-[12px] text-slate-500 mb-1">{f.label}</div>
                      <InputComp value={intForm.auth_config_json?.[f.key] || ''} placeholder={f.placeholder}
                        onChange={(e) => setIntForm({ ...intForm, auth_config_json: { ...intForm.auth_config_json, [f.key]: e.target.value } })} />
                    </div>
                  )
                })}
              </div>
            )}
          </div>
          {intForm.system_code === 'dingtalk' && (
            <div className="text-[12px] text-slate-500 bg-blue-50 border border-blue-100 rounded-lg px-3 py-2">
              <div className="font-semibold mb-1">钉钉「待办/工作通知」配置说明</div>
              <div>• Webhook URL：群机器人地址，用于群通知（可选）。</div>
              <div>• 在「认证配置」中填写企业内部应用的 <code>app_key</code> / <code>app_secret</code> / <code>agent_id</code> 后，系统会按负责人手机号匹配钉钉账号，下发「工作通知」并尽力创建钉钉「待办」。</div>
              <div>• <code>crm_base_url</code> 用于待办卡片的跳转链接（如 https://192.168.0.42:8410）。负责人需在「用户管理」中填写手机号。</div>
            </div>
          )}
          {['dingtalk', 'wecom'].includes(intForm.system_code) && intForm.base_url && (
            <Button size="small" onClick={async () => {
              try {
                const res = await client.post('/api/v1/events/webhook/test', { url: intForm.base_url }) as any
                if (res.data?.success) {
                  message.success(`Webhook 测试成功 (HTTP ${res.data.status_code})`)
                } else {
                  message.warning(`Webhook 测试失败: ${res.data?.response_body || '未知错误'}`)
                }
              } catch { message.error('Webhook 测试请求失败') }
            }}>
              测试 Webhook 连接
            </Button>
          )}
        </div>
      </Modal>

      {/* Custom Field Modal */}
      <Modal title={cfEditingId ? '编辑自定义字段' : '新增自定义字段'} open={cfModal} onOk={handleSaveCf}
        onCancel={() => { setCfModal(false); setCfEditingId(null) }} width={520}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">实体类型</label>
            <Select className="w-full" value={cfForm.entity_type} onChange={(v) => setCfForm({ ...cfForm, entity_type: v })}
              disabled={!!cfEditingId}
              options={[{ value: 'customer', label: '客户' }, { value: 'project', label: '商机' }]} />
            <div className="text-[13px] text-slate-400 mt-1">自定义字段会显示在「客户」和「商机」的新建/编辑表单及详情页。</div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">显示标签</label>
            <Input value={cfForm.field_label} onChange={(e) => setCfForm({ ...cfForm, field_label: e.target.value })} placeholder="所在区域" />
            <div className="text-[13px] text-slate-400 mt-1">字段 Key 由系统自动生成，无需填写。</div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">字段类型</label>
            <Select className="w-full" value={cfForm.field_type} onChange={(v) => setCfForm({ ...cfForm, field_type: v })}
              options={Object.entries(fieldTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
          </div>
          {(cfForm.field_type === 'select' || cfForm.field_type === 'multiselect') && (
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">选项</label>
              <StringListEditor value={cfForm.options_json} placeholder="选项内容，如：华东区"
                addText="添加选项" onChange={(v) => setCfForm({ ...cfForm, options_json: v })} />
              <div className="text-[13px] text-slate-400 mt-1">这些选项会作为下拉项展示给填写人。</div>
            </div>
          )}
          <div className="flex gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">必填</label>
              <Switch checked={cfForm.required} onChange={(v) => setCfForm({ ...cfForm, required: v })} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">启用</label>
              <Switch checked={cfForm.enabled} onChange={(v) => setCfForm({ ...cfForm, enabled: v })} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">排序</label>
              <InputNumber value={cfForm.sort_order} onChange={(v) => setCfForm({ ...cfForm, sort_order: v || 0 })} min={0} />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}


// ==================== Data Dictionary Tab ====================
const DICT_TYPES = [
  { value: 'industry', label: '行业' },
  { value: 'customer_type', label: '客户类型' },
  { value: 'customer_source', label: '客户来源' },
  { value: 'customer_level', label: '客户等级' },
  { value: 'scale_level', label: '企业规模' },
  { value: 'risk_level', label: '风险等级' },
  { value: 'ticket_category', label: '工单分类' },
  { value: 'lead_source', label: '线索来源' },
  { value: 'budget_range', label: '预算范围' },
  { value: 'payment_method', label: '付款方式' },
  { value: 'contract_type', label: '合同类型' },
  { value: 'project_status', label: '商机状态' },
]

function HealthCheckTab() {
  const [health, setHealth] = useState<{ api: string; db: string; checked_at: string } | null>(null)
  const [loading, setLoading] = useState(false)

  const checkHealth = async () => {
    setLoading(true)
    try {
      const [apiRes, dbRes] = await Promise.allSettled([
        client.get('/health') as Promise<any>,
        client.get('/health/ready') as Promise<any>,
      ])
      setHealth({
        api: apiRes.status === 'fulfilled' ? (apiRes.value as any)?.status || 'ok' : 'error',
        db: dbRes.status === 'fulfilled' ? (dbRes.value as any)?.db || (dbRes.value as any)?.status || 'ok' : 'error',
        checked_at: new Date().toLocaleString('zh-CN'),
      })
    } catch {
      setHealth({ api: 'error', db: 'unknown', checked_at: new Date().toLocaleString('zh-CN') })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { checkHealth() }, [])

  return (
    <div className="pb-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-500">检查 API 服务和数据库连接状态</p>
        <Button size="small" loading={loading} onClick={checkHealth}>刷新</Button>
      </div>
      {health && (
        <div className="grid grid-cols-2 gap-4">
          {[
            { label: 'API 服务', status: health.api },
            { label: '数据库连接', status: health.db },
          ].map((item) => {
            const isOk = item.status === 'ok' || item.status === 'connected'
            return (
              <div key={item.label} className={`rounded-xl p-5 border ${isOk ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
                <div className="flex items-center gap-3">
                  <span className={`w-3 h-3 rounded-full ${isOk ? 'bg-emerald-500' : 'bg-red-500'}`} />
                  <span className="text-sm font-bold text-slate-800">{item.label}</span>
                </div>
                <div className={`text-lg font-black mt-2 ${isOk ? 'text-emerald-700' : 'text-red-600'}`}>
                  {isOk ? '正常' : '异常'}
                </div>
                <div className="text-sm text-slate-400 mt-1">状态: {item.status}</div>
              </div>
            )
          })}
          <div className="col-span-2 text-sm text-slate-400">
            最后检查: {health.checked_at}
          </div>
        </div>
      )}
    </div>
  )
}

function RateLimitTab() {
  const [stats, setStats] = useState<{
    rpm_limit: number; active_clients: number; total_rejected: number;
    clients: { ip: string; requests: number; limit: number; usage_pct: number; rejected: number }[]
  } | null>(null)
  const [loading, setLoading] = useState(false)

  const fetch = async () => {
    setLoading(true)
    try {
      const res = await dashboardApi.rateLimitStats() as any
      setStats(res.data)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }

  useEffect(() => { fetch(); const t = setInterval(fetch, 10000); return () => clearInterval(t) }, [])

  return (
    <div className="pb-6">
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-slate-500">API 请求限流监控（每10秒自动刷新）</p>
        <Button size="small" loading={loading} onClick={fetch}>刷新</Button>
      </div>
      {stats && (
        <>
          <div className="grid grid-cols-3 gap-4 mb-4">
            <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
              <div className="text-sm font-bold text-slate-400 mb-1">限流阈值</div>
              <div className="text-2xl font-black text-slate-900">{stats.rpm_limit} <span className="text-sm font-normal text-slate-400">RPM</span></div>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
              <div className="text-sm font-bold text-slate-400 mb-1">活跃客户端</div>
              <div className="text-2xl font-black text-primary">{stats.active_clients}</div>
            </div>
            <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
              <div className="text-sm font-bold text-slate-400 mb-1">累计拒绝</div>
              <div className={`text-2xl font-black ${stats.total_rejected > 0 ? 'text-red-600' : 'text-emerald-600'}`}>{stats.total_rejected}</div>
            </div>
          </div>
          <Table rowKey="ip" dataSource={stats.clients} size="small" pagination={false} columns={[
            { title: 'IP', dataIndex: 'ip', width: 150, render: (v: string) => <span className="font-mono text-sm">{v}</span> },
            { title: '请求数', dataIndex: 'requests', width: 80 },
            { title: '使用率', dataIndex: 'usage_pct', width: 200, render: (v: number) => (
              <div className="flex items-center gap-2">
                <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${v >= 90 ? 'bg-red-500' : v >= 70 ? 'bg-amber-500' : 'bg-emerald-500'}`}
                    style={{ width: `${Math.min(100, v)}%` }} />
                </div>
                <span className="text-sm text-slate-500 w-12 text-right">{v}%</span>
              </div>
            )},
            { title: '被拒绝', dataIndex: 'rejected', width: 80, render: (v: number) => (
              <span className={v > 0 ? 'text-red-600 font-bold' : 'text-slate-400'}>{v}</span>
            )},
          ]} />
          {stats.clients.length === 0 && <div className="text-center py-8 text-slate-400 text-sm">当前无活跃请求</div>}
        </>
      )}
    </div>
  )
}

function DataDictTab() {
  const [items, setItems] = useState<any[]>([])
  const [filterType, setFilterType] = useState<string | undefined>()
  const [modal, setModal] = useState(false)
  const [editId, setEditId] = useState<string | null>(null)
  const [form, setForm] = useState({ dict_type: 'industry', dict_code: '', dict_label: '', sort_order: 0, color: '', enabled: true })

  const fetch = () => {
    settingsApi.listDataDict(filterType).then((r: any) => r.data && setItems(r.data)).catch(() => {})
  }
  useEffect(() => { fetch() }, [filterType])

  const handleSave = async () => {
    const code = (form.dict_code || '').trim()
    const label = (form.dict_label || '').trim()
    if (!code) { message.error('请填写编码（编码不能为空，否则下拉选项会互相冲突）'); return }
    if (!label) { message.error('请填写标签'); return }
    // Prevent duplicate codes within the same dict type — duplicates make the
    // Select unable to tell options apart (issue #96).
    const dup = items.find((it) => it.id !== editId && it.dict_type === form.dict_type && (it.dict_code || '').trim() === code)
    if (dup) { message.error(`编码「${code}」在该字典类型下已存在`); return }
    try {
      const payload = { ...form, dict_code: code, dict_label: label, color: form.color || null }
      if (editId) {
        await settingsApi.updateDataDict(editId, payload)
        message.success('已更新')
      } else {
        await settingsApi.createDataDict(payload)
        message.success('已创建')
      }
      setModal(false)
      setEditId(null)
      fetch()
    } catch { message.error('保存失败') }
  }

  const handleDelete = (id: string) => {
    Modal.confirm({
      title: '删除字典项', content: '确定删除此字典项？', okType: 'danger',
      onOk: async () => {
        await settingsApi.deleteDataDict(id)
        message.success('已删除')
        fetch()
      },
    })
  }

  return (
    <div className="pb-6">
      <div className="flex items-center gap-3 mb-3">
        <Select allowClear showSearch optionFilterProp="label" placeholder="选择字典类型" value={filterType} onChange={setFilterType}
          options={DICT_TYPES} style={{ width: 180 }} size="small" />
        <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => {
          setEditId(null)
          setForm({ dict_type: filterType || 'industry', dict_code: '', dict_label: '', sort_order: 0, color: '', enabled: true })
          setModal(true)
        }}>新增</Button>
      </div>
      <Table rowKey="id" dataSource={items} size="small" pagination={false} columns={[
        { title: '类型', dataIndex: 'dict_type', width: 120, render: (v: string) => {
          const dt = DICT_TYPES.find(t => t.value === v)
          return <Tag>{dt?.label || v}</Tag>
        }},
        { title: '编码', dataIndex: 'dict_code', width: 120 },
        { title: '标签', dataIndex: 'dict_label', width: 150 },
        { title: '排序', dataIndex: 'sort_order', width: 60 },
        { title: '颜色', dataIndex: 'color', width: 80, render: (v: string) => v ? <span className="inline-block w-4 h-4 rounded" style={{ background: v }} /> : '-' },
        { title: '启用', dataIndex: 'enabled', width: 60, render: (v: boolean) => v ? <span className="text-emerald-500 font-bold">是</span> : <span className="text-slate-400">否</span> },
        { title: '操作', width: 120, render: (_: unknown, r: any) => (
          <Space size="small">
            <a className="text-primary text-sm font-bold" onClick={() => {
              setEditId(r.id)
              setForm({ dict_type: r.dict_type, dict_code: r.dict_code, dict_label: r.dict_label, sort_order: r.sort_order, color: r.color || '', enabled: r.enabled })
              setModal(true)
            }}>编辑</a>
            <a className="text-red-500 text-sm font-bold" onClick={() => handleDelete(r.id)}>删除</a>
          </Space>
        )},
      ]} />
      <Modal title={editId ? '编辑字典项' : '新增字典项'} open={modal} onOk={handleSave} onCancel={() => setModal(false)}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">字典类型</label>
            <Select showSearch optionFilterProp="label" value={form.dict_type} onChange={(v) => setForm({ ...form, dict_type: v })} options={DICT_TYPES} style={{ width: '100%' }} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block"><span className="text-red-500">*</span> 编码</label>
            <Input value={form.dict_code} onChange={(e) => setForm({ ...form, dict_code: e.target.value })} placeholder="electronics（唯一，不能为空）" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">标签</label>
            <Input value={form.dict_label} onChange={(e) => setForm({ ...form, dict_label: e.target.value })} placeholder="电子制造" />
          </div>
          <div className="flex gap-4">
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">排序</label>
              <InputNumber value={form.sort_order} onChange={(v) => setForm({ ...form, sort_order: v || 0 })} min={0} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">颜色</label>
              <Input value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} placeholder="#3b82f6" style={{ width: 120 }} />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">启用</label>
              <Switch checked={form.enabled} onChange={(v) => setForm({ ...form, enabled: v })} />
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}


// ==================== Field Rules Tab ====================

const FIELD_RESOURCES = [
  { value: 'customer', label: '客户', fields: ['phone', 'email', 'address', 'credit_code', 'bank_account'] },
  { value: 'contact', label: '联系人', fields: ['phone', 'email', 'wechat', 'id_number'] },
  { value: 'project', label: '商机', fields: ['amount_expect', 'amount_actual', 'margin_rate'] },
  { value: 'contract', label: '合同', fields: ['amount', 'payment_terms', 'bank_account'] },
  { value: 'quote', label: '报价', fields: ['price_total', 'discount_rate', 'margin_rate'] },
]

const FIELD_LABELS: Record<string, string> = {
  phone: '电话', email: '邮箱', address: '地址', credit_code: '信用代码', bank_account: '银行账户',
  wechat: '微信', id_number: '身份证号',
  amount_expect: '预期金额', amount_actual: '实际金额', margin_rate: '毛利率',
  amount: '合同金额', payment_terms: '付款条件',
  price_total: '报价总额', discount_rate: '折扣率',
}

interface FieldRule { resource: string; field: string; roles: string[]; action: 'hide' | 'mask' }

function FieldRulesTab() {
  const [rules, setRules] = useState<FieldRule[]>([])
  const [saving, setSaving] = useState(false)
  const [roles, setRoles] = useState<{ id: string; code: string; name: string }[]>([])

  useEffect(() => {
    settingsApi.getFieldRules().then((r: any) => { if (Array.isArray(r.data)) setRules(r.data) }).catch(() => {})
    client.get('/api/admin/v1/tenant/roles').then((r: any) => { if (r.data) setRoles(r.data) }).catch(() => {})
  }, [])

  const addRule = () => {
    setRules([...rules, { resource: 'customer', field: 'phone', roles: [], action: 'mask' }])
  }

  const updateRule = (idx: number, patch: Partial<FieldRule>) => {
    const next = [...rules]
    next[idx] = { ...next[idx], ...patch }
    setRules(next)
  }

  const removeRule = (idx: number) => {
    setRules(rules.filter((_, i) => i !== idx))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await settingsApi.updateFieldRules(rules as any)
      message.success('字段权限规则已保存')
    } catch { message.error('保存失败') }
    finally { setSaving(false) }
  }

  const currentFields = (resource: string) => {
    const r = FIELD_RESOURCES.find((f) => f.value === resource)
    return (r?.fields || []).map((f) => ({ value: f, label: FIELD_LABELS[f] || f }))
  }

  return (
    <div className="pb-6">
      <p className="text-sm text-slate-500 mb-4">
        配置字段级别的可见性规则。当用户拥有指定角色时，对应字段将被隐藏或脱敏显示。
      </p>
      <div className="space-y-3 mb-4">
        {rules.map((rule, idx) => (
          <div key={idx} className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg border border-slate-100">
            <Select size="small" value={rule.resource} onChange={(v) => updateRule(idx, { resource: v, field: currentFields(v)[0]?.value || '' })}
              options={FIELD_RESOURCES.map((r) => ({ value: r.value, label: r.label }))} style={{ width: 100 }} />
            <Select size="small" value={rule.field} onChange={(v) => updateRule(idx, { field: v })}
              options={currentFields(rule.resource)} style={{ width: 120 }} />
            <Select size="small" mode="multiple" value={rule.roles} onChange={(v) => updateRule(idx, { roles: v })}
              options={roles.map((r) => ({ value: r.code, label: r.name }))}
              placeholder="适用角色" style={{ minWidth: 200, flex: 1 }} />
            <Select size="small" value={rule.action} onChange={(v) => updateRule(idx, { action: v })}
              options={[{ value: 'mask', label: '脱敏 (****)' }, { value: 'hide', label: '隐藏' }]} style={{ width: 130 }} />
            <Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeRule(idx)} />
          </div>
        ))}
        {rules.length === 0 && <div className="text-center text-slate-400 py-6">暂未配置字段权限规则</div>}
      </div>
      <Space>
        <Button icon={<PlusOutlined />} onClick={addRule}>添加规则</Button>
        <Button type="primary" loading={saving} onClick={handleSave}>保存规则</Button>
      </Space>
    </div>
  )
}


// ==================== Report Schedule Tab ====================

const REPORT_TYPES = [
  { value: 'summary', label: '业务汇总' },
  { value: 'pipeline', label: '商机漏斗' },
  { value: 'revenue', label: '回款统计' },
  { value: 'activity', label: '活动报告' },
  { value: 'sla', label: 'SLA达标' },
]

const FREQ_OPTIONS = [
  { value: 'daily', label: '每日' },
  { value: 'weekly', label: '每周' },
  { value: 'monthly', label: '每月' },
]

const WEEKDAY_OPTIONS = [
  { value: 0, label: '周一' }, { value: 1, label: '周二' }, { value: 2, label: '周三' },
  { value: 3, label: '周四' }, { value: 4, label: '周五' }, { value: 5, label: '周六' }, { value: 6, label: '周日' },
]

interface ReportSchedule {
  name: string; report_type: string; frequency: string
  send_hour: number; send_weekday?: number; send_day?: number
  recipient_ids: string[]; enabled: boolean
}

function ReportScheduleTab() {
  const [schedules, setSchedules] = useState<ReportSchedule[]>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    settingsApi.getReportSchedules().then((r: any) => {
      if (Array.isArray(r.data)) setSchedules(r.data)
    }).catch(() => {})
  }, [])

  const addSchedule = () => {
    setSchedules([...schedules, { name: '新报表', report_type: 'summary', frequency: 'daily', send_hour: 8, recipient_ids: [], enabled: true }])
  }

  const updateSchedule = (idx: number, patch: Partial<ReportSchedule>) => {
    const next = [...schedules]
    next[idx] = { ...next[idx], ...patch }
    setSchedules(next)
  }

  const removeSchedule = (idx: number) => {
    setSchedules(schedules.filter((_, i) => i !== idx))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await settingsApi.updateReportSchedules(schedules as any)
      message.success('报表推送计划已保存')
    } catch { message.error('保存失败') }
    finally { setSaving(false) }
  }

  return (
    <div className="pb-6">
      <p className="text-sm text-slate-500 mb-4">
        配置定时报表推送，系统将按计划发送报表通知给指定用户。
      </p>
      <div className="space-y-4 mb-4">
        {schedules.map((sched, idx) => (
          <div key={idx} className="p-4 bg-slate-50 rounded-lg border border-slate-100">
            <div className="flex items-center gap-3 mb-3">
              <Input size="small" value={sched.name} onChange={(e) => updateSchedule(idx, { name: e.target.value })}
                placeholder="报表名称" style={{ width: 160 }} />
              <Select size="small" value={sched.report_type} onChange={(v) => updateSchedule(idx, { report_type: v })}
                options={REPORT_TYPES} style={{ width: 120 }} />
              <Select size="small" value={sched.frequency} onChange={(v) => updateSchedule(idx, { frequency: v })}
                options={FREQ_OPTIONS} style={{ width: 100 }} />
              <InputNumber size="small" value={sched.send_hour} onChange={(v) => updateSchedule(idx, { send_hour: v ?? 8 })}
                min={0} max={23} addonAfter="时" style={{ width: 100 }} />
              {sched.frequency === 'weekly' && (
                <Select size="small" value={sched.send_weekday ?? 0} onChange={(v) => updateSchedule(idx, { send_weekday: v })}
                  options={WEEKDAY_OPTIONS} style={{ width: 90 }} />
              )}
              {sched.frequency === 'monthly' && (
                <InputNumber size="small" value={sched.send_day ?? 1} onChange={(v) => updateSchedule(idx, { send_day: v ?? 1 })}
                  min={1} max={28} addonAfter="日" style={{ width: 100 }} />
              )}
              <Switch size="small" checked={sched.enabled} onChange={(v) => updateSchedule(idx, { enabled: v })} />
              <Button size="small" danger icon={<DeleteOutlined />} onClick={() => removeSchedule(idx)} />
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-500">接收人ID (逗号分隔):</span>
              <Input size="small" value={(sched.recipient_ids || []).join(',')}
                onChange={(e) => updateSchedule(idx, { recipient_ids: e.target.value.split(',').map((s) => s.trim()).filter(Boolean) })}
                placeholder="user-id-1, user-id-2" style={{ flex: 1 }} />
            </div>
          </div>
        ))}
        {schedules.length === 0 && <div className="text-center text-slate-400 py-6">暂未配置报表推送计划</div>}
      </div>
      <Space>
        <Button icon={<PlusOutlined />} onClick={addSchedule}>添加推送计划</Button>
        <Button type="primary" loading={saving} onClick={handleSave}>保存</Button>
      </Space>
    </div>
  )
}


// ==================== Recycle Bin Tab ====================
const BIZ_TYPE_MAP: Record<string, string> = {
  customer: '客户', lead: '线索', project: '商机',
}

function RecycleBinTab() {
  const [items, setItems] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [filterType, setFilterType] = useState<string | undefined>()
  const [keyword, setKeyword] = useState('')
  const [loading, setLoading] = useState(false)

  const fetch = (p = page) => {
    setLoading(true)
    settingsApi.listRecycleBin({ biz_type: filterType, keyword: keyword || undefined, page_no: p, page_size: 20 })
      .then((r: any) => { setItems(r.data?.items || []); setTotal(r.data?.total || 0) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }
  useEffect(() => { fetch(1); setPage(1) }, [filterType])

  const handleRestore = async (bizType: string, id: string) => {
    try {
      await settingsApi.restoreRecord(bizType, id)
      message.success('已恢复')
      fetch()
    } catch { message.error('恢复失败') }
  }

  const handlePermanentDelete = (bizType: string, id: string) => {
    Modal.confirm({
      title: '永久删除', content: '永久删除后数据将无法恢复，确定继续？',
      okType: 'danger', okText: '永久删除',
      onOk: async () => {
        await settingsApi.permanentDelete(bizType, id)
        message.success('已永久删除')
        fetch()
      },
    })
  }

  return (
    <div className="pb-6">
      <div className="flex items-center gap-3 mb-3">
        <Select allowClear placeholder="记录类型" value={filterType} onChange={setFilterType}
          options={Object.entries(BIZ_TYPE_MAP).map(([v, l]) => ({ value: v, label: l }))}
          style={{ width: 120 }} size="small" />
        <Input.Search placeholder="搜索名称" size="small" style={{ width: 200 }}
          value={keyword} onChange={(e) => setKeyword(e.target.value)}
          onSearch={() => { fetch(1); setPage(1) }} allowClear />
      </div>
      <Table rowKey="id" dataSource={items} size="small" loading={loading}
        pagination={{ current: page, total, pageSize: 20, onChange: (p) => { setPage(p); fetch(p) }, showTotal: (t) => `共 ${t} 条` }}
        columns={[
          { title: '类型', dataIndex: 'biz_type', width: 80, render: (v: string) => <Tag>{BIZ_TYPE_MAP[v] || v}</Tag> },
          { title: '名称', dataIndex: 'name', width: 200 },
          { title: '编码', dataIndex: 'code', width: 150 },
          { title: '删除时间', dataIndex: 'deleted_at', width: 180, render: (v: string) => v ? new Date(v).toLocaleString('zh-CN') : '-' },
          { title: '操作', width: 160, render: (_: unknown, r: any) => (
            <Space size="small">
              <a className="text-primary text-sm font-bold" onClick={() => handleRestore(r.biz_type, r.id)}>恢复</a>
              <a className="text-red-500 text-sm font-bold" onClick={() => handlePermanentDelete(r.biz_type, r.id)}>永久删除</a>
            </Space>
          )},
        ]}
      />
    </div>
  )
}
