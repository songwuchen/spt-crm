// 流程动态侧栏（对齐简道云 / 审批中心右侧；移动端同组件、page 布局）
import { useState } from 'react'
import { Avatar, Button, Input, Modal, Tag, Tabs, Typography, message } from 'antd'
import type { WfFlowStep, WfInstanceDetail } from '@/types/lowcode'
import { WF_ACTION_TEXT as ACTION_TXT } from '@/utils/lowcodeWorkflowLabels'
import DataLog from '@/components/DataLog'

const { Text } = Typography

function fmtTime(v?: string | null) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return v
  return d.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).replace(/\//g, '-')
}

function isReviseStep(step: WfFlowStep) {
  return step.node_type === 'revise'
    || step.node_def_id === '__initiator_revise__'
    || (step.node_name || '').includes('修改并重新提交')
}

function stepDotColor(step: WfFlowStep) {
  if (step.is_current || step.status === 'running') return '#1677ff'
  if (step.status === 'rejected') return '#ef4444'
  if (step.status === 'returned') return '#f97316'
  if (step.status === 'completed') return '#12b876'
  if (step.status === 'cancelled') return '#94a3b8'
  return '#cbd5e1'
}

function stepTagColor(step: WfFlowStep) {
  if (step.node_type === 'cc' || step.action === 'cc') return 'default'
  if (step.status === 'rejected') return 'error'
  if (step.status === 'returned') return 'warning'
  if (step.is_current || step.status === 'running') return 'processing'
  if (step.status === 'completed') return 'success'
  return 'default'
}

function stepTagText(step: WfFlowStep) {
  if (step.node_type === 'cc' || step.action === 'cc') return '抄送'
  if (step.action === 'auto_approve') return '自动通过'
  if (isReviseStep(step) && (step.is_current || step.status === 'running')) return '待修改'
  return step.status_text || step.status
}

function isCcStep(step: WfFlowStep) {
  // 独立抄送节点，或审批节点「启用抄送」落库的卡片（node_type=approval + action=cc）
  return step.node_type === 'cc' || step.action === 'cc'
}

function avatarLetter(name: string) {
  const t = (name || '').trim()
  return t ? t.slice(0, 1) : '?'
}

export default function WfFlowDynamics({
  steps, comments, tab, onTabChange, onSubmitComment, commenting, variant = 'drawer',
  dataLog,
}: {
  steps: WfFlowStep[]
  comments: WfInstanceDetail['comments']
  tab?: string
  onTabChange?: (key: string) => void
  onSubmitComment?: (content: string) => Promise<void>
  commenting?: boolean
  /** drawer=PC 右侧栏；page=移动端整页嵌入 */
  variant?: 'drawer' | 'page'
  /** 数据日志（对齐简道云「数据日志」Tab） */
  dataLog?: {
    resourceType: string
    resourceId: string
    fieldLabels?: Record<string, string>
    alsoResources?: Array<{ resourceType: string; resourceId: string }>
  }
}) {
  const [innerTab, setInnerTab] = useState('flow')
  const [draft, setDraft] = useState('')
  const [ccStep, setCcStep] = useState<WfFlowStep | null>(null)
  const active = tab ?? innerTab
  const setActive = onTabChange ?? setInnerTab
  const isPage = variant === 'page'

  const send = async () => {
    const text = draft.trim()
    if (!text) {
      message.error('请填写评论内容')
      return
    }
    if (!onSubmitComment) return
    await onSubmitComment(text)
    setDraft('')
  }

  const tabItems = [
    { key: 'flow', label: '流程动态' },
    ...(dataLog ? [{ key: 'dataLog', label: '数据日志' }] : []),
    { key: 'comments', label: `评论${comments?.length ? ` (${comments.length})` : ''}` },
  ]

  return (
    <div className={isPage
      ? 'flex flex-col bg-white rounded-xl border border-slate-100 overflow-hidden'
      : 'h-full min-h-0 flex flex-col bg-slate-50'}
    >
      <Tabs
        size="small"
        activeKey={active}
        onChange={setActive}
        className="px-3 pt-2 shrink-0"
        items={tabItems}
      />
      {active === 'flow' ? (
        <div className={isPage ? 'px-3 pb-4' : 'flex-1 overflow-y-auto px-3 pb-4'}>
          <div className="relative pl-4">
            <div className="absolute left-[7px] top-2 bottom-2 w-px bg-slate-200" />
            {(steps || []).length === 0 && (
              <Text type="secondary" className="text-sm">暂无流程动态</Text>
            )}
            {(steps || []).map((s, idx) => {
              const isCc = isCcStep(s)
              return (
                <div key={s.step_key || `${s.node_instance_id}:${idx}`} className="relative mb-4 pl-4">
                  <span
                    className="absolute left-[-9px] top-1.5 w-2.5 h-2.5 rounded-full border-2 border-white shadow-sm"
                    style={{ background: stepDotColor(s) }}
                  />
                  <div className={`rounded-lg border p-3 ${s.is_current ? 'border-blue-300 bg-blue-50/60' : s.status === 'rejected' ? 'border-red-200 bg-red-50/40' : 'border-slate-200 bg-white'}`}>
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-semibold text-slate-800 text-sm">{s.node_name}</span>
                      <Tag color={stepTagColor(s)} className="m-0">
                        {stepTagText(s)}
                      </Tag>
                    </div>
                    {s.handler_name && (
                      <div className="text-sm text-slate-600">
                        {isCc ? '处理人' : s.is_current ? '当前负责人' : '处理人'}
                        ：
                        <span className="font-medium text-slate-800">{s.handler_name}</span>
                      </div>
                    )}
                    {/* 会签等多人节点：列出每位审批人状态（避免只显示最后操作人）；抄送不在此列名单 */}
                    {!isCc && (s.assignees || []).length > 1 && (
                      <div className="text-sm text-slate-500 mt-0.5 space-y-0.5">
                        {(s.assignees || []).filter((a) => a.status !== 'cancelled').map((a) => {
                          const st =
                            a.status === 'pending' ? '待处理'
                              : a.status === 'approved' ? '已通过'
                                : a.status === 'waiting' ? '排队中'
                                  : a.status === 'rejected' ? '已驳回'
                                    : a.status === 'returned' ? '已退回'
                                    : a.status
                          return (
                            <div key={a.id}>
                              {a.name}
                              <span className={a.status === 'pending' ? ' text-blue-600' : ''}>
                                （{st}）
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {s.action && s.action !== 'pending' && !isCc && (
                      <div className="text-sm text-slate-500 mt-0.5">
                        操作：{ACTION_TXT[s.action] || s.action}
                      </div>
                    )}
                    {s.opinion && !isCc && (
                      <div className="text-sm text-slate-500 mt-0.5">意见：{s.opinion}</div>
                    )}
                    {isCc && (
                      <button
                        type="button"
                        className="mt-1.5 text-sm text-amber-600 hover:text-amber-700 hover:underline"
                        onClick={() => setCcStep(s)}
                      >
                        查看抄送详情
                      </button>
                    )}
                    <div className="text-xs text-slate-400 mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5">
                      {s.started_at && <span>开始 {fmtTime(s.started_at)}</span>}
                      {s.completed_at && <span>完成 {fmtTime(s.completed_at)}</span>}
                      {s.duration && <span>耗时 {s.duration}</span>}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      ) : active === 'dataLog' && dataLog ? (
        <div className={isPage ? 'px-3 pb-4' : 'flex-1 overflow-y-auto px-3 pb-4'}>
          <DataLog
            resourceType={dataLog.resourceType}
            resourceId={dataLog.resourceId}
            alsoResources={dataLog.alsoResources}
            fieldLabels={dataLog.fieldLabels}
          />
        </div>
      ) : (
        <div className={isPage ? 'flex flex-col' : 'flex-1 min-h-0 flex flex-col'}>
          <div className={isPage ? 'px-3 pb-2 space-y-3' : 'flex-1 overflow-y-auto px-3 pb-2 space-y-3'}>
            {(comments || []).length === 0 && (
              <Text type="secondary" className="text-sm">暂无评论，可在下方发表讨论</Text>
            )}
            {(comments || []).map((c, i) => (
              <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="text-sm font-medium text-slate-800">{c.user_name || c.user_id}</div>
                <div className="text-sm text-slate-600 mt-1 whitespace-pre-wrap">{c.content}</div>
                <div className="text-xs text-slate-400 mt-1">{fmtTime(c.at)}</div>
              </div>
            ))}
          </div>
          {onSubmitComment && (
            <div className="shrink-0 border-t border-slate-200 bg-white p-3 space-y-2">
              <Input.TextArea
                rows={3}
                placeholder="发表评论（讨论留言，不影响审批流转）"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                maxLength={2000}
              />
              <div className="flex justify-end">
                <Button
                  type="primary"
                  size="small"
                  loading={commenting}
                  onClick={send}
                >
                  发表评论
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      <Modal
        title="抄送人"
        open={!!ccStep}
        onCancel={() => setCcStep(null)}
        footer={null}
        width={420}
        destroyOnClose
      >
        {ccStep && (
          <div>
            <div className="text-sm text-slate-500 mb-3">
              {fmtTime(ccStep.completed_at || ccStep.started_at)}
            </div>
            <div className="rounded-lg bg-slate-50 border border-slate-100 p-3">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {(ccStep.assignees || []).map((p) => (
                  <div key={p.id} className="flex items-center gap-2 min-w-0">
                    <Avatar size={28} className="bg-emerald-500 shrink-0 text-xs">
                      {avatarLetter(p.name)}
                    </Avatar>
                    <span className="text-sm text-slate-800 truncate">{p.name}</span>
                  </div>
                ))}
              </div>
              {(ccStep.assignees || []).length === 0 && (
                <Text type="secondary" className="text-sm">暂无抄送人</Text>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
