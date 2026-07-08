import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { leadApi } from '@/api/lead'
import { usePageTitle } from '@/hooks/usePageTitle'

interface LeadItem {
  id: string; title: string; company_name?: string; contact_name?: string
  source?: string; status: string; owner_name?: string; created_at: string
}

const statusConfig: Record<string, { label: string; color: string; bg: string }> = {
  new: { label: '新建', color: 'text-blue-700', bg: 'bg-blue-50' },
  following: { label: '跟进中', color: 'text-amber-700', bg: 'bg-amber-50' },
  qualified: { label: '已合格', color: 'text-emerald-700', bg: 'bg-emerald-50' },
  discarded: { label: '已废弃', color: 'text-slate-600', bg: 'bg-slate-100' },
}

const sourceLabels: Record<string, string> = {
  website: '官网', referral: '转介绍', exhibition: '展会',
  cold_call: '陌拜', advertising: '广告', other: '其他',
}

export default function MobileLeads() {
  usePageTitle('线索')
  const navigate = useNavigate()
  const [leads, setLeads] = useState<LeadItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filterStatus, setFilterStatus] = useState<string>('all')
  const [keyword, setKeyword] = useState('')

  const fetchLeads = (st?: string) => {
    setLoading(true)
    leadApi.list({ pageNo: 1, pageSize: 50, status: st && st !== 'all' ? st : undefined, keyword: keyword || undefined })
      .then((r: any) => setLeads(r.data?.items || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchLeads() }, [])

  const statuses = ['all', 'new', 'following', 'qualified', 'discarded']

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-white px-4 pt-3 pb-2 border-b border-slate-100 flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-900">线索</h1>
        <button onClick={() => navigate('/m/leads/new')}
          className="text-primary font-bold text-sm">新建</button>
      </div>

      {/* Search */}
      <div className="bg-white px-4 py-2 border-b border-slate-100">
        <div className="relative">
          <span className="material-symbols-outlined absolute left-2.5 top-2 text-slate-400" style={{ fontSize: 18 }}>search</span>
          <input value={keyword} onChange={(e) => setKeyword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchLeads(filterStatus)}
            placeholder="搜索线索" className="w-full bg-slate-50 border border-slate-200 rounded-lg pl-8 pr-3 py-2 text-sm" />
        </div>
      </div>

      {/* Status Tabs */}
      <div className="bg-white px-4 py-2 border-b border-slate-100 flex gap-1.5 overflow-x-auto">
        {statuses.map((s) => (
          <button key={s} onClick={() => { setFilterStatus(s); fetchLeads(s) }}
            className={`shrink-0 px-3 py-1.5 rounded-full text-sm font-bold transition-colors ${
              filterStatus === s ? 'bg-primary text-white' : 'bg-slate-100 text-slate-600'
            }`}>
            {s === 'all' ? '全部' : statusConfig[s]?.label || s}
          </button>
        ))}
      </div>

      {/* Lead List */}
      <div className="p-4 space-y-2 pb-20">
        {loading && <div className="text-center py-8 text-slate-400 text-sm">加载中...</div>}
        {!loading && leads.length === 0 && (
          <div className="text-center py-8 text-slate-400 text-sm">暂无线索</div>
        )}
        {leads.map((l) => {
          const st = statusConfig[l.status] || statusConfig.new
          return (
            <div key={l.id} onClick={() => navigate(`/m/leads/${l.id}`)}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-3 active:bg-slate-50">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold text-slate-800 flex-1 truncate">{l.title}</span>
                <span className={`px-2 py-0.5 rounded-full text-[12px] font-bold ${st.color} ${st.bg}`}>{st.label}</span>
              </div>
              {l.company_name && <p className="text-sm text-slate-600 mb-1">{l.company_name}</p>}
              <div className="flex items-center gap-3 text-[12px] text-slate-400">
                {l.contact_name && <span>{l.contact_name}</span>}
                {l.source && <span>{sourceLabels[l.source] || l.source}</span>}
                {l.owner_name && <span>{l.owner_name}</span>}
                <span className="ml-auto">{l.created_at ? new Date(l.created_at).toLocaleDateString('zh-CN') : ''}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
