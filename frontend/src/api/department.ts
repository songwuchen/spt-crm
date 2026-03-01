import client from './client'
import type { ApiResponse, Department } from './types'

export const departmentApi = {
  tree: () =>
    client.get<unknown, ApiResponse<Department[]>>('/api/admin/v1/tenant/departments/tree'),
  create: (data: { name: string; parent_id?: string; sort_order?: number }) =>
    client.post<unknown, ApiResponse<Department>>('/api/admin/v1/tenant/departments', data),
  update: (id: string, data: Partial<Department>) =>
    client.put<unknown, ApiResponse<Department>>(`/api/admin/v1/tenant/departments/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/departments/${id}`),
}
