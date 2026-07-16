import { useEffect, useState } from 'react'
import { Select, Input, Switch, Button, Space, Alert, AutoComplete, message } from 'antd'
import { settingsApi } from '@/api/settings'

interface ProviderCfg { base_url?: string; model?: string; api_key?: string; dimensions?: number }
interface ChatPreset { label: string; base_url: string; models: string[]; api: string; needs_key: boolean }
interface EmbPreset { label: string; base_url: string; models: string[]; default_dimensions: number; needs_key: boolean }

interface AiSettings {
  chat_provider: string
  chat: ProviderCfg
  embedding_provider: string
  embedding: ProviderCfg
  enabled: boolean
  chat_providers: Record<string, ChatPreset>
  embedding_providers: Record<string, EmbPreset>
}

const SECRET_PLACEHOLDER = '已配置，如需修改请重新输入'

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div>
      <label className="text-sm font-medium text-slate-700 mb-1 block">{label}</label>
      {children}
      {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
    </div>
  )
}

export default function AiModelTab() {
  const [enabled, setEnabled] = useState(false)
  const [chatProvider, setChatProvider] = useState('mock')
  const [chat, setChat] = useState<ProviderCfg>({})
  const [chatHasKey, setChatHasKey] = useState(false)
  const [embProvider, setEmbProvider] = useState('none')
  const [emb, setEmb] = useState<ProviderCfg>({})
  const [embHasKey, setEmbHasKey] = useState(false)
  const [chatPresets, setChatPresets] = useState<Record<string, ChatPreset>>({})
  const [embPresets, setEmbPresets] = useState<Record<string, EmbPreset>>({})
  const [saving, setSaving] = useState(false)
  const [testingChat, setTestingChat] = useState(false)
  const [testingEmb, setTestingEmb] = useState(false)
  const [dirty, setDirty] = useState(false)

  const load = () => {
    settingsApi.getAiSettings().then((r: { data: AiSettings }) => {
      const d = r.data
      if (!d) return
      setEnabled(!!d.enabled)
      setChatProvider(d.chat_provider || 'mock')
      setChatHasKey(d.chat?.api_key === '***')
      setChat({ ...d.chat, api_key: '' })
      setEmbProvider(d.embedding_provider || 'none')
      setEmbHasKey(d.embedding?.api_key === '***')
      setEmb({ ...d.embedding, api_key: '' })
      setChatPresets(d.chat_providers || {})
      setEmbPresets(d.embedding_providers || {})
      setDirty(false)
    }).catch(() => {})
  }
  useEffect(() => { load() }, [])

  const onChatProvider = (v: string) => {
    setChatProvider(v)
    const preset = chatPresets[v]
    // 切换供应商时用预设默认填充 base_url / model（自定义则保留）
    if (preset && v !== 'custom') {
      setChat((c) => ({ ...c, base_url: preset.base_url, model: preset.models[0] || c.model }))
    }
    setDirty(true)
  }
  const onEmbProvider = (v: string) => {
    setEmbProvider(v)
    const preset = embPresets[v]
    if (preset && v !== 'custom' && v !== 'none') {
      setEmb((c) => ({ ...c, base_url: preset.base_url, model: preset.models[0] || c.model }))
    }
    setDirty(true)
  }
  const updChat = (patch: Partial<ProviderCfg>) => { setChat({ ...chat, ...patch }); setDirty(true) }
  const updEmb = (patch: Partial<ProviderCfg>) => { setEmb({ ...emb, ...patch }); setDirty(true) }

  const buildPayload = () => {
    const chatBlock: ProviderCfg = { base_url: chat.base_url, model: chat.model }
    if (chat.api_key) chatBlock.api_key = chat.api_key
    const embBlock: ProviderCfg = { base_url: emb.base_url, model: emb.model }
    if (emb.api_key) embBlock.api_key = emb.api_key
    return {
      enabled,
      chat_provider: chatProvider,
      chat: chatBlock,
      embedding_provider: embProvider,
      embedding: embBlock,
    }
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await settingsApi.updateAiSettings(buildPayload())
      message.success('AI 模型配置已保存')
      load()
    } catch { message.error('保存失败') }
    finally { setSaving(false) }
  }

  const handleTestChat = async () => {
    if (dirty) { message.info('请先保存配置再测试连接'); return }
    setTestingChat(true)
    try {
      const res = await settingsApi.testAiChat() as { data: { connected: boolean; error?: string } }
      if (res.data?.connected) message.success('对话模型连接成功')
      else message.warning(`连接失败：${res.data?.error || '无法连接'}`)
    } catch { message.error('测试失败') }
    finally { setTestingChat(false) }
  }
  const handleTestEmb = async () => {
    if (dirty) { message.info('请先保存配置再测试连接'); return }
    setTestingEmb(true)
    try {
      const res = await settingsApi.testAiEmbedding() as { data: { connected: boolean; error?: string } }
      if (res.data?.connected) message.success('嵌入模型连接成功')
      else message.warning(`连接失败：${res.data?.error || '无法连接'}`)
    } catch { message.error('测试失败') }
    finally { setTestingEmb(false) }
  }

  const chatOpts = Object.entries(chatPresets).map(([v, p]) => ({ value: v, label: p.label }))
  const embOpts = Object.entries(embPresets).map(([v, p]) => ({ value: v, label: p.label }))
  const chatModelOpts = (chatPresets[chatProvider]?.models || []).map((m) => ({ value: m }))
  const embModelOpts = (embPresets[embProvider]?.models || []).map((m) => ({ value: m }))
  const chatNeedsKey = chatProvider !== 'mock'
  const embNeedsKey = embProvider !== 'none'

  return (
    <div className="pb-6 max-w-xl">
      <p className="text-sm text-slate-500 mb-4">
        配置对话/分析模型与向量嵌入模型。支持通义千问、DeepSeek、OpenAI、Claude 及任意 OpenAI 兼容接口。
        密钥使用 AES 加密存储，保存后不再明文返回。未启用时 AI 分析使用内置模拟结果。
      </p>

      <div className="space-y-5">
        <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg border border-slate-100">
          <div>
            <div className="text-sm font-medium text-slate-700">启用 AI 能力</div>
            <div className="text-xs text-slate-400">关闭时，风险分析/画像/知识库均使用内置模拟或关键词检索</div>
          </div>
          <Switch checked={enabled} onChange={(v) => { setEnabled(v); setDirty(true) }} />
        </div>

        {/* 对话模型 */}
        <div className="space-y-3 p-4 bg-white rounded-lg border border-slate-200">
          <div className="text-sm font-semibold text-slate-800">对话 / 分析模型</div>
          <Field label="供应商">
            <Select value={chatProvider} style={{ width: '100%' }} options={chatOpts} onChange={onChatProvider} />
          </Field>
          {chatProvider === 'mock' ? (
            <Alert type="info" showIcon message="使用内置模拟结果，不调用外部模型，无需配置。" />
          ) : (
            <>
              <Field label="接口地址 Base URL" hint="OpenAI 兼容端点，通常无需修改预设值">
                <Input value={chat.base_url || ''} placeholder="https://..."
                  onChange={(e) => updChat({ base_url: e.target.value })} />
              </Field>
              <Field label="模型">
                <AutoComplete style={{ width: '100%' }} value={chat.model || ''} options={chatModelOpts}
                  placeholder="如 qwen-plus / deepseek-chat"
                  onChange={(v) => updChat({ model: v })} filterOption={(i, o) => (o?.value as string ?? '').includes(i)} />
              </Field>
              <Field label="API Key">
                <Input.Password value={chat.api_key || ''} autoComplete="new-password"
                  placeholder={chatHasKey ? SECRET_PLACEHOLDER : 'sk-...'}
                  onChange={(e) => updChat({ api_key: e.target.value })} />
              </Field>
            </>
          )}
        </div>

        {/* 嵌入模型 */}
        <div className="space-y-3 p-4 bg-white rounded-lg border border-slate-200">
          <div className="text-sm font-semibold text-slate-800">向量嵌入模型（知识库语义检索）</div>
          <Field label="供应商">
            <Select value={embProvider} style={{ width: '100%' }} options={embOpts} onChange={onEmbProvider} />
          </Field>
          {embProvider === 'none' ? (
            <Alert type="info" showIcon message="未启用嵌入模型，知识库使用关键词匹配检索。" />
          ) : (
            <>
              <Field label="接口地址 Base URL">
                <Input value={emb.base_url || ''} placeholder="https://..."
                  onChange={(e) => updEmb({ base_url: e.target.value })} />
              </Field>
              <Field label="嵌入模型" hint="统一输出 1024 维向量（与向量库列维度对齐）">
                <AutoComplete style={{ width: '100%' }} value={emb.model || ''} options={embModelOpts}
                  placeholder="如 text-embedding-v3"
                  onChange={(v) => updEmb({ model: v })} filterOption={(i, o) => (o?.value as string ?? '').includes(i)} />
              </Field>
              <Field label="API Key">
                <Input.Password value={emb.api_key || ''} autoComplete="new-password"
                  placeholder={embHasKey ? SECRET_PLACEHOLDER : 'sk-...'}
                  onChange={(e) => updEmb({ api_key: e.target.value })} />
              </Field>
            </>
          )}
        </div>

        <Space>
          <Button type="primary" loading={saving} onClick={handleSave}>保存配置</Button>
          {chatNeedsKey && <Button loading={testingChat} onClick={handleTestChat}>测试对话模型</Button>}
          {embNeedsKey && <Button loading={testingEmb} onClick={handleTestEmb}>测试嵌入模型</Button>}
        </Space>
      </div>
    </div>
  )
}
