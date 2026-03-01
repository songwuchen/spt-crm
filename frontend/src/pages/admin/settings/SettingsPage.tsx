import { useState, useEffect } from 'react'
import { Tabs, Table, Button, Modal, Input, InputNumber, Select, Switch, Space, Progress, message } from 'antd'
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { settingsApi } from '@/api/settings'
import { usePageTitle } from '@/hooks/usePageTitle'

const { TextArea } = Input

interface StageConfig { id: string; stage_code: string; name: string; gate_rules_json?: Record<string, unknown>[]; enabled: boolean }
interface MarginPolicy { id: string; policy_code: string; redline_rate: number; action: string; scope_json?: Record<string, unknown>; enabled: boolean }
interface AiPolicy { id: string; task_type: string; model_route_json?: Record<string, unknown>; budget_json?: Record<string, unknown>; enabled: boolean }
interface Integration { id: string; system_code: string; name: string; base_url: string; auth_type: string; status: string }
interface FeatureToggle { id: string; feature_code: string; enabled: boolean; config_json?: Record<string, unknown> }
interface AiBudget { id: string; period: string; budget_cost?: number; used_cost?: number; budget_tokens?: number; used_tokens?: number; hard_limit: boolean }

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

  // Stage edit
  const [stageModal, setStageModal] = useState(false)
  const [stageForm, setStageForm] = useState({ stage_code: '', name: '', gate_rules_json: '' })

  // Margin create
  const [marginModal, setMarginModal] = useState(false)
  const [marginForm, setMarginForm] = useState({ policy_code: '', redline_rate: 0.2, action: 'warn' })

  // Integration create
  const [intModal, setIntModal] = useState(false)
  const [intForm, setIntForm] = useState({ system_code: '', name: '', base_url: '', auth_type: 'apikey' })

  const currentPeriod = new Date().toISOString().slice(0, 7)

  const fetchAll = () => {
    settingsApi.listStages().then((r: { data: StageConfig[] }) => r.data && setStages(r.data)).catch(() => {})
    settingsApi.listMargins().then((r: { data: MarginPolicy[] }) => r.data && setMargins(r.data)).catch(() => {})
    settingsApi.listAiPolicies().then((r: { data: AiPolicy[] }) => r.data && setAiPolicies(r.data)).catch(() => {})
    settingsApi.listIntegrations().then((r: { data: Integration[] }) => r.data && setIntegrations(r.data)).catch(() => {})
    settingsApi.listFeatures().then((r: { data: FeatureToggle[] }) => r.data && setFeatures(r.data)).catch(() => {})
    settingsApi.getAiBudget(currentPeriod).then((r: { data: AiBudget | null }) => r.data && setAiBudget(r.data)).catch(() => {})
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

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">系统配置</h1>
        <p className="text-sm text-slate-500 mt-1">管理阶段Gate、毛利红线、AI策略、集成端点和功能开关</p>
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
    </div>
  )
}
