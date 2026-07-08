import { useState, useEffect } from 'react'
import { message } from 'antd'
import { taskApi } from '@/api/task'
import { usePageTitle } from '@/hooks/usePageTitle'

interface TaskItem {
  id: string; title: string; due_date: string | null; priority: string
  status: string; is_completed: boolean; biz_name: string | null
}

const priorityColors: Record<string, string> = {
  urgent: 'text-red-600', high: 'text-amber-600', normal: 'text-blue-600', low: 'text-slate-400',
}

export default function MobileTasks() {
  usePageTitle('待办任务')
  const [tasks, setTasks] = useState<TaskItem[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [title, setTitle] = useState('')

  const fetch = async () => {
    const res = await taskApi.list({ pageNo: 1, pageSize: 50 })
    setTasks(res.data?.items || [])
  }

  useEffect(() => { fetch() }, [])

  const toggleComplete = async (t: TaskItem) => {
    await taskApi.update(t.id, { is_completed: !t.is_completed, status: !t.is_completed ? 'done' : 'todo' })
    fetch()
  }

  const addTask = async () => {
    if (!title.trim()) return
    await taskApi.create({ title: title.trim() })
    setTitle('')
    setShowAdd(false)
    message.success('任务已创建')
    fetch()
  }

  const todoTasks = tasks.filter(t => !t.is_completed)
  const doneTasks = tasks.filter(t => t.is_completed)

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-extrabold text-slate-900">待办任务</h1>
        <button onClick={() => setShowAdd(!showAdd)}
          className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>add</span>
        </button>
      </div>

      {showAdd && (
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-3 mb-3 flex gap-2">
          <input className="flex-1 border border-slate-200 rounded-lg px-3 py-2 text-sm"
            placeholder="输入任务标题" value={title} onChange={e => setTitle(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && addTask()} autoFocus />
          <button onClick={addTask} className="px-4 py-2 bg-primary text-white rounded-lg text-sm font-bold">添加</button>
        </div>
      )}

      {todoTasks.length > 0 && (
        <div className="space-y-2 mb-4">
          {todoTasks.map(t => (
            <div key={t.id} role="button" tabIndex={0} onClick={() => toggleComplete(t)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleComplete(t) } }}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 flex items-center gap-3 cursor-pointer active:bg-slate-50">
              <div className="w-5 h-5 rounded-full border-2 border-slate-300 flex items-center justify-center shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-bold text-slate-800 truncate">{t.title}</div>
                {t.due_date && (
                  <div className="text-[12px] text-slate-400 mt-0.5">{t.due_date}</div>
                )}
              </div>
              <span className={`material-symbols-outlined ${priorityColors[t.priority] || 'text-slate-400'}`} style={{ fontSize: 14 }}>
                {t.priority === 'urgent' || t.priority === 'high' ? 'priority_high' : 'remove'}
              </span>
            </div>
          ))}
        </div>
      )}

      {doneTasks.length > 0 && (
        <>
          <div className="text-[12px] font-bold text-slate-400 uppercase tracking-wider mb-2">已完成 ({doneTasks.length})</div>
          <div className="space-y-2">
            {doneTasks.slice(0, 5).map(t => (
              <div key={t.id} role="button" tabIndex={0} onClick={() => toggleComplete(t)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleComplete(t) } }}
                className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 flex items-center gap-3 cursor-pointer active:bg-slate-50 opacity-60">
                <div className="w-5 h-5 rounded-full border-2 border-emerald-400 bg-emerald-50 flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-emerald-500" style={{ fontSize: 14 }}>check</span>
                </div>
                <span className="text-sm text-slate-500 line-through truncate">{t.title}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {tasks.length === 0 && (
        <div className="text-center py-12 text-slate-400 text-sm">暂无待办任务</div>
      )}
    </div>
  )
}
