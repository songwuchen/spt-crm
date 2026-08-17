// 扩展平台 审批流程 API。对接后端 /api/v1/lc/wf/*。
import client from './client'
import type { ApiResponse, PageData } from './types'
import type { WfDefinition, WfDesign, WfTodoItem, WfInstanceDetail } from '@/types/lowcode'

export const workflowApi = {
  // ---- 定义 ----
  listDefs: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<WfDefinition>>>('/api/v1/lc/wf/definitions', { params }),
  getDef: (id: string) =>
    client.get<unknown, ApiResponse<WfDefinition>>(`/api/v1/lc/wf/definitions/${id}`),
  createDef: (data: Partial<WfDefinition>) =>
    client.post<unknown, ApiResponse<WfDefinition>>('/api/v1/lc/wf/definitions', data),
  updateDef: (id: string, data: Partial<WfDefinition>) =>
    client.put<unknown, ApiResponse<WfDefinition>>(`/api/v1/lc/wf/definitions/${id}`, data),
  deleteDef: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/lc/wf/definitions/${id}`),
  loadDesign: (id: string) =>
    client.get<unknown, ApiResponse<WfDesign>>(`/api/v1/lc/wf/definitions/${id}/design`),
  saveDesign: (id: string, data: WfDesign) =>
    client.post<unknown, ApiResponse<WfDesign>>(`/api/v1/lc/wf/definitions/${id}/design`, data),
  publish: (id: string) =>
    client.post<unknown, ApiResponse<WfDesign>>(`/api/v1/lc/wf/definitions/${id}/publish`),

  // ---- 运行时 ----
  todo: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<WfTodoItem>>>('/api/v1/lc/wf/tasks/todo', { params }),
  done: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<WfTodoItem>>>('/api/v1/lc/wf/tasks/done', { params }),
  mine: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<{
      id: string
      title?: string
      business_no?: string
      status: string
      form_instance_id?: string
      biz_type?: string
      biz_id?: string
      biz_ref_id?: string
      process_name?: string | null
      current_node_name?: string
      created_at?: string
      started_at?: string
      completed_at?: string
    }>>>('/api/v1/lc/wf/instances/mine', { params }),
  cc: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<{
      cc_id: string
      is_read: boolean
      process_instance_id: string
      title?: string
      business_no?: string
      status?: string
      biz_type?: string
      biz_id?: string
      biz_ref_id?: string
      process_name?: string | null
      initiator_name?: string
      created_at?: string
    }>>>('/api/v1/lc/wf/instances/cc', { params }),
  /** 业务详情页：按 biz 查最新流程实例（含审批记录）；无流程时 data 为 null */
  byBiz: (params: { biz_type: string; biz_id: string }) =>
    client.get<unknown, ApiResponse<WfInstanceDetail | null>>('/api/v1/lc/wf/instances/by-biz', { params }),
  /** 表单详情：按 form_instance_id 查最新流程（兼容未回写 process_instance_id 的旧数据） */
  byFormInstance: (params: { form_instance_id: string }) =>
    client.get<unknown, ApiResponse<WfInstanceDetail | null>>('/api/v1/lc/wf/instances/by-form-instance', { params }),
  instance: (id: string, params?: { task_id?: string }) =>
    client.get<unknown, ApiResponse<WfInstanceDetail>>(`/api/v1/lc/wf/instances/${id}`, { params }),
  comment: (instanceId: string, content: string) =>
    client.post<unknown, ApiResponse<void>>(`/api/v1/lc/wf/instances/${instanceId}/comments`, { content }),
  act: (taskId: string, data: {
    action: string
    opinion?: string
    transfer_to?: string
    to_node_id?: string
    field_updates?: Record<string, unknown>
  }) =>
    client.post<unknown, ApiResponse<void>>(`/api/v1/lc/wf/tasks/${taskId}/act`, data),
  withdraw: (instanceId: string) =>
    client.post<unknown, ApiResponse<void>>(`/api/v1/lc/wf/instances/${instanceId}/withdraw`),
  resubmit: (instanceId: string) =>
    client.post<unknown, ApiResponse<{ id: string; status: string; title?: string }>>(
      `/api/v1/lc/wf/instances/${instanceId}/resubmit`,
    ),
  urge: (instanceId: string) =>
    client.post<unknown, ApiResponse<{ notified: number }>>(`/api/v1/lc/wf/instances/${instanceId}/urge`),
  activateNodes: (instanceId: string) =>
    client.get<unknown, ApiResponse<{ id: string; name: string; type?: string }[]>>(
      `/api/v1/lc/wf/instances/${instanceId}/activate-nodes`,
    ),
  activate: (instanceId: string, data: { to_node_id: string }) =>
    client.post<unknown, ApiResponse<{ id: string; status: string; title?: string }>>(
      `/api/v1/lc/wf/instances/${instanceId}/activate`,
      data,
    ),

  // 业务类型审批流的业务字段目录(业务流无表单时用于条件分支/字段选择)
  bizFields: (bizType: string) =>
    client.get<unknown, ApiResponse<{ id: string; label: string; type: string }[]>>(`/api/v1/lc/wf/biz-fields/${bizType}`),

  // 代理审批（委托）
  listAgents: () =>
    client.get<unknown, ApiResponse<WfAgent[]>>('/api/v1/lc/wf/agents'),
  createAgent: (data: { agent_id: string; start_time: string; end_time: string; note?: string }) =>
    client.post<unknown, ApiResponse<{ id: string }>>('/api/v1/lc/wf/agents', data),
  deleteAgent: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/lc/wf/agents/${id}`),
}

export interface WfAgent {
  id: string
  agent_id: string
  agent_name?: string
  start_time?: string
  end_time?: string
  status: string
  note?: string
  active_now: boolean
}
