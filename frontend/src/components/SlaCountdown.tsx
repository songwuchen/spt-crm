import { useState, useEffect } from 'react'

import Icon from '@/components/Icon'
interface SlaCountdownProps {
  label: string
  deadline?: string | null
  completedAt?: string | null
}

function formatDuration(ms: number) {
  const abs = Math.abs(ms)
  const hours = Math.floor(abs / 3600000)
  const minutes = Math.floor((abs % 3600000) / 60000)
  const seconds = Math.floor((abs % 60000) / 1000)
  if (hours > 0) return `${hours}h ${minutes}m`
  if (minutes > 0) return `${minutes}m ${seconds}s`
  return `${seconds}s`
}

export default function SlaCountdown({ label, deadline, completedAt }: SlaCountdownProps) {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    if (completedAt || !deadline) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [deadline, completedAt])

  if (!deadline) return null

  const deadlineMs = new Date(deadline).getTime()

  // Already completed
  if (completedAt) {
    const completedMs = new Date(completedAt).getTime()
    const diff = deadlineMs - completedMs
    const met = diff >= 0
    return (
      <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${met ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}>
        <Icon name={met ? 'check_circle' : 'cancel'} className={`${met ? 'text-emerald-500' : 'text-red-500'}`} style={{ fontSize: 18 }} />
        <div>
          <div className="text-[13px] text-slate-500 font-bold">{label}</div>
          <div className={`text-sm font-black ${met ? 'text-emerald-600' : 'text-red-600'}`}>
            {met ? '已达标' : '已超时'} {formatDuration(Math.abs(diff))}
          </div>
        </div>
      </div>
    )
  }

  // Countdown in progress
  const remaining = deadlineMs - now
  const breached = remaining < 0
  const warning = remaining > 0 && remaining < 3600000 // < 1h

  let bgClass = 'bg-blue-50 border-blue-200'
  let textClass = 'text-blue-600'
  let icon = 'timer'
  if (breached) {
    bgClass = 'bg-red-50 border-red-200'
    textClass = 'text-red-600'
    icon = 'alarm'
  } else if (warning) {
    bgClass = 'bg-amber-50 border-amber-200'
    textClass = 'text-amber-600'
    icon = 'warning'
  }

  return (
    <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${bgClass}`}>
      <Icon name={icon} className={`${textClass} ${!breached && !completedAt ? 'animate-pulse' : ''}`} style={{ fontSize: 18 }} />
      <div>
        <div className="text-[13px] text-slate-500 font-bold">{label}</div>
        <div className={`text-sm font-black tabular-nums ${textClass}`}>
          {breached ? `超时 ${formatDuration(remaining)}` : formatDuration(remaining)}
        </div>
      </div>
    </div>
  )
}
