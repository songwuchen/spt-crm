import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { CONTEXTUAL_TIPS } from './OnboardingTour'

import Icon from '@/components/Icon'
export default function ContextualHelp() {
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())
  const [showHelp, setShowHelp] = useState(false)
  const location = useLocation()

  // Find matching tip for current path
  const path = location.pathname
  const tip = Object.entries(CONTEXTUAL_TIPS).find(([p]) => path === p || path.startsWith(p + '/'))?.[1]

  if (!tip || dismissed.has(path)) return null

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {showHelp && (
        <div className="mb-2 bg-white rounded-xl shadow-2xl border border-slate-200 p-4 max-w-xs animate-in fade-in slide-in-from-bottom-2">
          <div className="flex items-start justify-between mb-1">
            <div className="flex items-center gap-2">
              <Icon name="help" className="text-blue-500" style={{ fontSize: 18 }} />
              <h4 className="font-bold text-sm text-slate-800">{tip.title}</h4>
            </div>
            <button onClick={() => { setShowHelp(false); setDismissed((s) => new Set(s).add(path)) }}
              className="text-slate-400 hover:text-slate-600">
              <Icon name="close" style={{ fontSize: 16 }} />
            </button>
          </div>
          <p className="text-sm text-slate-500 leading-relaxed">{tip.content}</p>
        </div>
      )}
      <button
        onClick={() => setShowHelp(!showHelp)}
        className="w-10 h-10 rounded-full bg-blue-500 text-white shadow-lg hover:bg-blue-600 flex items-center justify-center transition-colors"
        title="帮助提示"
      >
        <Icon name={showHelp ? 'close' : 'help'} style={{ fontSize: 20 }} />
      </button>
    </div>
  )
}
