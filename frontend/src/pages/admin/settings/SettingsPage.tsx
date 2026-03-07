import { useState, useEffect } from 'react'
import { Tabs, Table, Button, Modal, Input, InputNumber, Select, Switch, Space, Progress, message } from 'antd'
import { PlusOutlined, DeleteOutlined, EditOutlined, CloudDownloadOutlined, SafetyCertificateOutlined } from '@ant-design/icons'
import { settingsApi } from '@/api/settings'
import { downloadFile } from '@/utils/download'
import { usePageTitle } from '@/hooks/usePageTitle'
import ApprovalPolicyModal from './ApprovalPolicyModal'

const { TextArea } = Input

interface StageConfig { id: string; stage_code: string; name: string; gate_rules_json?: Record<string, unknown>[]; enabled: boolean }
interface MarginPolicy { id: string; policy_code: string; redline_rate: number; action: string; scope_json?: Record<string, unknown>; enabled: boolean }
interface AiPolicy { id: string; task_type: string; model_route_json?: Record<string, unknown>; budget_json?: Record<string, unknown>; enabled: boolean }
interface Integration { id: string; system_code: string; name: string; base_url: string; auth_type: string; status: string }
interface FeatureToggle { id: string; feature_code: string; enabled: boolean; config_json?: Record<string, unknown> }
interface AiBudget { id: string; period: string; budget_cost?: number; used_cost?: number; budget_tokens?: number; used_tokens?: number; hard_limit: boolean }
interface ApprovalPolicyItem { id: string; biz_type: string; name: string; condition_json?: Record<string, unknown>; approver_rules_json?: Record<string, unknown>; approval_mode: string; sla_hours?: number; escalation_json?: Record<string, unknown>[]; priority: number; enabled: boolean }
interface DocTemplateItem { id: string; doc_type: string; name: string; description?: string; content_json?: Record<string, unknown>; is_default: boolean; created_by_name?: string; created_at: string }
interface EmailTemplateItem { id: string; code: string; name: string; subject?: string; body_html?: string; variables_json?: unknown; enabled: boolean; created_at: string }
interface CustomFieldItem { id: string; entity_type: string; field_key: string; field_label: string; field_type: string; options_json?: string[]; required: boolean; sort_order: number; enabled: boolean }

function JsonCell({ value }: { value: unknown }) {
  if (!value) return <span className="text-slate-300">-</span>
  return <pre className="text-xs text-slate-600 whitespace-pre-wrap max-w-xs">{JSON.stringify(value, null, 2)}</pre>
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
  const [docTemplates, setDocTemplates] = useState<DocTemplateItem[]>([])
  const [emailTemplates, setEmailTemplates] = useState<EmailTemplateItem[]>([])
  const [customFields, setCustomFields] = useState<CustomFieldItem[]>([])
  const [backupStats, setBackupStats] = useState<Record<string, number>>({})
  const [backupLoading, setBackupLoading] = useState(false)
  const [auditResult, setAuditResult] = useState<{ total_checked: number; no_hash: number; tampered_count: number; tampered: { id: string; created_at: string; summary: string }[] } | null>(null)
  const [auditLoading, setAuditLoading] = useState(false)

  // Custom field
  const [cfModal, setCfModal] = useState(false)
  const [cfEditingId, setCfEditingId] = useState<string | null>(null)
  const defaultCfForm = { entity_type: 'customer', field_key: '', field_label: '', field_type: 'text', options_json: '', required: false, sort_order: 0, enabled: true }
  const [cfForm, setCfForm] = useState(defaultCfForm)

  // Doc template
  const [dtModal, setDtModal] = useState(false)
  const [dtEditingId, setDtEditingId] = useState<string | null>(null)
  const defaultDtForm = { doc_type: 'quote' as string, name: '', description: '', content_json: '', is_default: false }
  const [dtForm, setDtForm] = useState(defaultDtForm)

  // Email template
  const [etModal, setEtModal] = useState(false)
  const [etEditingId, setEtEditingId] = useState<string | null>(null)
  const defaultEtForm = { code: '', name: '', subject: '', body_html: '', variables_json: '', enabled: true }
  const [etForm, setEtForm] = useState(defaultEtForm)

  // Stage edit
  const [stageModal, setStageModal] = useState(false)
  const [stageForm, setStageForm] = useState({ stage_code: '', name: '', gate_rules_json: '' })

  // Margin create
  const [marginModal, setMarginModal] = useState(false)
  const [marginForm, setMarginForm] = useState({ policy_code: '', redline_rate: 0.2, action: 'warn' })

  // Integration create
  const [intModal, setIntModal] = useState(false)
  const [intForm, setIntForm] = useState({ system_code: '', name: '', base_url: '', auth_type: 'apikey' })

  // Approval policy create/edit
  const [apModal, setApModal] = useState(false)
  const [apEditingId, setApEditingId] = useState<string | null>(null)
  const defaultApForm = { biz_type: 'quote_version', name: '', condition_json: '', approver_rules_json: '', approval_mode: 'sequential', sla_hours: undefined as number | undefined, escalation_json: '' }
  const [apForm, setApForm] = useState(defaultApForm)

  const currentPeriod = new Date().toISOString().slice(0, 7)

  const fetchAll = () => {
    settingsApi.listStages().then((r: { data: StageConfig[] }) => r.data && setStages(r.data)).catch(() => {})
    settingsApi.listMargins().then((r: { data: MarginPolicy[] }) => r.data && setMargins(r.data)).catch(() => {})
    settingsApi.listAiPolicies().then((r: { data: AiPolicy[] }) => r.data && setAiPolicies(r.data)).catch(() => {})
    settingsApi.listIntegrations().then((r: { data: Integration[] }) => r.data && setIntegrations(r.data)).catch(() => {})
    settingsApi.listFeatures().then((r: { data: FeatureToggle[] }) => r.data && setFeatures(r.data)).catch(() => {})
    settingsApi.getAiBudget(currentPeriod).then((r: { data: AiBudget | null }) => r.data && setAiBudget(r.data)).catch(() => {})
    settingsApi.listApprovalPolicies().then((r: { data: ApprovalPolicyItem[] }) => r.data && setApprovalPolicies(r.data)).catch(() => {})
    settingsApi.listDocTemplates().then((r: { data: DocTemplateItem[] }) => r.data && setDocTemplates(r.data)).catch(() => {})
    settingsApi.listEmailTemplates().then((r: { data: EmailTemplateItem[] }) => r.data && setEmailTemplates(r.data)).catch(() => {})
    settingsApi.listCustomFields().then((r: { data: CustomFieldItem[] }) => r.data && setCustomFields(r.data)).catch(() => {})
    settingsApi.backupStats().then((r: { data: Record<string, number> }) => r.data && setBackupStats(r.data)).catch(() => {})
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

  const handleSaveStage = async () => {
    let gateJson = null
    if (stageForm.gate_rules_json) {
      try { gateJson = JSON.parse(stageForm.gate_rules_json) } catch { message.error('Gate规则JSON格式错误'); return }
    }
    try {
      await settingsApi.updateStage(stageForm.stage_code, {
        name: stageForm.name, gate_rules_json: gateJson,
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

  const handleCreateInt = async () => {
    try {
      await settingsApi.createIntegration(intForm)
      message.success('集成端点已创建')
      setIntModal(false)
      setIntForm({ system_code: '', name: '', base_url: '', auth_type: 'apikey' })
      fetchAll()
    } catch {
      message.error('创建集成端点失败')
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

  const handleSaveDt = async () => {
    let contentJson = null
    if (dtForm.content_json) {
      try { contentJson = JSON.parse(dtForm.content_json) } catch { message.error('内容JSON格式错误'); return }
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
    let varsJson = null
    if (etForm.variables_json) {
      try { varsJson = JSON.parse(etForm.variables_json) } catch { message.error('变量JSON格式错误'); return }
    }
    try {
      const payload = { code: etForm.code, name: etForm.name, subject: etForm.subject || undefined, body_html: etForm.body_html || undefined, variables_json: varsJson, enabled: etForm.enabled }
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
    let optionsJson = null
    if (cfForm.options_json) {
      try { optionsJson = JSON.parse(cfForm.options_json) } catch { message.error('选项JSON格式错误'); return }
    }
    try {
      const payload = { ...cfForm, options_json: optionsJson }
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
                    setStageForm({ stage_code: '', name: '', gate_rules_json: '' }); setStageModal(true)
                  }}>配置阶段</Button>
                </div>
                <Table rowKey="id" dataSource={stages} size="small" pagination={false} columns={[
                  { title: '阶段', dataIndex: 'stage_code', width: 80, render: (v: string) => <span className="font-mono font-bold text-primary">{v}</span> },
                  { title: '名称', dataIndex: 'name', width: 120 },
                  { title: 'Gate规则', dataIndex: 'gate_rules_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '启用', dataIndex: 'enabled', width: 80, render: (v: boolean) => v ? <span className="text-emerald-500 font-bold">是</span> : <span className="text-slate-400">否</span> },
                  { title: '', width: 80, render: (_: unknown, r: StageConfig) => (
                    <a className="text-primary text-xs font-bold" onClick={() => {
                      setStageForm({ stage_code: r.stage_code, name: r.name, gate_rules_json: r.gate_rules_json ? JSON.stringify(r.gate_rules_json, null, 2) : '' })
                      setStageModal(true)
                    }}>编辑</a>
                  )},
                ]} />
              </div>
            ),
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
                    quote_version: '报价审批', contract_version: '合同审批', change_request: '变更审批',
                  }[v] || v) },
                  { title: '策略名称', dataIndex: 'name', width: 150 },
                  { title: '触发条件', dataIndex: 'condition_json', render: (v: unknown) => <JsonCell value={v} /> },
                  { title: '审批人规则', dataIndex: 'approver_rules_json', render: (v: unknown) => <JsonCell value={v} /> },
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
                      <a className="text-primary text-xs font-bold" onClick={() => openApEdit(r)}>编辑</a>
                      <a className="text-rose-500 text-xs font-bold" onClick={async () => {
                        try {
                          await settingsApi.deleteApprovalPolicy(r.id)
                          message.success('已删除')
                          fetchAll()
                        } catch { message.error('删除失败') }
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
                      <a className="text-primary text-xs font-bold" onClick={() => {
                        setDtEditingId(r.id)
                        setDtForm({ doc_type: r.doc_type, name: r.name, description: r.description || '',
                          content_json: r.content_json ? JSON.stringify(r.content_json, null, 2) : '', is_default: r.is_default })
                        setDtModal(true)
                      }}>编辑</a>
                      <a className="text-rose-500 text-xs font-bold" onClick={async () => {
                        try { await settingsApi.deleteDocTemplate(r.id); message.success('已删除'); fetchAll() } catch { message.error('删除失败') }
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
                  { title: '编码', dataIndex: 'code', width: 140, render: (v: string) => <span className="font-mono text-xs">{v}</span> },
                  { title: '名称', dataIndex: 'name', width: 160 },
                  { title: '主题', dataIndex: 'subject', ellipsis: true },
                  { title: '启用', dataIndex: 'enabled', width: 60, render: (v: boolean, r: EmailTemplateItem) => (
                    <Switch size="small" checked={v} onChange={async (checked) => {
                      try { await settingsApi.updateEmailTemplate(r.id, { code: r.code, name: r.name, enabled: checked }); fetchAll() } catch { message.error('更新失败') }
                    }} />
                  )},
                  { title: '', width: 100, render: (_: unknown, r: EmailTemplateItem) => (
                    <Space size="middle">
                      <a className="text-primary text-xs font-bold" onClick={() => {
                        setEtEditingId(r.id)
                        setEtForm({ code: r.code, name: r.name, subject: r.subject || '',
                          body_html: r.body_html || '', variables_json: r.variables_json ? JSON.stringify(r.variables_json, null, 2) : '',
                          enabled: r.enabled })
                        setEtModal(true)
                      }}>编辑</a>
                      <a className="text-rose-500 text-xs font-bold" onClick={async () => {
                        try { await settingsApi.deleteEmailTemplate(r.id); message.success('已删除'); fetchAll() } catch { message.error('删除失败') }
                      }}>删除</a>
                    </Space>
                  )},
                ]} />
                {emailTemplates.length === 0 && <div className="text-center py-8 text-slate-400 text-sm">暂无邮件模板</div>}
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
                  <Button type="primary" size="small" icon={<PlusOutlined />} onClick={() => setIntModal(true)}>新增集成</Button>
                </div>
                <Table rowKey="id" dataSource={integrations} size="small" pagination={false} columns={[
                  { title: '系统', dataIndex: 'system_code', width: 120 },
                  { title: '名称', dataIndex: 'name', width: 150 },
                  { title: 'URL', dataIndex: 'base_url', ellipsis: true },
                  { title: '认证', dataIndex: 'auth_type', width: 100 },
                  { title: '状态', dataIndex: 'status', width: 80 },
                  { title: '', width: 80, render: (_: unknown, r: Integration) => (
                    <a className="text-rose-500 text-xs font-bold" onClick={async () => {
                      try {
                        await settingsApi.deleteIntegration(r.id)
                        message.success('已删除')
                        fetchAll()
                      } catch {
                        message.error('删除失败')
                      }
                    }}>删除</a>
                  )},
                ]} />
              </div>
            ),
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
                    <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">费用预算 ({currentPeriod})</div>
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
                    <div className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Token 配额 ({currentPeriod})</div>
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
                    <span className="text-xs text-slate-500">
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
                        setCfForm({ entity_type: r.entity_type, field_key: r.field_key, field_label: r.field_label, field_type: r.field_type, options_json: r.options_json ? JSON.stringify(r.options_json) : '', required: r.required, sort_order: r.sort_order, enabled: r.enabled })
                        setCfModal(true)
                      }} className="text-primary text-xs font-bold">编辑</a>
                      <a className="text-rose-500 text-xs font-bold" onClick={async () => {
                        await settingsApi.deleteCustomField(r.id); message.success('已删除'); fetchAll()
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
                  <Button type="primary" icon={<CloudDownloadOutlined />} loading={backupLoading} onClick={() => {
                    setBackupLoading(true)
                    downloadFile(settingsApi.backupDownloadUrl(), `backup_${new Date().toISOString().slice(0, 10)}.json`)
                    setTimeout(() => setBackupLoading(false), 3000)
                  }}>下载备份</Button>
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
                        <span className="text-xs text-slate-500">{labelMap[table] || table}</span>
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
                        <div className="text-xs text-slate-500 mt-1">检查总数</div>
                      </div>
                      <div className={`rounded-xl p-4 border text-center ${auditResult.tampered_count === 0 ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
                        <div className={`text-2xl font-black ${auditResult.tampered_count === 0 ? 'text-emerald-700' : 'text-red-600'}`}>{auditResult.tampered_count}</div>
                        <div className={`text-xs mt-1 ${auditResult.tampered_count === 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                          {auditResult.tampered_count === 0 ? '无异常' : '疑似篡改'}
                        </div>
                      </div>
                      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 text-center">
                        <div className="text-2xl font-black text-slate-900">{auditResult.no_hash}</div>
                        <div className="text-xs text-slate-500 mt-1">无哈希记录</div>
                      </div>
                    </div>

                    {auditResult.tampered_count > 0 && (
                      <div>
                        <h4 className="text-sm font-bold text-red-600 mb-2">异常记录 (前50条)</h4>
                        <Table rowKey="id" dataSource={auditResult.tampered} size="small" pagination={false} columns={[
                          { title: 'ID', dataIndex: 'id', width: 280, render: (v: string) => <span className="font-mono text-xs">{v}</span> },
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
      <Modal title="配置阶段Gate" open={stageModal} onOk={handleSaveStage} onCancel={() => setStageModal(false)}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">阶段代码</label>
            <Input value={stageForm.stage_code} onChange={(e) => setStageForm({ ...stageForm, stage_code: e.target.value })} placeholder="S1" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">名称</label>
            <Input value={stageForm.name} onChange={(e) => setStageForm({ ...stageForm, name: e.target.value })} placeholder="线索确认" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">Gate规则 (JSON)</label>
            <TextArea rows={6} value={stageForm.gate_rules_json} onChange={(e) => setStageForm({ ...stageForm, gate_rules_json: e.target.value })}
              placeholder='[{"code":"HAS_CUSTOMER","name":"已关联客户","message":"请先关联客户"}]' />
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
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">内容 (JSON)</label>
            <TextArea rows={8} value={dtForm.content_json} onChange={(e) => setDtForm({ ...dtForm, content_json: e.target.value })}
              placeholder={dtForm.doc_type === 'quote'
                ? '{"title":"标准报价","tax_rate":0.13,"validity_days":30,"terms_summary_json":{"payment":"预付30%"},"lines":[{"item_name":"示例","qty":1,"unit":"台","unit_price":10000}]}'
                : '{"title":"标准合同","payment_terms_json":{"method":"分期"},"delivery_terms_json":{"address":"客户指定"},"key_clauses_json":["验收条款","质保条款"]}'} />
          </div>
          <div className="flex items-center gap-3">
            <Switch checked={dtForm.is_default} onChange={(v) => setDtForm({ ...dtForm, is_default: v })} />
            <span className="text-sm text-slate-700">设为默认模板</span>
          </div>
        </div>
      </Modal>

      {/* Email Template Modal */}
      <Modal title={etEditingId ? '编辑邮件模板' : '新增邮件模板'} open={etModal} onOk={handleSaveEt} onCancel={() => { setEtModal(false); setEtEditingId(null) }} width={600}>
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
            <label className="text-sm font-medium text-slate-700 mb-1 block">邮件内容 (HTML)</label>
            <TextArea rows={8} value={etForm.body_html} onChange={(e) => setEtForm({ ...etForm, body_html: e.target.value })}
              placeholder="<p>{{user_name}} 你好，</p><p>客户 {{customer_name}} 已 {{days}} 天未跟进。</p>" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">变量定义 (JSON)</label>
            <TextArea rows={3} value={etForm.variables_json} onChange={(e) => setEtForm({ ...etForm, variables_json: e.target.value })}
              placeholder='[{"name":"customer_name","label":"客户名称"},{"name":"days","label":"天数"}]' />
          </div>
          <div className="flex items-center gap-3">
            <Switch checked={etForm.enabled} onChange={(v) => setEtForm({ ...etForm, enabled: v })} />
            <span className="text-sm text-slate-700">启用</span>
          </div>
        </div>
      </Modal>

      {/* Integration Modal */}
      <Modal title="新增集成端点" open={intModal} onOk={handleCreateInt} onCancel={() => setIntModal(false)}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">系统代码</label>
            <Input value={intForm.system_code} onChange={(e) => setIntForm({ ...intForm, system_code: e.target.value })} placeholder="erp_k3" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">名称</label>
            <Input value={intForm.name} onChange={(e) => setIntForm({ ...intForm, name: e.target.value })} placeholder="金蝶K3" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">Base URL</label>
            <Input value={intForm.base_url} onChange={(e) => setIntForm({ ...intForm, base_url: e.target.value })} placeholder="https://erp.example.com/api" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">认证方式</label>
            <Select className="w-full" value={intForm.auth_type} onChange={(v) => setIntForm({ ...intForm, auth_type: v })}
              options={[{ value: 'apikey', label: 'API Key' }, { value: 'oauth2', label: 'OAuth2' }, { value: 'basic', label: 'Basic Auth' }]} />
          </div>
        </div>
      </Modal>

      {/* Custom Field Modal */}
      <Modal title={cfEditingId ? '编辑自定义字段' : '新增自定义字段'} open={cfModal} onOk={handleSaveCf}
        onCancel={() => { setCfModal(false); setCfEditingId(null) }} width={520}>
        <div className="space-y-4 py-2">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">实体类型</label>
            <Select className="w-full" value={cfForm.entity_type} onChange={(v) => setCfForm({ ...cfForm, entity_type: v })}
              options={Object.entries(entityTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">字段Key</label>
            <Input value={cfForm.field_key} onChange={(e) => setCfForm({ ...cfForm, field_key: e.target.value })} placeholder="custom_region" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">显示标签</label>
            <Input value={cfForm.field_label} onChange={(e) => setCfForm({ ...cfForm, field_label: e.target.value })} placeholder="所在区域" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">字段类型</label>
            <Select className="w-full" value={cfForm.field_type} onChange={(v) => setCfForm({ ...cfForm, field_type: v })}
              options={Object.entries(fieldTypeLabels).map(([k, v]) => ({ value: k, label: v }))} />
          </div>
          {(cfForm.field_type === 'select' || cfForm.field_type === 'multiselect') && (
            <div>
              <label className="text-sm font-medium text-slate-700 mb-1 block">选项 (JSON数组)</label>
              <TextArea rows={3} value={cfForm.options_json} onChange={(e) => setCfForm({ ...cfForm, options_json: e.target.value })}
                placeholder='["选项1", "选项2", "选项3"]' />
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
