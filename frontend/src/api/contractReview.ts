import client from './client'
import type { ApiResponse, PageData } from './types'

export interface ContractReview {
  id: string
  review_code: string
  review_type?: string | null
  status: string
  customer_id?: string | null
  company_name?: string | null
  owner_id?: string | null
  owner_name?: string | null
  department_id?: string | null
  department_name?: string | null
  region_manager_id?: string | null
  region_manager_name?: string | null
  is_export?: string | null
  need_pricing?: string | null
  need_install?: string | null
  customer_type?: string | null
  elec_ctrl?: string | null
  project_title?: string | null
  reported_at?: string | null
  contract_amount?: number | null
  delivery_period?: string | null
  conclusion?: string | null
  payment_term?: string | null
  review_json?: Record<string, unknown>
  custom_fields_json?: Record<string, unknown>
  created_by_name?: string | null
  created_at?: string
  updated_at?: string
}

export const contractReviewApi = {
  list: (params?: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<ContractReview>>>('/api/v1/contract-reviews', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<ContractReview>>(`/api/v1/contract-reviews/${id}`),
  create: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<ContractReview>>('/api/v1/contract-reviews', data),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ContractReview>>(`/api/v1/contract-reviews/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/contract-reviews/${id}`),
  submit: (id: string) =>
    client.post<unknown, ApiResponse<ContractReview>>(`/api/v1/contract-reviews/${id}/submit`),
}
