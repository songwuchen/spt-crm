// 流程动态侧栏（对齐简道云 / 审批中心右侧；移动端同组件、page 布局）
import { useState } from 'react'
import { Avatar, Button, Input, Modal, Tag, Tabs, Typography, message } from 'antd'
import type { WfFlowStep, WfInstanceDetail } from '@/types/lowcode'
import { WF_ACTION_TEXT as ACTION_TXT } from '@/utils/lowcodeWorkflowLabels'

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

function stepDotColor(step: WfFlowStep) {
  if (step.is_current || step.status === 'running') return '#1677ff'
  if (step.status === 'rejected') return '#ef4444'
  if (step.status === 'completed') return '#12b876'
  if (step.status === 'cancelled') return '#94a3b8'
  return '#cbd5e1'
}

function stepTagColor(step: WfFlowStep) {
  if (step.node_type === 'cc') return 'default'
  if (step.status === 'rejected') return 'error'
  if (step.is_current || step.status === 'running') return 'processing'
  if (step.status === 'completed') return 'success'
  return 'default'
}

function stepTagText(step: WfFlowStep) {
  if (step.node_type === 'cc') return '抄送'
  return step.status_text || step.status
}

function avatarLetter(name: string) {
  const t = (name || '').trim()
  return t ? t.slice(0, 1) : '?'
}

export default function WfFlowDynamics({
  steps, comments, tab, onTabChange, onSubmitComment, commenting, variant = 'drawer',
}: {
  steps: WfFlowStep[]
  comments: WfInstanceDetail['comments']
  tab?: string
  onTabChange?: (key: string) => void
  onSubmitComment?: (content: string) => Promise<void>
  commenting?: boolean
  /** drawer=PC 右侧栏；page=移动端整页嵌入 */
  variant?: 'drawer' | 'page'
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
        items={[
          { key: 'flow', label: '流程动态' },
          { key: 'comments', label: `评论${comments?.length ? ` (${comments.length})` : ''}` },
        ]}
      />
      {active === 'flow' ? (
        <div className={isPage ? 'px-3 pb-4' : 'flex-1 overflow-y-auto px-3 pb-4'}>
          <div className="relative pl-4">
            <div className="absolute left-[7px] top-2 bottom-2 w-px bg-slate-200" />
            {(steps || []).length === 0 && (
              <Text type="secondary" className="text-sm">暂无流程动态</Text>
            )}
            {(steps || []).map((s) => {
              const isCc = s.node_type === 'cc'
              const ccPeople = isCc ? (s.assignees || []) : []
              return (
                <div key={s.node_instance_id} className="relative mb-4 pl-4">
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
                    {s.action && s.action !== 'pending' && !isCc && (
                      <div className="text-sm text-slate-500 mt-0.5">
                        操作：{ACTION_TXT[s.action] || s.action}
                      </div>
                    )}
                    {s.opinion && (
                      <div className="text-sm text-slate-500 mt-0.5">意见：{s.opinion}</div>
                    )}
                    {isCc && ccPeople.length > 0 && (
                      <button
                        type="button"
                        className="mt-1.5 inline-flex items-center rounded px-2 py-0.5 text-xs font-medium text-amber-800 bg-amber-50 border border-amber-200 hover:bg-amber-100"
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
