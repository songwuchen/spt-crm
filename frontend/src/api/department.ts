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

// 部门 → 角色 自动分配规则
export interface DeptRoleRule {
  id: string
  department_id: string
  department_name?: string
  department_path?: string
  role_id: string
  role_code?: string
  role_name?: string
  include_children: boolean
  enabled: boolean
}

export const deptRoleRuleApi = {
  list: () =>
    client.get<unknown, ApiResponse<DeptRoleRule[]>>('/api/admin/v1/tenant/dept-role-rules'),
  create: (data: { department_id: string; role_id: string; include_children: boolean; enabled: boolean }) =>
    client.post<unknown, ApiResponse<{ id: string }>>('/api/admin/v1/tenant/dept-role-rules', data),
  update: (id: string, data: { include_children?: boolean; enabled?: boolean }) =>
    client.put<unknown, ApiResponse<DeptRoleRule>>(`/api/admin/v1/tenant/dept-role-rules/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/dept-role-rules/${id}`),
  applyAll: () =>
    client.post<unknown, ApiResponse<{ users_touched: number; roles_added: number }>>(
      '/api/admin/v1/tenant/dept-role-rules/apply-all', {},
    ),
}
