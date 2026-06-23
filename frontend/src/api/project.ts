import client from './client'
import type { ApiResponse, PageData, OpportunityProject, ProjectStageHistory, ProjectHealthScore, AclShareItem, ProjectMember } from './types'

export const projectApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<OpportunityProject>>>('/api/v1/projects', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<OpportunityProject>>(`/api/v1/projects/${id}`),
  create: (data: Partial<OpportunityProject>) =>
    client.post<unknown, ApiResponse<OpportunityProject>>('/api/v1/projects', data),
  update: (id: string, data: Partial<OpportunityProject>) =>
    client.put<unknown, ApiResponse<OpportunityProject>>(`/api/v1/projects/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/projects/${id}`),
  transfer: (id: string, data: { owner_id: string; note?: string }) =>
    client.post<unknown, ApiResponse<OpportunityProject>>(`/api/v1/projects/${id}/transfer`, data),
  advance: (id: string, data: { to_stage: string; note?: string }) =>
    client.post<unknown, ApiResponse<OpportunityProject>>(`/api/v1/projects/${id}/advance`, data),
  rollback: (id: string, data: { to_stage: string; note?: string }) =>
    client.post<unknown, ApiResponse<OpportunityProject>>(`/api/v1/projects/${id}/rollback`, data),
  stageHistory: (id: string) =>
    client.get<unknown, ApiResponse<ProjectStageHistory[]>>(`/api/v1/projects/${id}/stage_history`),
  health: (id: string) =>
    client.get<unknown, ApiResponse<ProjectHealthScore>>(`/api/v1/projects/${id}/health`),
  // Shares
  listShares: (id: string) =>
    client.get<unknown, ApiResponse<AclShareItem[]>>(`/api/v1/projects/${id}/shares`),
  createShare: (id: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<{ id: string }>>(`/api/v1/projects/${id}/shares`, data),
  deleteShare: (id: string, shareId: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/projects/${id}/shares/${shareId}`),
  // Members (多部门 / 多人协作)
  listMembers: (id: string) =>
    client.get<unknown, ApiResponse<ProjectMember[]>>(`/api/v1/projects/${id}/members`),
  addMember: (id: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<ProjectMember>>(`/api/v1/projects/${id}/members`, data),
  updateMember: (id: string, memberId: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ProjectMember>>(`/api/v1/projects/${id}/members/${memberId}`, data),
  removeMember: (id: string, memberId: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/projects/${id}/members/${memberId}`),
}
