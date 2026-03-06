import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { leadApi } from '@/api/lead'
import { usePageTitle } from '@/hooks/usePageTitle'

interface LeadItem {
  id: string; lead_code: string; title: string; company_name: string | null
  contact_name: string | null; contact_phone: string | null; contact_email: string | null
  source: string | null; status: string; score: number | null
  demand_summary: string | null; industry: string | null; region: string | null
  owner_name: string | null; created_at: string
}

const statusMap: Record<string, { label: string; color: string }> = {
  new: { label: '新建', color: 'bg-blue-100 text-blue-700' },
  following: { label: '跟进中', color: 'bg-amber-100 text-amber-700' },
  qualified: { label: '已转化', color: 'bg-emerald-100 text-emerald-700' },
  discarded: { label: '已废弃', color: 'bg-slate-100 text-slate-500' },
}

export default function MobileLeadDetail() {
  usePageTitle('线索详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [lead, setLead] = useState<LeadItem | null>(null)

  useEffect(() => {
    if (!id) return
    leadApi.get(id).then((r: any) => setLead(r.data)).catch(() => message.error('加载失败'))
  }, [id])

  if (!lead) return <div className="text-center py-12 text-slate-400">加载中...</div>

  const st = statusMap[lead.status] || statusMap.new

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <span className="material-symbols-outlined" style={{ fontSize: 20 }}>arrow_back</span>
        </button>
        <h1 className="text-lg font-extrabold text-slate-900 flex-1">{lead.title}</h1>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${st.color}`}>{st.label}</span>
      </div>

      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 space-y-3">
        <div className="flex justify-between">
          <span className="text-xs text-slate-400">编码</span>
          <span className="text-xs font-mono text-slate-600">{lead.lead_code}</span>
        </div>
        {lead.company_name && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">公司</span>
            <span className="text-sm font-bold text-slate-800">{lead.company_name}</span>
          </div>
        )}
        {lead.contact_name && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">联系人</span>
            <span className="text-sm text-slate-700">{lead.contact_name}</span>
          </div>
        )}
        {lead.contact_phone && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">电话</span>
            <a href={`tel:${lead.contact_phone}`} className="text-sm text-primary font-bold">{lead.contact_phone}</a>
          </div>
        )}
        {lead.contact_email && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">邮箱</span>
            <span className="text-sm text-slate-600">{lead.contact_email}</span>
          </div>
        )}
        {lead.source && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">来源</span>
            <span className="text-sm text-slate-600">{lead.source}</span>
          </div>
        )}
        {lead.industry && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">行业</span>
            <span className="text-sm text-slate-600">{lead.industry}</span>
          </div>
        )}
        {lead.region && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">地区</span>
            <span className="text-sm text-slate-600">{lead.region}</span>
          </div>
        )}
        {lead.score != null && (
          <div className="flex justify-between">
            <span className="text-xs text-slate-400">评分</span>
            <span className="text-sm font-bold text-amber-600">{lead.score}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-xs text-slate-400">负责人</span>
          <span className="text-sm text-slate-600">{lead.owner_name || '-'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-slate-400">创建时间</span>
          <span className="text-xs text-slate-500">{lead.created_at ? new Date(lead.created_at).toLocaleDateString('zh-CN') : '-'}</span>
        </div>
      </div>

      {lead.demand_summary && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 mt-3">
          <h3 className="text-xs font-bold text-slate-400 uppercase mb-2">需求摘要</h3>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{lead.demand_summary}</p>
        </div>
      )}
    </div>
  )
}
