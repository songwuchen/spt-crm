// 新旧两套审批引擎的「待我审批」聚合。
//
// 背景：系统同时存在旧 approval 引擎（approval_flows/approval_tasks，API /api/v1/approvals）
// 与新的可视化工作流引擎（wf_* 表，API /api/v1/lc/wf）。业务按 biz_type 逐个从旧引擎切到
// 新引擎，切换期间一个人的待办会分散在两套表里，而两套 API、两个审批中心页面互不聚合 ——
// 用户会在首页/审批中心看不到已经切过去的业务的待办。
//
// 这里把两边归一成同一种条目并提供统一的审批动作，调用方（首页待办卡、审批中心、移动端）
// 只需消费 UnifiedPendingItem，不必关心条目来自哪套引擎。
import { approvalApi } from './approval'
import { workflowApi } from './lowcodeWorkflow'

export type ApprovalEngine = 'legacy' | 'wf'

/** 单页最多取多少条待办。两套引擎的分页上限都是 100。 */
const PAGE_SIZE = 100

export interface UnifiedPendingItem {
  /** React key / 去重用，跨引擎唯一 */
  key: string
  /** 审批动作要用的 task id（各自引擎内的主键） */
  taskId: string
  engine: ApprovalEngine
  title: string
  /** 副标题：提交人、节点进度等，已按各引擎能提供的信息拼好 */
  subtitle: string
  bizType?: string | null
  bizId?: string | null
  /** 新引擎的流程实例 id（旧引擎为 flow id），用于跳详情 */
  instanceId?: string
  createdAt?: string
}

export interface UnifiedPendingResult {
  items: UnifiedPendingItem[]
  /** 两套引擎的待办总数之和。items 受分页上限限制，计数请用这个值。 */
  total: number
}

/**
 * 拉取当前用户在两套引擎里的待办。
 *
 * 任一侧失败不影响另一侧（仍返回另一侧的结果）；**两侧都失败时抛错**，否则调用方
 * 无法把「真的没有待办」和「后端挂了」区分开，会把故障渲染成「暂无待审批」。
 */
export async function fetchUnifiedPending(): Promise<UnifiedPendingResult> {
  const [legacy, wf] = await Promise.allSettled([
    approvalApi.myPending(),
    // 注意：该端点的分页参数是 pageNo/pageSize（camelCase），写成 page_no/page_size
    // 会被 FastAPI 忽略并静默退回默认的 20 条
    workflowApi.todo({ pageNo: 1, pageSize: PAGE_SIZE }),
  ])

  if (legacy.status === 'rejected' && wf.status === 'rejected') {
    throw legacy.reason
  }

  const out: UnifiedPendingItem[] = []
  let total = 0

  if (legacy.status === 'fulfilled') {
    const rows = legacy.value.data || []
    total += rows.length
    for (const it of rows) {
      out.push({
        key: `legacy:${it.id}`,
        taskId: it.id,
        engine: 'legacy',
        title: it.flow?.title || it.flow?.biz_type || '审批',
        subtitle: [
          it.flow?.submitted_by_name ? `${it.flow.submitted_by_name} 发起` : '',
          it.flow?.total_nodes ? `节点 ${it.node_order}/${it.flow.total_nodes}` : '',
        ].filter(Boolean).join(' · '),
        bizType: it.flow?.biz_type,
        bizId: it.flow?.biz_id,
        // flow_id 是待办自身的一级字段，比 flow?.id 可靠（flow 关联体可能未展开）
        instanceId: it.flow_id || it.flow?.id,
        createdAt: it.created_at,
      })
    }
  }

  if (wf.status === 'fulfilled') {
    total += wf.value.data?.total ?? 0
    for (const it of wf.value.data?.items || []) {
      if (it.status !== 'pending') continue
      out.push({
        key: `wf:${it.task_id}`,
        taskId: it.task_id,
        engine: 'wf',
        title: it.title || it.business_no || '审批',
        subtitle: [
          it.initiator_name ? `${it.initiator_name} 发起` : '',
          it.on_behalf_of && it.delegator_name ? `代 ${it.delegator_name} 审批` : '',
        ].filter(Boolean).join(' · '),
        bizType: it.biz_type,
        bizId: it.biz_id,
        instanceId: it.process_instance_id,
        createdAt: it.created_at,
      })
    }
  }

  return { items: out, total }
}

/** 统一的通过/驳回，按条目所属引擎分派到对应 API。 */
export async function decideUnified(
  item: UnifiedPendingItem,
  action: 'approve' | 'reject',
  comment?: string,
): Promise<void> {
  if (item.engine === 'wf') {
    await workflowApi.act(item.taskId, { action, opinion: comment })
    return
  }
  await approvalApi.decide(item.taskId, {
    action: action === 'approve' ? 'approved' : 'rejected',
    comment,
  })
}
