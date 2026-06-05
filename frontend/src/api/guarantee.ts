import client from './client'
import type { ApiResponse, PageData, Guarantee, GuaranteeSummary } from './types'

export const guaranteeApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Guarantee>>>('/api/v1/guarantees', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Guarantee>>(`/api/v1/guarantees/${id}`),
  create: (data: Partial<Guarantee>) =>
    client.post<unknown, ApiResponse<Guarantee>>('/api/v1/guarantees', data),
  update: (id: string, data: Partial<Guarantee>) =>
    client.put<unknown, ApiResponse<Guarantee>>(`/api/v1/guarantees/${id}`, data),
  remove: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/guarantees/${id}`),
  markReturned: (id: string, data: { return_date?: string; remark?: string }) =>
    client.post<unknown, ApiResponse<Guarantee>>(`/api/v1/guarantees/${id}/return`, data),
  summary: () =>
    client.get<unknown, ApiResponse<GuaranteeSummary>>('/api/v1/guarantees/summary'),
  notify: (days = 30) =>
    client.post<unknown, ApiResponse<{ notified: number }>>(`/api/v1/guarantees/notify?days=${days}`),
}
