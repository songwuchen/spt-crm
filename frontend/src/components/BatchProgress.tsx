import { useState, useEffect, useCallback } from 'react'
import { Progress, message } from 'antd'

interface BatchTask {
  id: string
  label: string
  fn: () => Promise<void>
}

interface BatchProgressProps {
  tasks: BatchTask[]
  onComplete: (results: { id: string; success: boolean; error?: string }[]) => void
  onCancel?: () => void
}

export default function BatchProgress({ tasks, onComplete, onCancel }: BatchProgressProps) {
  const [current, setCurrent] = useState(0)
  const [results, setResults] = useState<{ id: string; success: boolean; error?: string }[]>([])
  const [cancelled, setCancelled] = useState(false)
  const [running, setRunning] = useState(true)

  const run = useCallback(async () => {
    const allResults: typeof results = []
    for (let i = 0; i < tasks.length; i++) {
      if (cancelled) break
      setCurrent(i + 1)
      try {
        await tasks[i].fn()
        allResults.push({ id: tasks[i].id, success: true })
      } catch (err: any) {
        allResults.push({ id: tasks[i].id, success: false, error: err?.message || String(err) })
      }
      setResults([...allResults])
    }
    setRunning(false)
    onComplete(allResults)
  }, [tasks, cancelled, onComplete])

  useEffect(() => { run() }, [])

  const pct = tasks.length > 0 ? Math.round((current / tasks.length) * 100) : 0
  const successCount = results.filter(r => r.success).length
  const failCount = results.filter(r => !r.success).length

  return (
    <div className="fixed bottom-6 right-6 z-50 bg-white rounded-xl border border-slate-200 shadow-xl p-4 w-80">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-bold text-slate-800">
          {running ? '批量处理中...' : '处理完成'}
        </span>
        <span className="text-sm text-slate-400">{current}/{tasks.length}</span>
      </div>
      <Progress percent={pct} size="small"
        status={failCount > 0 ? 'exception' : running ? 'active' : 'success'} />
      <div className="flex items-center gap-3 mt-2 text-sm">
        <span className="text-emerald-600 font-bold">成功 {successCount}</span>
        {failCount > 0 && <span className="text-red-500 font-bold">失败 {failCount}</span>}
      </div>
      {running && current < tasks.length && (
        <div className="text-sm text-slate-400 mt-1 truncate">
          正在处理: {tasks[current - 1]?.label || ''}
        </div>
      )}
      <div className="flex justify-end mt-2">
        {running ? (
          <button className="text-sm text-rose-500 font-bold hover:underline" onClick={() => { setCancelled(true); onCancel?.() }}>取消</button>
        ) : (
          <button className="text-sm text-blue-600 font-bold hover:underline" onClick={() => onComplete(results)}>关闭</button>
        )}
      </div>
    </div>
  )
}
