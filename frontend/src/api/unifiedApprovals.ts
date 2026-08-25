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

/** 侧栏角标等：审批待办变化时派发，便于立即刷新计数 */
export const APPROVAL_PENDING_CHANGED = 'spt:approval-pending-changed'

/** 单页条数：过大时 WF enrich / 旧引擎 list 会明显拖慢审批中心首屏 */
const PAGE_SIZE = 40
const PAGE_SIZE_FILTERED = 100

import type { FormFilterDsl } from '@/components/lowcode/formInstanceFilterUtils'

export interface ApprovalListFilters {
  keyword?: string
  processDefinitionId?: string
  formCode?: string
  nodeName?: string
  initiatorId?: string
  createdFrom?: string
  createdTo?: string
  /** 流程表单字段筛选（需先选流程表单） */
  formFilters?: FormFilterDsl | null
}

export interface WfFilterProcessOption {
  id: string
  name: string
  form_code?: string | null
}

export interface WfFilterOptions {
  processes: WfFilterProcessOption[]
  node_names: string[]
  fields?: Array<{ id: string; label: string; type: string; options?: unknown[] }>
}

export function countActiveFilters(f?: ApprovalListFilters): number {
  if (!f) return 0
  let n = 0
  if (f.keyword?.trim()) n++
  if (f.processDefinitionId) n++
  if (f.nodeName) n++
  if (f.initiatorId) n++
  if (f.createdFrom || f.createdTo) n++
  n += f.formFilters?.rules?.length || 0
  return n
}

function toWfFilterParams(filters?: ApprovalListFilters): Record<string, unknown> {
  if (!filters || !countActiveFilters(filters)) return {}
  const params: Record<string, unknown> = {
    keyword: filters.keyword?.trim() || undefined,
    process_definition_id: filters.processDefinitionId,
    form_code: filters.formCode,
    node_name: filters.nodeName,
    initiator_id: filters.initiatorId,
    created_from: filters.createdFrom,
    created_to: filters.createdTo,
  }
  if (filters.formFilters?.rules?.length) {
    params.form_filters = JSON.stringify(filters.formFilters)
  }
  return params
}

/** 旧引擎条目客户端筛选（新引擎走服务端） */
export function matchesClientFilters(
  item: {
    title?: string
    subtitle?: string
    processName?: string | null
    nodeName?: string | null
    initiatorId?: string | null
    businessNo?: string | null
    createdAt?: string
    bizType?: string | null
    engine?: ApprovalEngine
  },
  filters?: ApprovalListFilters,
  processNameById?: Map<string, string>,
): boolean {
  if (!filters || !countActiveFilters(filters)) return true
  if (filters.processDefinitionId && item.engine === 'legacy') {
    const pname = processNameById?.get(filters.processDefinitionId)
    if (pname && !(item.title || '').includes(pname) && item.bizType !== pname) {
      return false
    }
  }
  if (filters.keyword?.trim()) {
    const kw = filters.keyword.trim().toLowerCase()
    const hay = [
      item.title, item.subtitle, item.processName, item.businessNo, item.bizType,
    ].filter(Boolean).join(' ').toLowerCase()
    if (!hay.includes(kw)) return false
  }
  if (filters.nodeName) {
    const nodeHay = (item.nodeName || item.subtitle || '').toLowerCase()
    if (!nodeHay.includes(filters.nodeName.toLowerCase())) return false
  }
  if (filters.initiatorId && item.initiatorId && item.initiatorId !== filters.initiatorId) {
    return false
  }
  if (filters.createdFrom || filters.createdTo) {
    const t = item.createdAt ? new Date(item.createdAt).getTime() : 0
    if (filters.createdFrom && t < new Date(filters.createdFrom).getTime()) return false
    if (filters.createdTo && t > new Date(filters.createdTo).getTime()) return false
  }
  return true
}

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
  /** 发起人修订待办（撤回/驳回/退回后修改再提交） */
  taskKind?: 'approve' | 'revise'
  formInstanceId?: string | null
  formCode?: string | null
  processName?: string | null
  nodeName?: string | null
  initiatorId?: string | null
  initiatorName?: string | null
  businessNo?: string | null
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
export async function fetchUnifiedPending(
  filters?: ApprovalListFilters,
  processNameById?: Map<string, string>,
): Promise<UnifiedPendingResult> {
  const hasFilter = countActiveFilters(filters) > 0
  const pageSize = hasFilter ? PAGE_SIZE_FILTERED : PAGE_SIZE
  const wfParams = { pageNo: 1, pageSize, ...toWfFilterParams(filters) }

  const [legacy, wf] = await Promise.allSettled([
    approvalApi.myPending(),
    workflowApi.todo(wfParams),
  ])

  if (legacy.status === 'rejected' && wf.status === 'rejected') {
    throw legacy.reason
  }

  const out: UnifiedPendingItem[] = []
  let total = 0

  if (legacy.status === 'fulfilled') {
    const rows = legacy.value.data || []
    for (const it of rows) {
      const mapped: UnifiedPendingItem = {
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
        instanceId: it.flow_id || it.flow?.id,
        createdAt: it.created_at,
        initiatorId: it.flow?.submitted_by_id,
        initiatorName: it.flow?.submitted_by_name,
        nodeName: it.flow?.total_nodes ? `节点 ${it.node_order}` : undefined,
      }
      if (!matchesClientFilters(mapped, filters, processNameById)) continue
      out.push(mapped)
    }
    total += out.filter((i) => i.engine === 'legacy').length
  }

  if (wf.status === 'fulfilled') {
    total += wf.value.data?.total ?? 0
    for (const it of wf.value.data?.items || []) {
      if (it.status !== 'pending') continue
      out.push({
        key: `wf:${it.task_id}`,
        taskId: it.task_id,
        engine: 'wf',
        title: it.title || it.process_name || it.business_no || '审批',
        subtitle: [
          it.task_kind === 'revise'
            ? '待修改并重新提交'
            : (it.initiator_name ? `${it.initiator_name} 发起` : ''),
          it.task_kind === 'revise'
            ? (it.process_status === 'withdrawn' ? '已撤回' : it.process_status === 'rejected' ? '已驳回/退回' : '')
            : (it.node_name ? `待审：${it.node_name}` : ''),
          it.on_behalf_of && it.delegator_name ? `代 ${it.delegator_name}` : '',
        ].filter(Boolean).join(' · '),
        bizType: it.biz_type || it.process_name || null,
        bizId: it.biz_id,
        instanceId: it.process_instance_id,
        createdAt: it.created_at,
        taskKind: it.task_kind === 'revise' ? 'revise' : 'approve',
        formInstanceId: it.form_instance_id || null,
        formCode: it.form_code || null,
        processName: it.process_name || null,
        nodeName: it.node_name || null,
        initiatorId: it.initiator_id || null,
        initiatorName: it.initiator_name || null,
        businessNo: it.business_no || null,
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
    if (item.taskKind === 'revise') {
      throw new Error('修订待办请打开详情修改后重新提交')
    }
    await workflowApi.act(item.taskId, { action, opinion: comment })
  } else {
    await approvalApi.decide(item.taskId, {
      action: action === 'approve' ? 'approved' : 'rejected',
      comment,
    })
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(APPROVAL_PENDING_CHANGED))
  }
}

export interface UnifiedMineItem {
  key: string
  engine: ApprovalEngine
  instanceId: string
  title: string
  status: string
  bizType?: string | null
  bizId?: string | null
  formInstanceId?: string | null
  formCode?: string | null
  subtitle?: string
  createdAt?: string
  processName?: string | null
  nodeName?: string | null
  initiatorId?: string | null
  businessNo?: string | null
}

/** 我发起的：旧引擎按发起人过滤 + 新工作流 mine。 */
export async function fetchUnifiedMine(
  userId?: string,
  filters?: ApprovalListFilters,
  processNameById?: Map<string, string>,
): Promise<UnifiedMineItem[]> {
  const hasFilter = countActiveFilters(filters) > 0
  const pageSize = hasFilter ? PAGE_SIZE_FILTERED : PAGE_SIZE
  const wfParams = { pageNo: 1, pageSize, ...toWfFilterParams(filters) }

  const [legacy, wf] = await Promise.allSettled([
    approvalApi.list({
      pageNo: 1,
      pageSize,
      ...(userId ? { submitted_by_id: userId } : {}),
    }),
    workflowApi.mine(wfParams),
  ])
  const out: UnifiedMineItem[] = []

  if (legacy.status === 'fulfilled') {
    for (const f of legacy.value.data?.items || []) {
      const mapped: UnifiedMineItem = {
        key: `legacy:${f.id}`,
        engine: 'legacy',
        instanceId: f.id,
        title: f.title || f.biz_type || '审批',
        status: f.status,
        bizType: f.biz_type,
        bizId: f.biz_id,
        subtitle: f.total_nodes ? `节点 ${f.current_node}/${f.total_nodes}` : undefined,
        createdAt: f.created_at,
        nodeName: f.total_nodes ? `节点 ${f.current_node}` : undefined,
        initiatorId: f.submitted_by_id,
      }
      if (!matchesClientFilters(mapped, filters, processNameById)) continue
      out.push(mapped)
    }
  }

  if (wf.status === 'fulfilled') {
    for (const it of wf.value.data?.items || []) {
      out.push({
        key: `wf:${it.id}`,
        engine: 'wf',
        instanceId: it.id,
        title: it.title || it.business_no || it.process_name || '审批',
        status: it.status,
        bizType: it.biz_type || it.process_name || null,
        bizId: it.biz_id,
        formInstanceId: it.form_instance_id || null,
        formCode: it.form_code || null,
        subtitle: it.current_node_name ? `当前：${it.current_node_name}` : undefined,
        createdAt: it.created_at,
        processName: it.process_name || null,
        nodeName: it.current_node_name || null,
        businessNo: it.business_no || null,
      })
    }
  }

  out.sort((a, b) => (b.createdAt || '').localeCompare(a.createdAt || ''))
  return out
}

export interface UnifiedDoneItem {
  key: string
  engine: ApprovalEngine
  taskId?: string
  instanceId: string
  title: string
  status: string
  bizType?: string | null
  subtitle?: string
  actionAt?: string
  processName?: string | null
  nodeName?: string | null
  initiatorId?: string | null
  createdAt?: string
}

/** 我已办：新工作流 done + 旧引擎 my/done。 */
export async function fetchUnifiedDone(
  _userId?: string,
  filters?: ApprovalListFilters,
  processNameById?: Map<string, string>,
): Promise<UnifiedDoneItem[]> {
  const hasFilter = countActiveFilters(filters) > 0
  const pageSize = hasFilter ? PAGE_SIZE_FILTERED : PAGE_SIZE
  const wfParams = { pageNo: 1, pageSize, ...toWfFilterParams(filters) }

  const [wf, legacy] = await Promise.allSettled([
    workflowApi.done(wfParams),
    approvalApi.myDone({ pageSize }),
  ])
  const out: UnifiedDoneItem[] = []

  if (wf.status === 'fulfilled') {
    for (const it of wf.value.data?.items || []) {
      out.push({
        key: `wf:${it.task_id}`,
        engine: 'wf',
        taskId: it.task_id,
        instanceId: it.process_instance_id,
        title: it.title || it.process_name || it.business_no || '审批',
        status: it.status,
        bizType: it.biz_type || it.process_name || null,
        subtitle: [
          it.node_name ? `节点：${it.node_name}` : '',
          it.initiator_name ? `${it.initiator_name} 发起` : '',
        ].filter(Boolean).join(' · '),
        actionAt: it.action_at || it.created_at,
        processName: it.process_name || null,
        nodeName: it.node_name || null,
        initiatorId: it.initiator_id || null,
        createdAt: it.created_at,
      })
    }
  }

  if (legacy.status === 'fulfilled') {
    for (const it of legacy.value.data || []) {
      const f = it.flow
      const mapped: UnifiedDoneItem = {
        key: `legacy:${it.id}`,
        engine: 'legacy',
        taskId: it.id,
        instanceId: it.flow_id || f?.id || '',
        title: f?.title || f?.biz_type || '审批',
        status: it.status,
        bizType: f?.biz_type,
        subtitle: f?.total_nodes ? `节点 ${it.node_order}/${f.total_nodes}` : undefined,
        actionAt: it.decided_at || it.created_at,
        nodeName: f?.total_nodes ? `节点 ${it.node_order}` : undefined,
        initiatorId: f?.submitted_by_id,
        createdAt: it.created_at,
      }
      if (!matchesClientFilters(mapped, filters, processNameById)) continue
      out.push(mapped)
    }
  }

  out.sort((a, b) => (b.actionAt || '').localeCompare(a.actionAt || ''))
  return out
}

/** 抄送列表（新引擎），带筛选。 */
export async function fetchUnifiedCc(filters?: ApprovalListFilters) {
  const hasFilter = countActiveFilters(filters) > 0
  const pageSize = hasFilter ? PAGE_SIZE_FILTERED : PAGE_SIZE
  const r = await workflowApi.cc({ pageNo: 1, pageSize, ...toWfFilterParams(filters) })
  return r.data?.items || []
}

export async function fetchFilterOptions(processDefinitionId?: string): Promise<WfFilterOptions> {
  const r = await workflowApi.filterOptions(
    processDefinitionId ? { process_definition_id: processDefinitionId } : undefined,
  )
  return r.data || { processes: [], node_names: [], fields: [] }
}
