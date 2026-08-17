import client from './client'
import type { ApiResponse, PageData, Lead, LeadReactivationRecord } from './types'

export const leadApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Lead>>>('/api/v1/leads', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}`),
  create: (data: Partial<Lead> & { as_draft?: boolean }) =>
    client.post<unknown, ApiResponse<Lead>>('/api/v1/leads', data),
  update: (id: string, data: Partial<Lead>) =>
    client.put<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}`, data),
  qualify: (id: string, createOpportunity = false) =>
    client.post<unknown, ApiResponse<{ lead_id: string; customer_id: string; customer_name: string; project_id?: string; project_code?: string }>>(
      `/api/v1/leads/${id}/qualify`, { create_opportunity: createOpportunity }),
  discard: (id: string) =>
    client.post<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}/discard`),
  submitReview: (id: string) =>
    client.post<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}/submit_review`),
  intelReview: (id: string, data: {
    decision: 'include' | 'attack' | 'return' | 'revise' | 'draft'
    task_id: string
    customer_newness?: 'new' | 'old'
    return_reason?: string
    opinion?: string
    assess_remark?: string
  }) =>
    client.post<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}/intel_review`, data),
  listReactivationRecords: (id: string) =>
    client.get<unknown, ApiResponse<LeadReactivationRecord[]>>(
      `/api/v1/leads/${id}/reactivation/records`),
  submitReactivation: (id: string, data: {
    project_recent?: string
    follow_progress?: string
    site_visit?: string
    report_project_status: string
  }) =>
    client.post<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}/reactivation/submit`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/leads/${id}`),
  batchAssign: (ids: string[], owner_id: string, owner_name: string) =>
    client.post<unknown, ApiResponse<{ updated: number }>>('/api/v1/leads/batch_assign', { ids, owner_id, owner_name }),
  batchStatus: (ids: string[], status: string) =>
    client.post<unknown, ApiResponse<{ updated: number }>>('/api/v1/leads/batch_status', { ids, status }),
}
