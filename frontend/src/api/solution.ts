import client from './client'
import type { ApiResponse, SolutionItem, SolutionVersion } from './types'

export const solutionApi = {
  list: (params?: Record<string, unknown>) =>
    client.get('/api/v1/solutions', { params }),
  listByProject: (projectId: string) =>
    client.get<unknown, ApiResponse<SolutionItem[]>>(`/api/v1/projects/${projectId}/solutions`),
  create: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<{ solution: SolutionItem; version: SolutionVersion }>>(`/api/v1/projects/${projectId}/solutions`, data),
  get: (id: string) =>
    client.get<unknown, ApiResponse<SolutionItem>>(`/api/v1/solutions/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<SolutionItem>>(`/api/v1/solutions/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/solutions/${id}`),
  newVersion: (id: string) =>
    client.post<unknown, ApiResponse<SolutionVersion>>(`/api/v1/solutions/${id}/new_version`),

  // Version
  getVersion: (vid: string) =>
    client.get<unknown, ApiResponse<SolutionVersion>>(`/api/v1/solution_versions/${vid}`),
  updateVersion: (vid: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<SolutionVersion>>(`/api/v1/solution_versions/${vid}`, data),

  // Compare
  compare: (solutionId: string, v1: number, v2: number) =>
    client.get(`/api/v1/solutions/${solutionId}/compare`, { params: { v1, v2 } }),
}
