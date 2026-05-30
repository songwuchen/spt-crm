import client from './client'
import type { ApiResponse, PageData, Tender } from './types'

export const tenderApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Tender>>>('/api/v1/tenders', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Tender>>(`/api/v1/tenders/${id}`),
  create: (data: Partial<Tender>) =>
    client.post<unknown, ApiResponse<Tender>>('/api/v1/tenders', data),
  update: (id: string, data: Partial<Tender>) =>
    client.put<unknown, ApiResponse<Tender>>(`/api/v1/tenders/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/tenders/${id}`),
}
