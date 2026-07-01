import client from './client'
import type { ApiResponse, PageData, ServiceTicketItem, RenewalItem } from './types'

export const serviceTicketApi = {
  list: (params?: { customer_id?: string; project_id?: string; keyword?: string; status?: string; priority?: string; type?: string; pageNo?: number; pageSize?: number }) =>
    client.get<unknown, ApiResponse<PageData<ServiceTicketItem>>>('/api/v1/service_tickets', { params }),
  create: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<ServiceTicketItem>>('/api/v1/service_tickets', data),
  get: (id: string) =>
    client.get<unknown, ApiResponse<ServiceTicketItem>>(`/api/v1/service_tickets/${id}`),
  // 关联订单下拉（售后专用，无需 order:view 权限）
  orderOptions: (params?: { customer_id?: string; keyword?: string }) =>
    client.get<unknown, ApiResponse<{ items: { id: string; order_no: string; title?: string }[] }>>(
      '/api/v1/service_tickets/order_options', { params }),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ServiceTicketItem>>(`/api/v1/service_tickets/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/v1/service_tickets/${id}`),
  submit: (id: string) =>
    client.post<unknown, ApiResponse<ServiceTicketItem>>(`/api/v1/service_tickets/${id}/submit`),

  // Renewal
  listRenewals: (params?: { customer_id?: string }) =>
    client.get<unknown, ApiResponse<RenewalItem[]>>('/api/v1/renewal_opportunities', { params }),
  createRenewal: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<RenewalItem>>('/api/v1/renewal_opportunities', data),
  getRenewal: (id: string) =>
    client.get<unknown, ApiResponse<RenewalItem>>(`/api/v1/renewal_opportunities/${id}`),
  updateRenewal: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<RenewalItem>>(`/api/v1/renewal_opportunities/${id}`, data),

  // Satisfaction
  rate: (id: string, data: { score: number; comment?: string }) =>
    client.post<unknown, ApiResponse<ServiceTicketItem>>(`/api/v1/service_tickets/${id}/rate`, data),

  // SLA
  slaStats: () => client.get('/api/v1/service_tickets/sla/stats'),

  // Knowledge base
  knowledgeSearch: (keyword: string, type?: string) =>
    client.get<unknown, ApiResponse<{ id: string; ticket_no: string; type: string; priority: string; description: string; resolution: string; updated_at: string }[]>>(
      '/api/v1/service_tickets/knowledge', { params: { keyword, type: type || undefined } }
    ),
}
