import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { dashboardApi } from '@/api/dashboard'
import { usePageTitle } from '@/hooks/usePageTitle'

interface SearchResult {
  type: string; id: string; title: string; subtitle: string; url: string
}

const typeConfig: Record<string, { icon: string; label: string; color: string }> = {
  customer: { icon: 'business', label: '客户', color: 'text-blue-500' },
  lead: { icon: 'trending_up', label: '线索', color: 'text-emerald-500' },
  project: { icon: 'rocket_launch', label: '商机', color: 'text-amber-500' },
  contact: { icon: 'person', label: '联系人', color: 'text-indigo-500' },
  ticket: { icon: 'confirmation_number', label: '工单', color: 'text-red-500' },
}

export default function MobileSearch() {
  usePageTitle('搜索')
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [searched, setSearched] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const doSearch = async (q: string) => {
    if (!q.trim()) { setResults([]); setSearched(false); return }
    setLoading(true)
    try {
      const res = await dashboardApi.search({ q: q.trim() }) as any
      setResults(res.data || [])
      setSearched(true)
    } catch { setResults([]) }
    finally { setLoading(false) }
  }

  const handleChange = (val: string) => {
    setQuery(val)
    if (timerRef.current) clearTimeout(timerRef.current)
    if (val.trim().length >= 1) {
      timerRef.current = setTimeout(() => doSearch(val), 300)
    } else {
      setResults([])
      setSearched(false)
    }
  }

  const grouped = results.reduce<Record<string, SearchResult[]>>((acc, r) => {
    (acc[r.type] ||= []).push(r)
    return acc
  }, {})

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Search Bar */}
      <div className="bg-white px-4 pt-3 pb-3 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <button onClick={() => navigate(-1)} className="text-slate-400 shrink-0">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
          </button>
          <div className="flex-1 relative">
            <span className="material-symbols-outlined absolute left-2.5 top-2 text-slate-400" style={{ fontSize: 18 }}>search</span>
            <input autoFocus value={query} onChange={(e) => handleChange(e.target.value)}
              placeholder="搜索客户、线索、商机、工单..."
              className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-2 text-sm" />
          </div>
          {query && (
            <button onClick={() => { setQuery(''); setResults([]); setSearched(false) }}
              className="text-sm text-slate-400 shrink-0">清除</button>
          )}
        </div>
      </div>

      {/* Results */}
      <div className="p-4 space-y-3">
        {loading && <div className="text-center py-8 text-slate-400 text-sm">搜索中...</div>}
        {!loading && searched && results.length === 0 && (
          <div className="text-center py-8 text-slate-400 text-sm">未找到匹配结果</div>
        )}
        {!loading && Object.entries(grouped).map(([type, items]) => {
          const cfg = typeConfig[type] || typeConfig.customer
          return (
            <div key={type}>
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">
                {cfg.label}（{items.length}）
              </div>
              <div className="space-y-1.5">
                {items.map((r) => (
                  <div key={`${r.type}-${r.id}`} onClick={() => navigate(r.url)}
                    className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 flex items-center gap-3 active:bg-slate-50">
                    <span className={`material-symbols-outlined ${cfg.color}`} style={{ fontSize: 20 }}>{cfg.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-bold text-slate-800 truncate">{r.title}</div>
                      {r.subtitle && <div className="text-sm text-slate-400 truncate">{r.subtitle}</div>}
                    </div>
                    <span className="material-symbols-outlined text-slate-300" style={{ fontSize: 16 }}>chevron_right</span>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
