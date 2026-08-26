import client from './client'
import type { ApiResponse, PageData, Lead, LeadReactivationRecord, LeadReactivationDetail } from './types'

export const leadApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Lead>>>('/api/v1/leads', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}`),
  create: (data: Partial<Lead> & { as_draft?: boolean }) =>
    client.post<unknown, ApiResponse<Lead>>('/api/v1/leads', data),
  update: (id: string, data: Partial<Lead>) =>
    client.put<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}`, data),
  qualify: (id: string, createOpportunity = true) =>
    client.post<unknown, ApiResponse<{ lead_id: string; project_id?: string; project_code?: string }>>(
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
  reactivationIntelReview: (id: string, data: {
    decision: 'include' | 'attack' | 'return' | 'revise' | 'draft'
    task_id: string
    customer_newness?: 'new' | 'old'
    return_reason?: string
    opinion?: string
    assess_remark?: string
    has_internal_conflict?: string
    conflict_note?: string
  }) =>
    client.post<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}/reactivation/intel_review`, data),
  submitReactivation: (id: string, data: {
    project_recent?: string
    follow_progress?: string
    site_visit?: string
    report_project_status: string
  }) =>
    client.post<unknown, ApiResponse<Lead>>(`/api/v1/leads/${id}/reactivation/submit`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/leads/${id}`),
  batchStatus: (ids: string[], status: string) =>
    client.post<unknown, ApiResponse<{ updated: number }>>('/api/v1/leads/batch_status', { ids, status }),
}

/** 180天项目激活（独立列表/详情，对齐简道云数据管理） */
export interface LeadReactivationStats {
  total: number
  active: number
  completed: number
  closed: number
  finished: number
}

export const leadReactivationApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<LeadReactivationRecord>>>('/api/v1/lead-reactivations', { params }),
  stats: () =>
    client.get<unknown, ApiResponse<LeadReactivationStats>>('/api/v1/lead-reactivations/stats'),
  get: (id: string) =>
    client.get<unknown, ApiResponse<LeadReactivationDetail>>(`/api/v1/lead-reactivations/${id}`),
}
