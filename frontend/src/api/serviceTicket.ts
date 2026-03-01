import client from './client'
import type { ApiResponse, PageData, ServiceTicketItem, RenewalItem } from './types'

export const serviceTicketApi = {
  list: (params?: { customer_id?: string; project_id?: string; keyword?: string; status?: string; pageNo?: number; pageSize?: number }) =>
    client.get<unknown, ApiResponse<PageData<ServiceTicketItem>>>('/api/v1/service_tickets', { params }),
  create: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<ServiceTicketItem>>('/api/v1/service_tickets', data),
  get: (id: string) =>
    client.get<unknown, ApiResponse<ServiceTicketItem>>(`/api/v1/service_tickets/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ServiceTicketItem>>(`/api/v1/service_tickets/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/v1/service_tickets/${id}`),

  // Renewal
  listRenewals: (params?: { customer_id?: string }) =>
    client.get<unknown, ApiResponse<RenewalItem[]>>('/api/v1/renewal_opportunities', { params }),
  createRenewal: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<RenewalItem>>('/api/v1/renewal_opportunities', data),
  getRenewal: (id: string) =>
    client.get<unknown, ApiResponse<RenewalItem>>(`/api/v1/renewal_opportunities/${id}`),
  updateRenewal: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<RenewalItem>>(`/api/v1/renewal_opportunities/${id}`, data),
}
