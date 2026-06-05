import client from './client'
import type {
  ApiResponse, PageData, Commission, CommissionPayout, CommissionRule, CommissionSummary,
} from './types'

export const commissionApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Commission>>>('/api/v1/commissions', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Commission>>(`/api/v1/commissions/${id}`),
  create: (data: Partial<Commission>) =>
    client.post<unknown, ApiResponse<Commission>>('/api/v1/commissions', data),
  update: (id: string, data: Partial<Commission>) =>
    client.put<unknown, ApiResponse<Commission>>(`/api/v1/commissions/${id}`, data),
  remove: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/commissions/${id}`),
  recalc: (id: string) =>
    client.post<unknown, ApiResponse<Commission>>(`/api/v1/commissions/${id}/recalc`),
  generateFromContract: (contractId: string) =>
    client.post<unknown, ApiResponse<Commission>>(`/api/v1/commissions/generate/from-contract/${contractId}`),
  summary: () =>
    client.get<unknown, ApiResponse<CommissionSummary[]>>('/api/v1/commissions/summary'),
  listPayouts: (id: string) =>
    client.get<unknown, ApiResponse<CommissionPayout[]>>(`/api/v1/commissions/${id}/payouts`),
  addPayout: (id: string, data: Partial<CommissionPayout>) =>
    client.post<unknown, ApiResponse<CommissionPayout>>(`/api/v1/commissions/${id}/payouts`, data),
  // rules
  listRules: () =>
    client.get<unknown, ApiResponse<CommissionRule[]>>('/api/v1/commissions/rules'),
  createRule: (data: Partial<CommissionRule>) =>
    client.post<unknown, ApiResponse<CommissionRule>>('/api/v1/commissions/rules', data),
  updateRule: (id: string, data: Partial<CommissionRule>) =>
    client.put<unknown, ApiResponse<CommissionRule>>(`/api/v1/commissions/rules/${id}`, data),
  deleteRule: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/commissions/rules/${id}`),
}
