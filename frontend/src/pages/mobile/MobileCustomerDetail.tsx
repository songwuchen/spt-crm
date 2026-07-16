import { useState, useEffect } from 'react'
import MobileIcon from '@/components/MobileIcon'
import { useParams, useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { customerApi } from '@/api/customer'
import { contactApi } from '@/api/contact'
import { activityApi } from '@/api/activity'
import { industryFallback } from '@/api/types'
import { useDataDict } from '@/hooks/useDataDict'
import { usePageTitle } from '@/hooks/usePageTitle'
import { formatRegion } from '@/utils/address'

interface CustomerInfo {
  id: string; name: string; customer_code?: string; short_name?: string
  industry?: string; scale_level?: string; region?: string; address?: string
  province?: string; city?: string; district?: string; region_code?: string
  website?: string; owner_name?: string; source?: string; level?: string
  status: string; remark?: string; created_at: string
}

interface Contact {
  id: string; name: string; title?: string; role_type?: string
  phone?: string; mobile?: string; email?: string; is_primary: boolean
}

interface Activity {
  id: string; activity_type: string; subject?: string; content?: string
  contact_name?: string; created_by_name?: string; created_at: string
}

const levelColors: Record<string, string> = {
  A: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  B: 'bg-blue-50 text-blue-700 border-blue-200',
  C: 'bg-amber-50 text-amber-700 border-amber-200',
  D: 'bg-slate-50 text-slate-600 border-slate-200',
}

const activityIcons: Record<string, string> = {
  call: 'call', visit: 'directions_walk', meeting: 'groups', email: 'email', note: 'edit_note',
}

export default function MobileCustomerDetail() {
  usePageTitle('客户详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [customer, setCustomer] = useState<CustomerInfo | null>(null)
  const [contacts, setContacts] = useState<Contact[]>([])
  const [activities, setActivities] = useState<Activity[]>([])
  const [tab, setTab] = useState<'info' | 'contacts' | 'activities'>('info')
  const { options: industryOpts } = useDataDict('industry', industryFallback)
  const industryMap = Object.fromEntries(industryOpts.map((o) => [o.value, o.label]))

  useEffect(() => {
    if (!id) return
    customerApi.get(id).then((r: any) => setCustomer(r.data)).catch(() => message.error('加载失败'))
    contactApi.list(id).then((r: any) => setContacts(r.data || [])).catch(() => {})
    activityApi.list('customer', id).then((r: any) => setActivities(r.data || [])).catch(() => {})
  }, [id])

  if (!customer) return <div className="text-center py-12 text-slate-400">加载中...</div>

  const lc = levelColors[customer.level || ''] || levelColors.D

  return (
    <div>
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <MobileIcon name="arrow_back" style={{ fontSize: 20 }} />
        </button>
        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-extrabold text-slate-900 truncate">{customer.name}</h1>
          <span className="text-[12px] font-mono text-slate-400">{customer.customer_code}</span>
        </div>
        {customer.level && (
          <span className={`px-2 py-0.5 rounded text-[12px] font-bold border ${lc}`}>
            {customer.level}级
          </span>
        )}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className="bg-gradient-to-br from-primary/10 to-blue-50 rounded-xl p-3 text-center border border-primary/10">
          <div className="text-lg font-black text-slate-900">{contacts.length}</div>
          <div className="text-[12px] text-slate-500 font-bold">联系人</div>
        </div>
        <div className="bg-gradient-to-br from-emerald-50 to-green-50 rounded-xl p-3 text-center border border-emerald-100">
          <div className="text-lg font-black text-emerald-600">{activities.length}</div>
          <div className="text-[12px] text-slate-500 font-bold">互动记录</div>
        </div>
        <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-3 text-center border border-amber-100">
          <div className="text-lg font-black text-amber-600">
            {customer.status === 'active' ? '活跃' : '停用'}
          </div>
          <div className="text-[12px] text-slate-500 font-bold">状态</div>
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex gap-1 mb-4 bg-slate-100 rounded-lg p-1">
        {(['info', 'contacts', 'activities'] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`flex-1 py-2 rounded-md text-sm font-bold transition-colors ${tab === t ? 'bg-white text-primary shadow-sm' : 'text-slate-500'}`}>
            {t === 'info' ? '基本信息' : t === 'contacts' ? '联系人' : '互动记录'}
          </button>
        ))}
      </div>

      {tab === 'info' && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 space-y-3">
          {customer.short_name && (
            <div className="flex justify-between"><span className="text-sm text-slate-400">简称</span><span className="text-sm text-slate-700">{customer.short_name}</span></div>
          )}
          {customer.industry && (
            <div className="flex justify-between"><span className="text-sm text-slate-400">行业</span><span className="text-sm text-slate-700">{industryMap[customer.industry] || customer.industry}</span></div>
          )}
          {(() => {
            const region = formatRegion(customer)
            return region ? (
              <div className="flex justify-between"><span className="text-sm text-slate-400">区域</span><span className="text-sm text-slate-700">{region}</span></div>
            ) : null
          })()}
          <div className="flex justify-between"><span className="text-sm text-slate-400">负责人</span><span className="text-sm text-slate-700">{customer.owner_name || '-'}</span></div>
          {customer.source && (
            <div className="flex justify-between"><span className="text-sm text-slate-400">来源</span><span className="text-sm text-slate-700">{customer.source}</span></div>
          )}
          <div className="flex justify-between"><span className="text-sm text-slate-400">创建时间</span><span className="text-sm text-slate-500">{new Date(customer.created_at).toLocaleDateString('zh-CN')}</span></div>
          {customer.remark && (
            <div><span className="text-sm text-slate-400 block mb-1">备注</span><p className="text-sm text-slate-700">{customer.remark}</p></div>
          )}
        </div>
      )}

      {tab === 'contacts' && (
        <div>
          {contacts.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">暂无联系人</div>
          ) : (
            <div className="space-y-2">
              {contacts.map((c) => (
                <div key={c.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-bold text-slate-800">{c.name}</span>
                    {c.is_primary && <span className="text-[12px] font-bold text-amber-600 bg-amber-50 px-1 rounded">主要</span>}
                    {c.title && <span className="text-sm text-slate-500">{c.title}</span>}
                  </div>
                  <div className="flex gap-3 text-sm text-slate-500">
                    {c.phone && <span>{c.phone}</span>}
                    {c.mobile && <span>{c.mobile}</span>}
                    {c.email && <span>{c.email}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {tab === 'activities' && (
        <div>
          {activities.length === 0 ? (
            <div className="text-center py-12 text-slate-400 text-sm">暂无互动记录</div>
          ) : (
            <div className="space-y-2">
              {activities.map((a) => (
                <div key={a.id} className="bg-white rounded-xl border border-slate-100 shadow-sm p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <MobileIcon name={activityIcons[a.activity_type] || 'note'} className="text-slate-400" style={{ fontSize: 16 }} />
                    <span className="text-sm font-bold text-slate-800 flex-1 truncate">{a.subject || a.content?.slice(0, 30) || '-'}</span>
                  </div>
                  {a.content && <p className="text-sm text-slate-600 mb-1 line-clamp-2">{a.content}</p>}
                  <div className="text-[12px] text-slate-400">
                    {a.created_by_name || ''} &middot; {a.created_at ? new Date(a.created_at).toLocaleDateString('zh-CN') : ''}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="fixed bottom-20 left-0 right-0 px-4 pb-2">
        <div className="flex gap-2">
          <button onClick={() => navigate('/m/follow-up/new')}
            className="flex-1 py-2.5 bg-primary text-white rounded-lg text-sm font-bold shadow-sm">
            写跟进
          </button>
        </div>
      </div>
    </div>
  )
}
