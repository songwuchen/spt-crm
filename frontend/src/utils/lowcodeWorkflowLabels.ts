// 扩展平台审批流程 —— 状态/动作标签的单一来源(桌面 antd + 移动 Tailwind 共用)。
// 桌面用 color(antd Tag), 移动用 cls(Tailwind), text 两端共用。新增状态/动作只需改这里。

export const WF_ACTION_TEXT: Record<string, string> = {
  submit: '发起', approve: '通过', reject: '驳回', transfer: '转交', comment: '评论',
  withdraw: '撤回', auto_approve: '自动通过', auto_reject: '自动终止', return: '退回',
  urge: '催办', auto_transfer: '自动转交', timeout: '超时提醒',
}

export interface WfStatusMeta { text: string; color: string; cls: string }

export const WF_STATUS: Record<string, WfStatusMeta> = {
  running: { text: '审批中', color: 'gold', cls: 'bg-amber-50 text-amber-600' },
  completed: { text: '已通过', color: 'green', cls: 'bg-green-50 text-green-600' },
  rejected: { text: '已驳回', color: 'red', cls: 'bg-red-50 text-red-600' },
  withdrawn: { text: '已撤回', color: 'default', cls: 'bg-slate-100 text-slate-500' },
}
