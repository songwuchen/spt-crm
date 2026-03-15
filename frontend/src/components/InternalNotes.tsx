import { useState, useEffect, useRef, useCallback } from 'react'
import { Input, Button, message, Popconfirm } from 'antd'
import { activityApi } from '@/api/activity'
import { userApi } from '@/api/user'
import type { ActivityItem } from '@/api/types'
import VoiceInput from '@/components/VoiceInput'

interface InternalNotesProps {
  bizType: string
  bizId: string
}

export default function InternalNotes({ bizType, bizId }: InternalNotesProps) {
  const [notes, setNotes] = useState<ActivityItem[]>([])
  const [content, setContent] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [mentionOpen, setMentionOpen] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const [mentionUsers, setMentionUsers] = useState<{ label: string; value: string }[]>([])
  const [selectedMentions, setSelectedMentions] = useState<{ user_id: string; user_name: string }[]>([])
  const inputRef = useRef<any>(null)

  const fetchNotes = async () => {
    try {
      const res = await activityApi.list(bizType, bizId)
      const all = res.data || []
      setNotes(all.filter((a) => a.activity_type === 'note'))
    } catch { /* ignore */ }
  }

  useEffect(() => { fetchNotes() }, [bizType, bizId])

  const mentionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const searchUsers = useCallback((kw: string) => {
    if (mentionTimerRef.current) clearTimeout(mentionTimerRef.current)
    if (kw.length < 1) { setMentionUsers([]); return }
    mentionTimerRef.current = setTimeout(async () => {
      try {
        const r = await userApi.list({ pageNo: 1, pageSize: 20, keyword: kw })
        setMentionUsers((r.data?.items || []).map((u: any) => ({
          label: u.real_name || u.username,
          value: u.id,
        })))
      } catch { /* ignore */ }
    }, 300)
  }, [])

  useEffect(() => {
    return () => { if (mentionTimerRef.current) clearTimeout(mentionTimerRef.current) }
  }, [])

  const handleInput = (val: string) => {
    setContent(val)
    // Detect @ trigger
    const lastAt = val.lastIndexOf('@')
    if (lastAt >= 0) {
      const afterAt = val.slice(lastAt + 1)
      if (!afterAt.includes(' ') && afterAt.length > 0) {
        setMentionOpen(true)
        setMentionQuery(afterAt)
        searchUsers(afterAt)
        return
      }
    }
    setMentionOpen(false)
  }

  const insertMention = (userId: string, userName: string) => {
    const lastAt = content.lastIndexOf('@')
    const newContent = content.slice(0, lastAt) + `@${userName} `
    setContent(newContent)
    setMentionOpen(false)
    if (!selectedMentions.find((m) => m.user_id === userId)) {
      setSelectedMentions([...selectedMentions, { user_id: userId, user_name: userName }])
    }
    inputRef.current?.focus()
  }

  const handleSubmit = async () => {
    if (!content.trim()) return
    setSubmitting(true)
    try {
      await activityApi.create({
        biz_type: bizType,
        biz_id: bizId,
        activity_type: 'note',
        subject: '内部备忘',
        content: content.trim(),
        mentions_json: selectedMentions.length > 0 ? selectedMentions : undefined,
      })
      setContent('')
      setSelectedMentions([])
      fetchNotes()
    } catch {
      message.error('提交失败')
    } finally {
      setSubmitting(false)
    }
  }

  const handlePin = async (id: string) => {
    try {
      await activityApi.togglePin(id)
      fetchNotes()
    } catch {
      message.error('操作失败')
    }
  }

  const handleDelete = async (id: string) => {
    try {
      await activityApi.delete(id)
      fetchNotes()
    } catch {
      message.error('删除失败')
    }
  }

  const sortedNotes = [...notes].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1
    if (!a.pinned && b.pinned) return 1
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })

  return (
    <div className="space-y-4">
      {/* Input area */}
      <div className="relative">
        <Input.TextArea
          ref={inputRef}
          rows={3}
          value={content}
          onChange={(e) => handleInput(e.target.value)}
          placeholder="输入内部备忘... 使用 @ 提及同事"
          onPressEnter={(e) => { if (e.ctrlKey) handleSubmit() }}
        />
        {mentionOpen && mentionUsers.length > 0 && (
          <div className="absolute bottom-full left-0 mb-1 bg-white border border-slate-200 rounded-lg shadow-lg z-50 w-60 max-h-40 overflow-y-auto">
            {mentionUsers.map((u) => (
              <div key={u.value}
                className="px-3 py-2 hover:bg-blue-50 cursor-pointer text-sm"
                onClick={() => insertMention(u.value, u.label)}>
                {u.label}
              </div>
            ))}
          </div>
        )}
        <div className="flex justify-between items-center mt-2">
          <div className="flex items-center gap-2">
            <VoiceInput onResult={(text) => setContent((prev) => prev + text)} />
            <span className="text-[11px] text-slate-400">Ctrl+Enter 快速提交</span>
          </div>
          <Button type="primary" size="small" loading={submitting} onClick={handleSubmit}
            disabled={!content.trim()}>
            发布备忘
          </Button>
        </div>
      </div>

      {/* Notes list */}
      {sortedNotes.length === 0 ? (
        <div className="text-center text-slate-400 text-sm py-6">暂无内部备忘</div>
      ) : (
        <div className="space-y-3">
          {sortedNotes.map((note) => (
            <div key={note.id}
              className={`p-4 rounded-lg border ${note.pinned ? 'bg-amber-50 border-amber-200' : 'bg-white border-slate-200'}`}>
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-bold text-slate-800">{note.created_by_name || '未知'}</span>
                    <span className="text-[11px] text-slate-400">{note.created_at ? new Date(note.created_at).toLocaleString('zh-CN') : ''}</span>
                    {note.pinned && (
                      <span className="text-[10px] bg-amber-100 text-amber-700 px-1.5 py-0.5 rounded font-bold">置顶</span>
                    )}
                  </div>
                  <p className="text-sm text-slate-700 whitespace-pre-wrap">{note.content}</p>
                  {note.mentions_json && note.mentions_json.length > 0 && (
                    <div className="flex gap-1 mt-2">
                      {note.mentions_json.map((m) => (
                        <span key={m.user_id} className="text-[11px] bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded">
                          @{m.user_name}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => handlePin(note.id)}
                    className={`p-1 rounded hover:bg-slate-100 ${note.pinned ? 'text-amber-500' : 'text-slate-300 hover:text-slate-500'}`}
                    title={note.pinned ? '取消置顶' : '置顶'}>
                    <span className="material-symbols-outlined" style={{ fontSize: 16 }}>push_pin</span>
                  </button>
                  <Popconfirm title="确认删除？" onConfirm={() => handleDelete(note.id)} okText="删除" cancelText="取消">
                    <button className="p-1 rounded hover:bg-slate-100 text-slate-300 hover:text-red-500" title="删除">
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>delete</span>
                    </button>
                  </Popconfirm>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
