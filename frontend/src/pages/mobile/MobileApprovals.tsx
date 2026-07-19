import { useState, useEffect } from 'react'
import MobileIcon from '@/components/MobileIcon'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { fetchUnifiedPending } from '@/api/unifiedApprovals'
import type { UnifiedPendingItem } from '@/api/unifiedApprovals'
import { usePageTitle } from '@/hooks/usePageTitle'

const bizTypeLabels: Record<string, string> = {
  quote_version: '报价',
  contract_version: '合同',
  change_request: '变更',
  solution: '方案',
  lead: '线索',
  order: '订单',
  service_ticket: '工单',
}

const bizTypeIcons: Record<string, string> = {
  quote_version: 'description',
  contract_version: 'handshake',
  change_request: 'swap_horiz',
  solution: 'lightbulb',
  lead: 'person_search',
  order: 'receipt_long',
  service_ticket: 'support_agent',
}

// 本页只列「待我审批」，因此只有 pending 一种呈现
const PENDING_BADGE = 'bg-amber-50 text-amber-600'

export default function MobileApprovals() {
  usePageTitle('审批中心')
  const navigate = useNavigate()
  const [pending, setPending] = useState<UnifiedPendingItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    // 聚合旧 approval 引擎与新工作流引擎的待办：线索等业务已切到新引擎，
    // 只查旧接口会让用户在这里看不到自己的待办
    fetchUnifiedPending().then((r) => setPending(r.items))
      .catch(() => message.error('加载失败'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <MobileIcon name="progress_activity" className="animate-spin text-primary" style={{ fontSize: 32 }} />
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => navigate(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0">
          <MobileIcon name="arrow_back_ios" />
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">审批中心</h2>
        <div className="w-10" />
      </div>

      {/* Stats */}
      <div className="bg-primary/10 rounded-xl p-4 mb-4 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
          <MobileIcon name="task_alt" className="text-primary" style={{ fontSize: 22 }} />
        </div>
        <div>
          <div className="text-2xl font-black text-primary">{pending.length}</div>
          <div className="text-sm text-primary/70 font-medium">待审批</div>
        </div>
      </div>

      {/* Pending List */}
      {pending.length > 0 ? (
        <div className="space-y-3">
          {pending.map((item) => (
            <div
              key={item.key}
              onClick={() => navigate(
                item.engine === 'wf'
                  ? `/m/lowcode/approvals/${item.instanceId}`
                  : `/m/approvals/${item.instanceId}`,
              )}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer active:bg-slate-50 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <MobileIcon name={bizTypeIcons[item.bizType || ''] || 'description'} className="text-primary" style={{ fontSize: 20 }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900 truncate">
                      {item.title || `${bizTypeLabels[item.bizType || ''] || ''}审批`}
                    </h4>
                    <span className={`text-[12px] font-bold px-2 py-0.5 rounded-full shrink-0 ${PENDING_BADGE}`}>
                      待审批
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-sm text-slate-500">
                      {bizTypeLabels[item.bizType || ''] || item.bizType || '审批'}
                    </span>
                    {item.subtitle && (
                      <>
                        <span className="text-sm text-slate-300">·</span>
                        <span className="text-sm text-slate-500 truncate">{item.subtitle}</span>
                      </>
                    )}
                  </div>
                  {item.createdAt && (
                    <div className="text-sm text-slate-400 mt-1.5">
                      {new Date(item.createdAt).toLocaleDateString()}
                    </div>
                  )}
                </div>
                <MobileIcon name="chevron_right" className="text-slate-300 shrink-0" style={{ fontSize: 16 }} />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <MobileIcon name="task_alt" className="text-slate-200 mb-2" style={{ fontSize: 48 }} />
          <p className="text-sm text-slate-400 mt-2">暂无待审批事项</p>
        </div>
      )}
    </div>
  )
}
