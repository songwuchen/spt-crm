import client from './client'
import type { ApiResponse, PageData, Lead } from './types'

export const leadApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Lead>>>('/api/v1/leads', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}`),
  create: (data: Partial<Lead>) =>
    client.post<unknown, ApiResponse<Lead>>('/api/v1/leads', data),
  update: (id: string, data: Partial<Lead>) =>
    client.put<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}`, data),
  qualify: (id: string) =>
    client.post<unknown, ApiResponse<{ lead_id: string; customer_id: string; customer_name: string }>>(`/api/v1/leads/${id}/qualify`),
  discard: (id: string) =>
    client.post<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}/discard`),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/leads/${id}`),
  batchAssign: (ids: string[], owner_id: string, owner_name: string) =>
    client.post<unknown, ApiResponse<{ updated: number }>>('/api/v1/leads/batch_assign', { ids, owner_id, owner_name }),
  batchStatus: (ids: string[], status: string) =>
    client.post<unknown, ApiResponse<{ updated: number }>>('/api/v1/leads/batch_status', { ids, status }),
}
