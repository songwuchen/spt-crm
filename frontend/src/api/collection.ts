import client from './client'
import type {
  ApiResponse, PageData, ArAgingReport, DebtTransfer, CollectionFollowUp,
} from './types'

export const collectionApi = {
  aging: (params?: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<ArAgingReport>>('/api/v1/collection/aging', { params }),
  agingNotify: () =>
    client.post<unknown, ApiResponse<{ notified: number }>>('/api/v1/collection/aging/notify'),
  // transfers
  listTransfers: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<DebtTransfer>>>('/api/v1/collection/transfers', { params }),
  createTransfer: (data: Partial<DebtTransfer>) =>
    client.post<unknown, ApiResponse<DebtTransfer>>('/api/v1/collection/transfers', data),
  updateTransfer: (id: string, data: Partial<DebtTransfer>) =>
    client.put<unknown, ApiResponse<DebtTransfer>>(`/api/v1/collection/transfers/${id}`, data),
  claim: (id: string, data: { commitment?: string }) =>
    client.post<unknown, ApiResponse<DebtTransfer>>(`/api/v1/collection/transfers/${id}/claim`, data),
  withdraw: (id: string) =>
    client.post<unknown, ApiResponse<DebtTransfer>>(`/api/v1/collection/transfers/${id}/withdraw`),
  deleteTransfer: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/collection/transfers/${id}`),
  // follow-ups
  listFollowups: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<CollectionFollowUp>>>('/api/v1/collection/followups', { params }),
  createFollowup: (data: Partial<CollectionFollowUp>) =>
    client.post<unknown, ApiResponse<CollectionFollowUp>>('/api/v1/collection/followups', data),
}
