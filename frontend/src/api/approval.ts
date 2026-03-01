import client from './client'
import type { ApiResponse, ApprovalFlowItem, ApprovalPendingItem } from './types'

export const approvalApi = {
  list: (params?: { biz_type?: string; biz_id?: string; status?: string }) =>
    client.get<unknown, ApiResponse<ApprovalFlowItem[]>>('/api/v1/approvals', { params }),
  submit: (data: { biz_type: string; biz_id: string; title?: string; assignee_ids: string[]; assignee_names?: string[] }) =>
    client.post<unknown, ApiResponse<ApprovalFlowItem>>('/api/v1/approvals', data),
  get: (flowId: string) =>
    client.get<unknown, ApiResponse<ApprovalFlowItem>>(`/api/v1/approvals/${flowId}`),
  decide: (taskId: string, data: { action: string; comment?: string }) =>
    client.post<unknown, ApiResponse<ApprovalFlowItem>>(`/api/v1/approval_tasks/${taskId}/decide`, data),
  myPending: () =>
    client.get<unknown, ApiResponse<ApprovalPendingItem[]>>('/api/v1/approvals/my/pending'),
}
