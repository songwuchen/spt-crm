import client from './client'
import type { ApiResponse, PageData, Customer } from './types'

export const customerApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Customer>>>('/api/v1/customers', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Customer>>(`/api/v1/customers/${id}`),
  create: (data: Partial<Customer>) =>
    client.post<unknown, ApiResponse<Customer>>('/api/v1/customers', data),
  update: (id: string, data: Partial<Customer>) =>
    client.put<unknown, ApiResponse<Customer>>(`/api/v1/customers/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/customers/${id}`),

  // Stats
  stats: (id: string) =>
    client.get<unknown, ApiResponse<Record<string, number>>>(`/api/v1/customers/${id}/stats`),

  // Relations
  listRelations: (id: string) =>
    client.get<unknown, ApiResponse<any[]>>(`/api/v1/customers/${id}/relations`),
  createRelation: (id: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<any>>(`/api/v1/customers/${id}/relations`, data),
  deleteRelation: (id: string, relId: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/customers/${id}/relations/${relId}`),

  // Shares
  listShares: (id: string) =>
    client.get<unknown, ApiResponse<any[]>>(`/api/v1/customers/${id}/shares`),
  createShare: (id: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<any>>(`/api/v1/customers/${id}/shares`, data),
  deleteShare: (id: string, shareId: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/customers/${id}/shares/${shareId}`),
}
