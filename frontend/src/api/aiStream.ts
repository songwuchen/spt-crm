// AI 助手流式(SSE)客户端。EventSource 不支持 POST/自定义头,故用 fetch + ReadableStream。
export interface AssistantSource {
  index: number
  document_id: string
  doc_title: string
  score?: number | null
}

export interface AssistantUsage {
  token_in?: number
  token_out?: number
  cost_est?: number
  model?: string
}

export interface AssistantMessage {
  role: 'user' | 'assistant'
  content: string
}

interface StreamHandlers {
  onSources?: (s: AssistantSource[]) => void
  onDelta?: (t: string) => void
  onDone?: (usage?: AssistantUsage) => void
  onError?: (e: string) => void
}

function safeJson<T>(s: string): T | null {
  try { return JSON.parse(s) as T } catch { return null }
}

function parseEvent(raw: string): { event: string; data: string } | null {
  let event = 'message'
  const dataLines: string[] = []
  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return null
  return { event, data: dataLines.join('\n') }
}

export async function streamAssistant(
  body: { question: string; history?: AssistantMessage[]; use_knowledge?: boolean },
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = localStorage.getItem('access_token')
  let resp: Response
  try {
    resp = await fetch('/api/v1/ai/assistant/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
      signal,
    })
  } catch (e) {
    handlers.onError?.((e as Error)?.message || '网络错误')
    return
  }
  if (!resp.ok || !resp.body) {
    handlers.onError?.(`请求失败 (HTTP ${resp.status})`)
    return
  }
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buf.indexOf('\n\n')) >= 0) {
        const raw = buf.slice(0, idx)
        buf = buf.slice(idx + 2)
        const ev = parseEvent(raw)
        if (!ev) continue
        if (ev.event === 'sources') handlers.onSources?.(safeJson<AssistantSource[]>(ev.data) || [])
        else if (ev.event === 'delta') {
          const d = safeJson<{ t: string }>(ev.data)
          if (d?.t) handlers.onDelta?.(d.t)
        } else if (ev.event === 'error') handlers.onError?.(safeJson<{ error: string }>(ev.data)?.error || '生成失败')
        else if (ev.event === 'done') handlers.onDone?.(safeJson<{ usage?: AssistantUsage }>(ev.data)?.usage)
      }
    }
  } catch (e) {
    if ((e as Error)?.name !== 'AbortError') handlers.onError?.((e as Error)?.message || '读取中断')
  }
}
