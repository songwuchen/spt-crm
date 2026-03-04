import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { message, Modal, Input, Select } from 'antd'
import { approvalApi } from '@/api/approval'
import { aiApi } from '@/api/ai'
import { usePageTitle } from '@/hooks/usePageTitle'
import type { ApprovalFlowItem, AiResultItem } from '@/api/types'
import client from '@/api/client'

const bizTypeLabels: Record<string, string> = {
  quote_version: '报价审批',
  contract_version: '合同审批',
  change_request: '变更审批',
  solution: '方案审批',
}

const bizTypeIcons: Record<string, string> = {
  quote_version: 'description',
  contract_version: 'handshake',
  change_request: 'swap_horiz',
  solution: 'lightbulb',
}

const modeLabels: Record<string, string> = {
  sequential: '顺序审批',
  parallel: '并行审批',
  any_one: '任一审批',
}

const taskStatusLabels: Record<string, string> = {
  pending: '待审批', approved: '已通过', rejected: '已拒绝',
  waiting: '等待中', cancelled: '已取消',
}

interface RiskItem {
  title: string
  description: string
  severity: 'H' | 'M' | 'L'
}

const severityConfig: Record<string, { bg: string; border: string; icon: string; iconColor: string; titleColor: string; descColor: string }> = {
  H: { bg: 'bg-red-50', border: 'border-red-100', icon: 'report_problem', iconColor: 'text-red-600', titleColor: 'text-red-900', descColor: 'text-red-800/80' },
  M: { bg: 'bg-orange-50', border: 'border-orange-100', icon: 'warning', iconColor: 'text-orange-600', titleColor: 'text-orange-900', descColor: 'text-orange-800/80' },
  L: { bg: 'bg-green-50', border: 'border-green-100', icon: 'check_circle', iconColor: 'text-green-600', titleColor: 'text-green-900', descColor: 'text-green-800/80' },
}

export default function MobileApprovalDetail() {
  usePageTitle('审批详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [flow, setFlow] = useState<ApprovalFlowItem | null>(null)
  const [aiResult, setAiResult] = useState<AiResultItem | null>(null)
  const [loading, setLoading] = useState(true)
  const [deciding, setDeciding] = useState(false)
  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [rejectComment, setRejectComment] = useState('')
  // Delegate
  const [delegateModalOpen, setDelegateModalOpen] = useState(false)
  const [delegateUserId, setDelegateUserId] = useState('')
  const [delegateReason, setDelegateReason] = useState('')
  const [users, setUsers] = useState<Array<{ id: string; real_name: string }>>([])

  useEffect(() => {
    if (!id) return
    setLoading(true)
    approvalApi.get(id).then((res) => {
      if (res.data) setFlow(res.data)
    }).catch(() => message.error('加载审批详情失败'))
      .finally(() => setLoading(false))

    aiApi.listTasks({ biz_id: id }).then((res) => {
      const tasks = res.data || []
      const riskTask = tasks.find((t: any) => t.task_type === 'quote_risk' || t.task_type === 'contract_risk')
      if (riskTask?.result) setAiResult(riskTask.result)
    }).catch(() => {})
  }, [id])

  const currentTask = flow?.tasks?.find((t) => t.status === 'pending')

  const handleDecide = async (action: 'approved' | 'rejected', comment?: string) => {
    if (!currentTask) return
    setDeciding(true)
    try {
      const res = await approvalApi.decide(currentTask.id, { action, comment })
      if (res.code === 0) {
        message.success(action === 'approved' ? '已通过' : '已拒绝')
        setFlow(res.data)
      }
    } catch { message.error('操作失败') }
    finally { setDeciding(false) }
  }

  const handleReject = () => {
    handleDecide('rejected', rejectComment)
    setRejectModalOpen(false)
    setRejectComment('')
  }

  const openDelegate = async () => {
    setDelegateUserId('')
    setDelegateReason('')
    setDelegateModalOpen(true)
    try {
      const res = await client.get('/api/admin/v1/tenant/users') as any
      const list = res.data?.items || res.data || []
      setUsers(list.map((u: any) => ({ id: u.id, real_name: u.real_name || u.username })))
    } catch { setUsers([]) }
  }

  const handleDelegate = async () => {
    if (!currentTask || !delegateUserId) { message.warning('请选择审批人'); return }
    setDeciding(true)
    try {
      await approvalApi.delegate(currentTask.id, { target_user_id: delegateUserId, reason: delegateReason || undefined })
      message.success('已转交')
      setDelegateModalOpen(false)
      // Reload
      if (id) {
        const res = await approvalApi.get(id)
        if (res.data) setFlow(res.data)
      }
    } catch { message.error('转交失败') }
    finally { setDeciding(false) }
  }

  const risks: RiskItem[] = aiResult?.result_json
    ? ((aiResult.result_json as any).risks || []).map((r: any) => ({
        title: r.title || r.name || '风险项',
        description: r.description || r.detail || '',
        severity: r.severity || r.level || 'M',
      }))
    : []

  // Build key info from biz_detail
  const keyInfo = flow ? (() => {
    const detail = flow.biz_detail || {}
    const items: Array<{ label: string; value: string; dot?: string }> = []
    if (detail.margin_rate) items.push({ label: '毛利率', value: detail.margin_rate })
    if (detail.price_total) items.push({ label: '报价金额', value: detail.price_total })
    if (detail.amount_total) items.push({ label: '合同金额', value: detail.amount_total })
    if (detail.quote_no) items.push({ label: '报价编号', value: detail.quote_no })
    if (detail.contract_no) items.push({ label: '合同编号', value: detail.contract_no })
    if (detail.change_no) items.push({ label: '变更编号', value: detail.change_no })
    if (detail.change_type) items.push({ label: '变更类型', value: detail.change_type })
    if (detail.version_no) items.push({ label: '版本号', value: `V${detail.version_no}` })
    if (items.length === 0) items.push({ label: '类型', value: bizTypeLabels[flow.biz_type] || flow.biz_type })
    return items
  })() : []

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <span className="material-symbols-outlined animate-spin text-primary" style={{ fontSize: 32 }}>progress_activity</span>
      </div>
    )
  }

  if (!flow) {
    return <div className="text-center py-20 text-slate-400">审批不存在</div>
  }

  const statusText = flow.status === 'pending' ? '审批中' : flow.status === 'approved' ? '已通过' : flow.status === 'withdrawn' ? '已撤回' : '已拒绝'

  return (
    <div className="flex flex-col min-h-[calc(100vh-7rem)]">
      {/* Top Nav */}
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => navigate(-1)} className="flex items-center text-primary bg-transparent border-0 cursor-pointer p-0">
          <span className="material-symbols-outlined">arrow_back_ios</span>
        </button>
        <h2 className="text-lg font-bold text-slate-900 flex-1 text-center">审批详情</h2>
        <div className="w-10" />
      </div>

      {/* Header Info Card */}
      <div className="flex gap-4 items-center mb-4">
        <div className="bg-primary/10 flex items-center justify-center rounded-xl min-h-[5rem] w-20 border border-primary/20 shrink-0">
          <span className="material-symbols-outlined text-primary" style={{ fontSize: 36 }}>
            {bizTypeIcons[flow.biz_type] || 'description'}
          </span>
        </div>
        <div className="flex flex-col justify-center min-w-0">
          <p className="text-lg font-bold text-slate-900 leading-tight truncate">
            {flow.title || bizTypeLabels[flow.biz_type] || '审批'}
          </p>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-primary text-base font-bold">{statusText}</p>
            {flow.approval_mode && flow.approval_mode !== 'sequential' && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-purple-50 text-purple-600 font-bold">
                {modeLabels[flow.approval_mode] || flow.approval_mode}
              </span>
            )}
          </div>
          <p className="text-slate-500 text-xs mt-0.5">
            {flow.submitted_by_name || '未知'} 发起 · 节点 {flow.current_node}/{flow.total_nodes}
            {flow.revision_no && flow.revision_no > 1 && ` · 第${flow.revision_no}次提交`}
          </p>
        </div>
      </div>

      {/* Key Information */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4 mb-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">关键信息</h3>
        <div className="space-y-2">
          {keyInfo.map((item, i) => (
            <div key={item.label} className={`flex justify-between items-center py-1.5 ${i > 0 ? 'border-t border-slate-50 pt-2.5' : ''}`}>
              <span className="text-sm text-slate-500">{item.label}</span>
              <div className="flex items-center gap-1.5">
                {item.dot && <span className={`h-2 w-2 rounded-full ${item.dot}`} />}
                <span className="text-sm font-semibold text-slate-900">{item.value}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Approval Nodes */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-100 p-4 mb-4">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">审批节点</h3>
        <div className="space-y-2">
          {(flow.tasks || []).map((task) => (
            <div key={task.id} className="flex items-center gap-3 py-1.5">
              <span className={`material-symbols-outlined ${
                task.status === 'approved' ? 'text-green-500' :
                task.status === 'rejected' ? 'text-red-500' :
                task.status === 'pending' ? 'text-amber-500' :
                task.status === 'cancelled' ? 'text-slate-300' : 'text-slate-300'
              }`} style={{ fontSize: 18 }}>
                {task.status === 'approved' ? 'check_circle' :
                 task.status === 'rejected' ? 'cancel' :
                 task.status === 'pending' ? 'schedule' :
                 task.status === 'cancelled' ? 'block' : 'hourglass_empty'}
              </span>
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-slate-800">{task.assignee_name || '审批人'}</span>
                {task.comment && <p className="text-xs text-slate-500 truncate">{task.comment}</p>}
              </div>
              <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                task.status === 'approved' ? 'bg-green-50 text-green-600' :
                task.status === 'rejected' ? 'bg-red-50 text-red-600' :
                task.status === 'pending' ? 'bg-amber-50 text-amber-600' :
                task.status === 'cancelled' ? 'bg-slate-50 text-slate-400' : 'bg-slate-50 text-slate-400'
              }`}>
                {taskStatusLabels[task.status] || task.status}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* AI Risk Report */}
      {risks.length > 0 && (
        <div className="mb-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 20 }}>auto_awesome</span>
            <h3 className="text-base font-bold text-slate-900">AI 风险报告</h3>
          </div>
          <div className="space-y-3">
            {risks.map((risk, i) => {
              const cfg = severityConfig[risk.severity] || severityConfig.M
              return (
                <div key={i} className={`p-4 ${cfg.bg} rounded-xl border ${cfg.border}`}>
                  <div className="flex items-start gap-3">
                    <span className={`material-symbols-outlined ${cfg.iconColor} mt-0.5`}>{cfg.icon}</span>
                    <div>
                      <p className={`text-sm font-bold ${cfg.titleColor}`}>{risk.title}</p>
                      <p className={`text-xs mt-1 leading-relaxed ${cfg.descColor}`}>{risk.description}</p>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Spacer for bottom bar */}
      <div className="flex-1" />
      <div className="h-20" />

      {/* Bottom Action Bar */}
      {currentTask && (
        <div className="fixed bottom-14 left-0 right-0 z-10 bg-white p-4 border-t border-slate-200 flex gap-3 shadow-[0_-4px_10px_rgba(0,0,0,0.05)]">
          <button
            disabled={deciding}
            onClick={() => setRejectModalOpen(true)}
            className="flex-1 h-11 rounded-xl bg-slate-100 text-slate-900 font-bold text-sm transition-colors active:bg-slate-200 border-0 cursor-pointer disabled:opacity-50"
          >
            拒绝
          </button>
          <button
            disabled={deciding}
            onClick={() => openDelegate()}
            className="flex-[0.8] h-11 rounded-xl bg-slate-100 text-slate-900 font-bold text-sm transition-colors active:bg-slate-200 border-0 cursor-pointer disabled:opacity-50"
          >
            转交
          </button>
          <button
            disabled={deciding}
            onClick={() => handleDecide('approved')}
            className="flex-[1.5] h-11 rounded-xl bg-primary text-white font-bold text-sm shadow-lg shadow-primary/30 transition-colors active:scale-95 border-0 cursor-pointer disabled:opacity-50"
          >
            通过
          </button>
        </div>
      )}

      {/* Reject Modal */}
      <Modal
        title="拒绝审批"
        open={rejectModalOpen}
        onOk={handleReject}
        onCancel={() => setRejectModalOpen(false)}
        okText="确认拒绝"
        cancelText="取消"
      >
        <Input.TextArea
          value={rejectComment}
          onChange={(e) => setRejectComment(e.target.value)}
          placeholder="请输入拒绝原因"
          rows={3}
        />
      </Modal>

      {/* Delegate Modal */}
      <Modal
        title="转交审批"
        open={delegateModalOpen}
        onOk={handleDelegate}
        onCancel={() => setDelegateModalOpen(false)}
        okText="确认转交"
        cancelText="取消"
      >
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">选择审批人</label>
            <Select
              className="w-full"
              placeholder="选择用户"
              value={delegateUserId || undefined}
              onChange={setDelegateUserId}
              showSearch
              optionFilterProp="label"
              options={users.map((u) => ({ value: u.id, label: u.real_name }))}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700 mb-1 block">转交原因（选填）</label>
            <Input.TextArea
              value={delegateReason}
              onChange={(e) => setDelegateReason(e.target.value)}
              placeholder="转交原因"
              rows={2}
            />
          </div>
        </div>
      </Modal>
    </div>
  )
}
