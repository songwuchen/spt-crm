import client from './client'
import type { ApiResponse, ActivityItem } from './types'

export const activityApi = {
  list: (bizType: string, bizId: string) =>
    client.get<unknown, ApiResponse<ActivityItem[]>>('/api/v1/activities', { params: { biz_type: bizType, biz_id: bizId } }),
  listAll: (params: Record<string, unknown>) =>
    client.get('/api/v1/activities/all', { params }),
  create: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<ActivityItem>>('/api/v1/activities', data),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ActivityItem>>(`/api/v1/activities/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/activities/${id}`),
  togglePin: (id: string) =>
    client.post<unknown, ApiResponse<ActivityItem>>(`/api/v1/activities/${id}/pin`),
}
