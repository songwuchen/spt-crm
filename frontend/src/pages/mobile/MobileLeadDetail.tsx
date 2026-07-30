import { useState, useEffect } from 'react'
import MobileIcon from '@/components/MobileIcon'
import { useParams, useNavigate } from 'react-router-dom'
import { message, Modal, Input, Select } from 'antd'
import { leadApi } from '@/api/lead'
import { workflowApi } from '@/api/lowcodeWorkflow'
import type { WfTodoItem } from '@/types/lowcode'
import { usePageTitle } from '@/hooks/usePageTitle'
import { leadReviewStatusConfig, customerNewnessLabels } from '@/constants/labels'
import LeadIntelReviewForm from '@/components/lead/LeadIntelReviewForm'

interface LeadItem {
  id: string; lead_code: string; title: string; company_name: string | null
  contact_name: string | null; contact_phone: string | null; contact_email: string | null
  source: string | null; status: string; score: number | null
  demand_summary: string | null; industry: string | null; region: string | null
  reporter_name?: string | null; reported_at?: string | null
  owner_name: string | null
  department_name?: string | null; created_at: string
  review_status?: string; reject_reason?: string | null
  customer_newness?: string | null; review_opinion?: string | null
}

const statusMap: Record<string, { label: string; color: string }> = {
  new: { label: '新建', color: 'bg-blue-100 text-blue-700' },
  following: { label: '跟进中', color: 'bg-amber-100 text-amber-700' },
  qualified: { label: '已转化', color: 'bg-emerald-100 text-emerald-700' },
  discarded: { label: '已废弃', color: 'bg-slate-100 text-slate-500' },
}

const statusOptions = [
  { value: 'new', label: '新建' },
  { value: 'following', label: '跟进中' },
  { value: 'qualified', label: '已转化' },
  { value: 'discarded', label: '已废弃' },
]

export default function MobileLeadDetail() {
  usePageTitle('线索详情')
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [lead, setLead] = useState<LeadItem | null>(null)
  const [myTask, setMyTask] = useState<WfTodoItem | null>(null)
  const [editModal, setEditModal] = useState(false)
  const [editForm, setEditForm] = useState<Record<string, string | null>>({})

  const loadLead = () => {
    if (!id) return
    leadApi.get(id).then((r: any) => setLead(r.data)).catch(() => message.error('加载失败'))
  }

  const loadMyTask = async () => {
    if (!id) return
    try {
      const res = await workflowApi.todo({ pageNo: 1, pageSize: 20, biz_type: 'lead', biz_id: id })
      const t = (res.data?.items || []).find((p) => p.status === 'pending')
      setMyTask(t || null)
    } catch { setMyTask(null) }
  }

  useEffect(() => { loadLead(); loadMyTask() }, [id])

  const openEdit = () => {
    if (!lead) return
    setEditForm({
      title: lead.title,
      company_name: lead.company_name,
      contact_name: lead.contact_name,
      contact_phone: lead.contact_phone,
      contact_email: lead.contact_email,
      demand_summary: lead.demand_summary,
      status: lead.status,
    })
    setEditModal(true)
  }

  const handleSave = async () => {
    if (!id) return
    try {
      await leadApi.update(id, editForm)
      message.success('已更新')
      setEditModal(false)
      loadLead()
    } catch {
      message.error('更新失败')
    }
  }

  const handleResubmit = async () => {
    if (!id) return
    try {
      await leadApi.submitReview(id)
      message.success('已重新提交审核')
      loadLead()
    } catch {
      message.error('提交审核失败')
    }
  }

  const handleQualify = () => {
    if (!id) return
    let createOpp = true
    Modal.confirm({
      title: '确认转化',
      content: (
        <div>
          <p className="mb-2">将此线索转化为客户？转化后线索状态将变为「已转化」。</p>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" defaultChecked onChange={(e) => { createOpp = e.target.checked }} />
            同时创建商机
          </label>
        </div>
      ),
      onOk: async () => {
        try {
          const res = await leadApi.qualify(id, createOpp)
          message.success(res.data.project_code
            ? `已转化客户并创建商机 ${res.data.project_code}`
            : `已转化为客户: ${res.data.customer_name}`)
          loadLead()
        } catch {
          message.error('转化失败')
        }
      },
    })
  }

  const handleStatusChange = (newStatus: string) => {
    if (!id || !lead) return
    Modal.confirm({
      title: '确认变更状态',
      content: `将线索状态改为「${statusMap[newStatus]?.label || newStatus}」？`,
      onOk: async () => {
        await leadApi.update(id, { status: newStatus })
        message.success('状态已更新')
        loadLead()
      },
    })
  }

  if (!lead) return <div className="text-center py-12 text-slate-400">加载中...</div>

  const st = statusMap[lead.status] || statusMap.new
  const reviewStatus = lead.review_status || 'approved'
  const reviewApproved = reviewStatus === 'approved'
  const reviewCfg = !reviewApproved ? leadReviewStatusConfig[reviewStatus] : null
  const canOperate = lead.status !== 'qualified' && lead.status !== 'discarded'

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <button onClick={() => navigate(-1)} className="text-slate-400">
          <MobileIcon name="arrow_back" style={{ fontSize: 20 }} />
        </button>
        <h1 className="text-lg font-extrabold text-slate-900 flex-1">{lead.title}</h1>
        <span className={`px-2 py-0.5 rounded text-[12px] font-bold ${st.color}`}>{st.label}</span>
      </div>

      {/* 待我情报审批 */}
      {myTask && (
        <div className="rounded-xl border border-primary/30 bg-primary/5 p-3 mb-3">
          <div className="text-sm font-bold text-slate-900 mb-2">该线索待您审批</div>
          <LeadIntelReviewForm
            compact
            leadId={id!}
            taskId={myTask.task_id}
            initialNewness={lead.customer_newness}
            initialOpinion={lead.review_opinion}
            initialReturnReason={lead.reject_reason}
            onDone={(decision) => {
              if (decision === 'draft') {
                loadLead()
              } else {
                setMyTask(null)
                loadLead()
              }
            }}
          />
        </div>
      )}

      {/* Review status banner */}
      {reviewCfg && (
        <div className={`rounded-xl border ${reviewCfg.border} ${reviewCfg.bg} p-3 mb-3`}>
          <div className={`flex items-center gap-1.5 text-sm font-bold ${reviewCfg.text}`}>
            <MobileIcon name={reviewStatus === 'pending' ? 'hourglass_top' : 'gpp_bad'} style={{ fontSize: 18 }} />
            {reviewStatus === 'pending' && '待内勤审核'}
            {reviewStatus === 'rejected' && '已回退'}
            {reviewStatus === 'attacked' && '已标记袭击'}
          </div>
          {reviewStatus === 'rejected' && (
            <div className="text-sm text-slate-600 mt-1">
              {lead.reject_reason ? `回退原因：${lead.reject_reason}` : '请修改后重新提交审核。'}
            </div>
          )}
          {reviewStatus === 'attacked' && (
            <div className="text-sm text-slate-600 mt-1">袭击状态不可转化为客户。</div>
          )}
          {reviewStatus === 'rejected' && (
            <button onClick={handleResubmit}
              className="mt-2 w-full py-2 bg-primary text-white rounded-lg text-sm font-bold">
              重新提交审核
            </button>
          )}
        </div>
      )}

      {reviewApproved && canOperate && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 mb-3">
          <div className="text-sm font-bold text-emerald-700">线索已收录</div>
          <div className="text-sm text-slate-600 mt-1">请确认是否转化为客户/商机，也可先跟进再转化。</div>
          <button onClick={handleQualify}
            className="mt-2 w-full py-2 bg-emerald-600 text-white rounded-lg text-sm font-bold">
            转化为客户
          </button>
        </div>
      )}

      <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 space-y-3">
        <div className="flex justify-between">
          <span className="text-sm text-slate-400">编码</span>
          <span className="text-sm font-mono text-slate-600">{lead.lead_code}</span>
        </div>
        {lead.customer_newness && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">新/老客户</span>
            <span className="text-sm text-slate-700">{customerNewnessLabels[lead.customer_newness] || lead.customer_newness}</span>
          </div>
        )}
        {lead.company_name && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">公司</span>
            <span className="text-sm font-bold text-slate-800">{lead.company_name}</span>
          </div>
        )}
        {lead.contact_name && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">联系人</span>
            <span className="text-sm text-slate-700">{lead.contact_name}</span>
          </div>
        )}
        {lead.contact_phone && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">电话</span>
            <a href={`tel:${lead.contact_phone}`} className="text-sm text-primary font-bold">{lead.contact_phone}</a>
          </div>
        )}
        {lead.contact_email && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">邮箱</span>
            <span className="text-sm text-slate-600">{lead.contact_email}</span>
          </div>
        )}
        {lead.source && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">来源</span>
            <span className="text-sm text-slate-600">{lead.source}</span>
          </div>
        )}
        {lead.industry && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">行业</span>
            <span className="text-sm text-slate-600">{lead.industry}</span>
          </div>
        )}
        {lead.region && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">地区</span>
            <span className="text-sm text-slate-600">{lead.region}</span>
          </div>
        )}
        {lead.score != null && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">评分</span>
            <span className="text-sm font-bold text-amber-600">{lead.score}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-sm text-slate-400">报备人</span>
          <span className="text-sm text-slate-600">{lead.reporter_name || '-'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-sm text-slate-400">报备时间</span>
          <span className="text-sm text-slate-600">
            {lead.reported_at ? new Date(lead.reported_at).toLocaleString('zh-CN') : '-'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-sm text-slate-400">负责人</span>
          <span className="text-sm text-slate-600">{lead.owner_name || '-'}</span>
        </div>
        {lead.department_name && (
          <div className="flex justify-between">
            <span className="text-sm text-slate-400">部门</span>
            <span className="text-sm text-slate-600">{lead.department_name}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-sm text-slate-400">创建时间</span>
          <span className="text-sm text-slate-500">{lead.created_at ? new Date(lead.created_at).toLocaleDateString('zh-CN') : '-'}</span>
        </div>
      </div>

      {lead.demand_summary && (
        <div className="bg-white rounded-xl border border-slate-100 shadow-sm p-4 mt-3">
          <h3 className="text-sm font-bold text-slate-400 uppercase mb-2">需求摘要</h3>
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{lead.demand_summary}</p>
        </div>
      )}

      {/* Action Buttons — 已转化/已废弃不可再编辑 */}
      {lead.status !== 'qualified' && lead.status !== 'discarded' && (
      <div className="mt-4 flex gap-2">
        <button onClick={openEdit}
          className="flex-1 py-2.5 bg-primary text-white rounded-xl text-sm font-bold flex items-center justify-center gap-1">
          <MobileIcon name="edit" style={{ fontSize: 16 }} />
          编辑
        </button>
        {lead.status === 'new' && (
          <button onClick={() => handleStatusChange('following')}
            className="flex-1 py-2.5 bg-amber-500 text-white rounded-xl text-sm font-bold">
            开始跟进
          </button>
        )}
        {lead.status === 'following' && reviewApproved && (
          <button onClick={handleQualify}
            className="flex-1 py-2.5 bg-emerald-500 text-white rounded-xl text-sm font-bold">
            转化为客户
          </button>
        )}
        <button onClick={() => handleStatusChange('discarded')}
          className="py-2.5 px-4 bg-slate-100 text-slate-500 rounded-xl text-sm font-bold">
          废弃
        </button>
      </div>
      )}
      {lead.status === 'qualified' && (
        <div className="mt-4 py-3 px-4 bg-emerald-50 text-emerald-700 rounded-xl text-sm text-center">
          已转化为客户，不可再编辑
        </div>
      )}

      {/* Edit Modal */}
      <Modal title="编辑线索" open={editModal} onOk={handleSave} onCancel={() => setEditModal(false)} width="90%">
        <div className="space-y-3">
          <div>
            <label className="text-sm text-slate-500 mb-1 block">标题</label>
            <Input value={editForm.title || ''} onChange={(e) => setEditForm({ ...editForm, title: e.target.value })} />
          </div>
          <div>
            <label className="text-sm text-slate-500 mb-1 block">公司</label>
            <Input value={editForm.company_name || ''} onChange={(e) => setEditForm({ ...editForm, company_name: e.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm text-slate-500 mb-1 block">联系人</label>
              <Input value={editForm.contact_name || ''} onChange={(e) => setEditForm({ ...editForm, contact_name: e.target.value })} />
            </div>
            <div>
              <label className="text-sm text-slate-500 mb-1 block">电话</label>
              <Input value={editForm.contact_phone || ''} onChange={(e) => setEditForm({ ...editForm, contact_phone: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="text-sm text-slate-500 mb-1 block">邮箱</label>
            <Input value={editForm.contact_email || ''} onChange={(e) => setEditForm({ ...editForm, contact_email: e.target.value })} />
          </div>
          <div>
            <label className="text-sm text-slate-500 mb-1 block">状态</label>
            <Select className="w-full" value={editForm.status || 'new'} onChange={(v) => setEditForm({ ...editForm, status: v })}
              options={statusOptions} />
          </div>
          <div>
            <label className="text-sm text-slate-500 mb-1 block">需求摘要</label>
            <Input.TextArea rows={3} value={editForm.demand_summary || ''}
              onChange={(e) => setEditForm({ ...editForm, demand_summary: e.target.value })} />
          </div>
        </div>
      </Modal>
    </div>
  )
}
