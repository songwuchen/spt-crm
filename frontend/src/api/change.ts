import client from './client'
import type { ApiResponse, ChangeRequestItem } from './types'

export const changeApi = {
  listByProject: (projectId: string) =>
    client.get<unknown, ApiResponse<ChangeRequestItem[]>>(`/api/v1/projects/${projectId}/change_requests`),
  create: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<ChangeRequestItem>>(`/api/v1/projects/${projectId}/change_requests`, data),
  get: (id: string) =>
    client.get<unknown, ApiResponse<ChangeRequestItem>>(`/api/v1/change_requests/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ChangeRequestItem>>(`/api/v1/change_requests/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/change_requests/${id}`),
}
