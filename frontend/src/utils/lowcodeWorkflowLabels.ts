// 扩展平台审批流程 —— 状态/动作标签的单一来源(桌面 antd + 移动 Tailwind 共用)。
// 桌面用 color(antd Tag), 移动用 cls(Tailwind), text 两端共用。新增状态/动作只需改这里。

export const WF_ACTION_TEXT: Record<string, string> = {
  submit: '发起', approve: '通过', reject: '驳回', transfer: '转交', comment: '评论',
  withdraw: '撤回', auto_approve: '自动通过', auto_reject: '自动终止', return: '退回',
  urge: '催办', auto_transfer: '自动转交', timeout: '超时提醒', cc: '抄送',
}

export interface WfStatusMeta { text: string; color: string; cls: string }

/** 表单实例 / 流程实例状态（列表、详情底栏、审批抽屉共用） */
export const FORM_INSTANCE_STATUS: Record<string, WfStatusMeta> = {
  draft: { text: '草稿', color: 'default', cls: 'bg-slate-100 text-slate-500' },
  submitted: { text: '已提交', color: 'blue', cls: 'bg-blue-50 text-blue-600' },
  running: { text: '审批中', color: 'gold', cls: 'bg-amber-50 text-amber-600' },
  completed: { text: '已通过', color: 'green', cls: 'bg-green-50 text-green-600' },
  rejected: { text: '已驳回', color: 'red', cls: 'bg-red-50 text-red-600' },
  returned: { text: '已退回', color: 'orange', cls: 'bg-orange-50 text-orange-600' },
  withdrawn: { text: '已撤回', color: 'default', cls: 'bg-slate-100 text-slate-500' },
  cancelled: { text: '已作废', color: 'default', cls: 'bg-slate-100 text-slate-400' },
  terminated: { text: '已终止', color: 'red', cls: 'bg-red-50 text-red-600' },
}

export const WF_STATUS: Record<string, WfStatusMeta> = {
  running: FORM_INSTANCE_STATUS.running,
  completed: FORM_INSTANCE_STATUS.completed,
  rejected: FORM_INSTANCE_STATUS.rejected,
  returned: FORM_INSTANCE_STATUS.returned,
  withdrawn: FORM_INSTANCE_STATUS.withdrawn,
  cancelled: FORM_INSTANCE_STATUS.cancelled,
  terminated: FORM_INSTANCE_STATUS.terminated,
}
