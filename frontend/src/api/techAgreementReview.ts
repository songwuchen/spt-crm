import client from './client'
import type { ApiResponse, PageData } from './types'

export interface TechAgreementReview {
  id: string
  review_code: string
  status: string
  customer_id?: string | null
  company_name?: string | null
  applicant_id?: string | null
  applicant_name?: string | null
  apply_at?: string | null
  owner_id?: string | null
  owner_name?: string | null
  department_id?: string | null
  department_name?: string | null
  industry?: string | null
  address?: string | null
  elec_ctrl?: string | null
  project_title?: string | null
  has_weight_req?: string | null
  use_idle_equip?: string | null
  has_smart?: string | null
  need_pricing?: string | null
  sign_basis?: string | null
  ref_contract_no?: string | null
  pre_contact?: string | null
  remark?: string | null
  has_objection?: string | null
  form_json?: Record<string, unknown>
  created_by_name?: string | null
  created_at?: string
  updated_at?: string
}

export const techAgreementReviewApi = {
  list: (params?: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<TechAgreementReview>>>('/api/v1/tech-agreement-reviews', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<TechAgreementReview>>(`/api/v1/tech-agreement-reviews/${id}`),
  create: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<TechAgreementReview>>('/api/v1/tech-agreement-reviews', data),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<TechAgreementReview>>(`/api/v1/tech-agreement-reviews/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/tech-agreement-reviews/${id}`),
  submit: (id: string) =>
    client.post<unknown, ApiResponse<TechAgreementReview>>(`/api/v1/tech-agreement-reviews/${id}/submit`),
}
