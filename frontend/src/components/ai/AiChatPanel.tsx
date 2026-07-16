// 可复用 AI 对话面板(流式 + RAG 引用)。用于知识库"AI 问答"与全局助手浮窗。
import { useRef, useState, useEffect } from 'react'
import { Input, Button, Switch, Tag, Tooltip } from 'antd'
import { SendOutlined, StopOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons'
import { streamAssistant, type AssistantSource, type AssistantMessage } from '@/api/aiStream'

interface ChatTurn {
  role: 'user' | 'assistant'
  content: string
  sources?: AssistantSource[]
  streaming?: boolean
  error?: boolean
}

interface Props {
  defaultUseKnowledge?: boolean
  showKnowledgeToggle?: boolean
  height?: number | string
  placeholder?: string
  welcome?: string
  onOpenDoc?: (documentId: string) => void
}

export default function AiChatPanel({
  defaultUseKnowledge = true,
  showKnowledgeToggle = true,
  height = 460,
  placeholder = '输入问题，例如：报价审批的流程是怎样的？',
  welcome = '你好，我是企业智能助手。可以问我知识库里的制度、流程等问题。',
  onOpenDoc,
}: Props) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [input, setInput] = useState('')
  const [useKnowledge, setUseKnowledge] = useState(defaultUseKnowledge)
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [turns])

  const send = async () => {
    const q = input.trim()
    if (!q || streaming) return
    setInput('')
    const history: AssistantMessage[] = turns
      .filter((t) => !t.error && t.content)
      .map((t) => ({ role: t.role, content: t.content }))
    setTurns((prev) => [...prev, { role: 'user', content: q }, { role: 'assistant', content: '', streaming: true }])
    setStreaming(true)
    const ctrl = new AbortController()
    abortRef.current = ctrl

    const patchLast = (fn: (t: ChatTurn) => ChatTurn) =>
      setTurns((prev) => {
        const next = [...prev]
        next[next.length - 1] = fn(next[next.length - 1])
        return next
      })

    await streamAssistant(
      { question: q, history, use_knowledge: useKnowledge },
      {
        onSources: (s) => patchLast((t) => ({ ...t, sources: s })),
        onDelta: (d) => patchLast((t) => ({ ...t, content: t.content + d })),
        onError: (e) => patchLast((t) => ({ ...t, content: t.content || `⚠️ ${e}`, error: true, streaming: false })),
        onDone: () => patchLast((t) => ({ ...t, streaming: false })),
      },
      ctrl.signal,
    )
    setStreaming(false)
    abortRef.current = null
  }

  const stop = () => { abortRef.current?.abort(); setStreaming(false); setTurns((p) => { const n = [...p]; if (n.length) n[n.length - 1] = { ...n[n.length - 1], streaming: false }; return n }) }

  return (
    <div className="flex flex-col" style={{ height }}>
      <div ref={scrollRef} className="flex-1 overflow-y-auto space-y-4 p-1">
        {turns.length === 0 && (
          <div className="text-center text-slate-400 text-sm pt-10 px-6">
            <RobotOutlined style={{ fontSize: 28 }} className="text-indigo-300 mb-2" />
            <p>{welcome}</p>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`flex gap-2 ${t.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${t.role === 'user' ? 'bg-primary/10 text-primary' : 'bg-indigo-50 text-indigo-500'}`}>
              {t.role === 'user' ? <UserOutlined /> : <RobotOutlined />}
            </div>
            <div className={`max-w-[82%] ${t.role === 'user' ? 'items-end' : ''}`}>
              <div className={`rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap break-words ${
                t.role === 'user' ? 'bg-primary text-white' : t.error ? 'bg-rose-50 text-rose-600' : 'bg-slate-100 text-slate-800'}`}>
                {t.content || (t.streaming ? '思考中…' : '')}
                {t.streaming && t.content && <span className="inline-block w-1.5 h-4 align-middle bg-slate-400 ml-0.5 animate-pulse" />}
              </div>
              {t.sources && t.sources.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {t.sources.map((s) => (
                    <Tooltip key={s.index} title={s.score != null ? `相关度 ${s.score}` : ''}>
                      <Tag
                        className="cursor-pointer !mr-0"
                        color="blue"
                        onClick={() => onOpenDoc?.(s.document_id)}
                      >
                        [{s.index}] {s.doc_title}
                      </Tag>
                    </Tooltip>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-slate-100 pt-2 mt-1">
        {showKnowledgeToggle && (
          <div className="flex items-center gap-2 mb-1.5 px-1">
            <Switch size="small" checked={useKnowledge} onChange={setUseKnowledge} />
            <span className="text-xs text-slate-500">查知识库（关闭则纯模型对话）</span>
          </div>
        )}
        <div className="flex gap-2 items-end">
          <Input.TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={placeholder}
            autoSize={{ minRows: 1, maxRows: 4 }}
            onPressEnter={(e) => { if (!e.shiftKey) { e.preventDefault(); send() } }}
            disabled={streaming}
          />
          {streaming ? (
            <Button danger icon={<StopOutlined />} onClick={stop}>停止</Button>
          ) : (
            <Button type="primary" icon={<SendOutlined />} onClick={send} disabled={!input.trim()}>发送</Button>
          )}
        </div>
      </div>
    </div>
  )
}
