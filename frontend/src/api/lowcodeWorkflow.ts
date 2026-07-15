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
    client.get<unknown, ApiResponse<PageData<{ id: string; title?: string; business_no?: string; status: string; form_instance_id?: string; created_at?: string }>>>('/api/v1/lc/wf/instances/mine', { params }),
  instance: (id: string) =>
    client.get<unknown, ApiResponse<WfInstanceDetail>>(`/api/v1/lc/wf/instances/${id}`),
  act: (taskId: string, data: { action: string; opinion?: string; transfer_to?: string; to_node_id?: string }) =>
    client.post<unknown, ApiResponse<void>>(`/api/v1/lc/wf/tasks/${taskId}/act`, data),
  withdraw: (instanceId: string) =>
    client.post<unknown, ApiResponse<void>>(`/api/v1/lc/wf/instances/${instanceId}/withdraw`),

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
