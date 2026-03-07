import client from './client'
import type { ApiResponse, ErpOrderLink, DeliveryMilestone } from './types'

export const deliveryApi = {
  // Global milestone list
  listAllMilestones: (params: Record<string, unknown>) =>
    client.get('/api/v1/milestones', { params }),

  // ERP Order Links
  listOrderLinks: (projectId: string) =>
    client.get<unknown, ApiResponse<ErpOrderLink[]>>(`/api/v1/projects/${projectId}/order_links`),
  createOrderLink: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<ErpOrderLink>>(`/api/v1/projects/${projectId}/order_links`, data),
  deleteOrderLink: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/order_links/${id}`),

  // Milestones
  listMilestones: (projectId: string) =>
    client.get<unknown, ApiResponse<DeliveryMilestone[]>>(`/api/v1/projects/${projectId}/milestones`),
  createMilestone: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<DeliveryMilestone>>(`/api/v1/projects/${projectId}/milestones`, data),
  updateMilestone: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<DeliveryMilestone>>(`/api/v1/milestones/${id}`, data),
  deleteMilestone: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/milestones/${id}`),
}
