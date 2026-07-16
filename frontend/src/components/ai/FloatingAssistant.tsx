// 全局 AI 助手浮窗：右下角常驻按钮，点开对话面板(复用 AiChatPanel)。
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { RobotOutlined, CloseOutlined } from '@ant-design/icons'
import AiChatPanel from './AiChatPanel'

export default function FloatingAssistant() {
  const [open, setOpen] = useState(false)
  const navigate = useNavigate()

  return (
    <>
      {/* 悬浮按钮 */}
      <button
        onClick={() => setOpen((v) => !v)}
        title="AI 助手"
        className="fixed z-[1000] bottom-6 right-6 w-14 h-14 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-xl shadow-indigo-500/30 flex items-center justify-center hover:scale-105 active:scale-95 transition-transform"
        style={{ display: open ? 'none' : 'flex' }}
      >
        <RobotOutlined style={{ fontSize: 24 }} />
      </button>

      {/* 对话面板 */}
      {open && (
        <div className="fixed z-[1000] bottom-6 right-6 w-[380px] max-w-[calc(100vw-2rem)] bg-white rounded-2xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden"
          style={{ height: 600, maxHeight: 'calc(100vh - 3rem)' }}>
          <div className="flex items-center justify-between px-4 py-3 bg-gradient-to-r from-indigo-500 to-violet-600 text-white">
            <div className="flex items-center gap-2">
              <RobotOutlined style={{ fontSize: 18 }} />
              <span className="font-bold text-sm">AI 助手</span>
            </div>
            <button onClick={() => setOpen(false)} className="text-white/80 hover:text-white p-1">
              <CloseOutlined />
            </button>
          </div>
          <div className="flex-1 min-h-0 p-3">
            <AiChatPanel
              height="100%"
              defaultUseKnowledge
              showKnowledgeToggle
              welcome="你好，我是企业智能助手。可以问我知识库里的制度、流程，或让我帮你梳理业务问题。"
              placeholder="问我任何问题…"
              onOpenDoc={(docId) => { setOpen(false); navigate(`/ai/knowledge?doc=${docId}`) }}
            />
          </div>
        </div>
      )}
    </>
  )
}
