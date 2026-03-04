import client from './client'
import type { ApiResponse, ApprovalFlowItem, ApprovalPendingItem } from './types'

export const approvalApi = {
  list: (params?: { biz_type?: string; biz_id?: string; status?: string }) =>
    client.get<unknown, ApiResponse<ApprovalFlowItem[]>>('/api/v1/approvals', { params }),
  submit: (data: { biz_type: string; biz_id: string; title?: string; assignee_ids: string[]; assignee_names?: string[]; approval_mode?: string }) =>
    client.post<unknown, ApiResponse<ApprovalFlowItem>>('/api/v1/approvals', data),
  get: (flowId: string) =>
    client.get<unknown, ApiResponse<ApprovalFlowItem>>(`/api/v1/approvals/${flowId}`),
  decide: (taskId: string, data: { action: string; comment?: string }) =>
    client.post<unknown, ApiResponse<ApprovalFlowItem>>(`/api/v1/approval_tasks/${taskId}/decide`, data),
  myPending: () =>
    client.get<unknown, ApiResponse<ApprovalPendingItem[]>>('/api/v1/approvals/my/pending'),
  withdraw: (flowId: string, data?: { reason?: string }) =>
    client.post<unknown, ApiResponse<ApprovalFlowItem>>(`/api/v1/approvals/${flowId}/withdraw`, data || {}),
  delegate: (taskId: string, data: { target_user_id: string; reason?: string }) =>
    client.post<unknown, ApiResponse<unknown>>(`/api/v1/approval_tasks/${taskId}/delegate`, data),
  resubmit: (flowId: string, data: { biz_type?: string; biz_id?: string; title?: string; assignee_ids?: string[]; assignee_names?: string[] }) =>
    client.post<unknown, ApiResponse<ApprovalFlowItem>>(`/api/v1/approvals/${flowId}/resubmit`, data),
  bulkDecide: (data: { task_ids: string[]; action: string; comment?: string }) =>
    client.post<unknown, ApiResponse<Array<{ task_id: string; success: boolean; error?: string }>>>('/api/v1/approval_tasks/bulk_decide', data),
  statistics: (params?: { date_from?: string; date_to?: string }) =>
    client.get<unknown, ApiResponse<Record<string, unknown>>>('/api/v1/approvals/statistics', { params }),
}
