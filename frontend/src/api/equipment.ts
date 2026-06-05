import client from './client'
import type { ApiResponse, PageData, CustomerEquipment, CustomerProcessSurvey } from './types'

export const equipmentApi = {
  // equipment ledger
  listEquipment: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<CustomerEquipment>>>('/api/v1/equipment/equipments', { params }),
  createEquipment: (data: Partial<CustomerEquipment>) =>
    client.post<unknown, ApiResponse<CustomerEquipment>>('/api/v1/equipment/equipments', data),
  updateEquipment: (id: string, data: Partial<CustomerEquipment>) =>
    client.put<unknown, ApiResponse<CustomerEquipment>>(`/api/v1/equipment/equipments/${id}`, data),
  deleteEquipment: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/equipment/equipments/${id}`),
  replacementCandidates: (months = 12) =>
    client.get<unknown, ApiResponse<CustomerEquipment[]>>(`/api/v1/equipment/replacement-candidates?months=${months}`),
  toRenewal: (id: string, data: { name?: string; amount_expect?: number; close_date_expect?: string }) =>
    client.post<unknown, ApiResponse<{ id: string; name: string }>>(`/api/v1/equipment/equipments/${id}/to-renewal`, data),
  // process surveys
  listSurveys: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<CustomerProcessSurvey>>>('/api/v1/equipment/surveys', { params }),
  createSurvey: (data: Partial<CustomerProcessSurvey>) =>
    client.post<unknown, ApiResponse<CustomerProcessSurvey>>('/api/v1/equipment/surveys', data),
  updateSurvey: (id: string, data: Partial<CustomerProcessSurvey>) =>
    client.put<unknown, ApiResponse<CustomerProcessSurvey>>(`/api/v1/equipment/surveys/${id}`, data),
  deleteSurvey: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/equipment/surveys/${id}`),
}
