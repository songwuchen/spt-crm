// 移动端 → 扩展平台审批中心(走 lowcode workflowApi): 我的待办 / 我发起的。
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import MobileIcon from '@/components/MobileIcon'
import { usePageTitle } from '@/hooks/usePageTitle'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfTodoItem } from '@/types/lowcode'
import { WF_STATUS as PSTATUS } from '@/utils/lowcodeWorkflowLabels'

type MineItem = { id: string; title?: string; status: string; created_at?: string }

export default function MobileLowcodeApprovals() {
  usePageTitle('扩展审批')
  const nav = useNavigate()
  const [tab, setTab] = useState<'todo' | 'mine'>('todo')
  const [todo, setTodo] = useState<WfTodoItem[]>([])
  const [mine, setMine] = useState<MineItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'todo') { const r = await workflowApi.todo({ pageNo: 1, pageSize: 50 }); setTodo(r.data.items) }
      else { const r = await workflowApi.mine({ pageNo: 1, pageSize: 50 }); setMine(r.data.items) }
    } catch { message.error('加载失败') } finally { setLoading(false) }
  }, [tab])
  useEffect(() => { load() }, [load])

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => nav(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0"><MobileIcon name="arrow_back_ios" /></button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">扩展审批</h2>
        <div className="w-10" />
      </div>

      <div className="flex bg-slate-100 rounded-xl p-1 mb-4">
        {(['todo', 'mine'] as const).map((k) => (
          <button key={k} onClick={() => setTab(k)}
            className={`flex-1 h-9 rounded-lg text-sm font-bold border-0 ${tab === k ? 'bg-white text-primary shadow-sm' : 'bg-transparent text-slate-500'}`}>
            {k === 'todo' ? '我的待办' : '我发起的'}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-48"><MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 28 }} /></div>
      ) : tab === 'todo' ? (
        todo.length ? (
          <div className="space-y-3">
            {todo.map((t) => (
              <div key={t.task_id} onClick={() => nav(`/m/lowcode/approvals/${t.process_instance_id}?task=${t.task_id}`)}
                className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer active:bg-slate-50">
                <div className="flex items-center justify-between gap-2">
                  <h4 className="text-sm font-bold text-slate-900 truncate">{t.title || '(无标题)'}</h4>
                  {t.on_behalf_of && <span className="text-[12px] font-bold px-2 py-0.5 rounded-full bg-purple-50 text-purple-600 shrink-0">代 {t.delegator_name || '委托人'}</span>}
                </div>
                <div className="text-sm text-slate-400 mt-1">{t.business_no || '—'} · {t.created_at ? t.created_at.slice(0, 10) : ''}</div>
              </div>
            ))}
          </div>
        ) : <Empty text="暂无待办" />
      ) : (
        mine.length ? (
          <div className="space-y-3">
            {mine.map((m) => {
              const st = PSTATUS[m.status] || { cls: 'bg-slate-100 text-slate-500', text: m.status }
              return (
                <div key={m.id} onClick={() => nav(`/m/lowcode/approvals/${m.id}`)}
                  className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer active:bg-slate-50">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900 truncate">{m.title || '(无标题)'}</h4>
                    <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${st.cls}`}>{st.text}</span>
                  </div>
                  <div className="text-sm text-slate-400 mt-1">{m.created_at ? m.created_at.slice(0, 10) : ''}</div>
                </div>
              )
            })}
          </div>
        ) : <Empty text="暂无发起的流程" />
      )}
    </div>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="text-center py-16"><MobileIcon name="task_alt" className="text-slate-200 mb-2" style={{ fontSize: 48 }} /><p className="text-sm text-slate-400 mt-2">{text}</p></div>
}
