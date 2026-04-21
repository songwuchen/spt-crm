import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { message } from 'antd'
import { approvalApi } from '@/api/approval'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { ApprovalPendingItem } from '@/api/types'

const bizTypeLabels: Record<string, string> = {
  quote_version: '报价',
  contract_version: '合同',
  change_request: '变更',
  solution: '方案',
}

const bizTypeIcons: Record<string, string> = {
  quote_version: 'description',
  contract_version: 'handshake',
  change_request: 'swap_horiz',
  solution: 'lightbulb',
}

const statusColors: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-600',
  approved: 'bg-green-50 text-green-600',
  rejected: 'bg-red-50 text-red-600',
}

export default function MobileApprovals() {
  usePageTitle('审批中心')
  const navigate = useNavigate()
  const [pending, setPending] = useState<ApprovalPendingItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    approvalApi.myPending().then((res) => {
      if (res.data) setPending(res.data)
    }).catch(() => message.error('加载失败'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="material-symbols-outlined animate-spin text-primary" style={{ fontSize: 32 }}>progress_activity</span>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => navigate(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0">
          <span className="material-symbols-outlined">arrow_back_ios</span>
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">审批中心</h2>
        <div className="w-10" />
      </div>

      {/* Stats */}
      <div className="bg-primary/10 rounded-xl p-4 mb-4 flex items-center gap-3">
        <div className="w-10 h-10 rounded-full bg-primary/20 flex items-center justify-center">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: 22 }}>task_alt</span>
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
              key={item.id}
              onClick={() => navigate(`/m/approvals/${item.flow_id}`)}
              className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 cursor-pointer active:bg-slate-50 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center shrink-0">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>
                    {bizTypeIcons[item.flow?.biz_type] || 'description'}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-slate-900 truncate">
                      {item.flow?.title || `${bizTypeLabels[item.flow?.biz_type] || ''}审批`}
                    </h4>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full shrink-0 ${statusColors[item.status] || statusColors.pending}`}>
                      {item.status === 'pending' ? '待审批' : item.status === 'approved' ? '已通过' : '已拒绝'}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-sm text-slate-500">
                      {bizTypeLabels[item.flow?.biz_type] || item.flow?.biz_type}
                    </span>
                    <span className="text-sm text-slate-300">·</span>
                    <span className="text-sm text-slate-500">
                      {item.flow?.submitted_by_name || '未知'} 发起
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-1.5">
                    <span className="text-sm text-slate-400">
                      节点 {item.node_order}/{item.flow?.total_nodes || '-'}
                    </span>
                    <span className="text-sm text-slate-300">·</span>
                    <span className="text-sm text-slate-400">
                      {new Date(item.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
                <span className="material-symbols-outlined text-slate-300 shrink-0" style={{ fontSize: 16 }}>chevron_right</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-16">
          <span className="material-symbols-outlined text-slate-200 mb-2" style={{ fontSize: 48 }}>task_alt</span>
          <p className="text-sm text-slate-400 mt-2">暂无待审批事项</p>
        </div>
      )}
    </div>
  )
}
