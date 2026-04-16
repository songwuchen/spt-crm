import client from './client'
import type { ApiResponse, PageData, Role, PermissionItem } from './types'

interface UserItem {
  id: string
  username: string
  real_name: string
  phone?: string
  email?: string
  is_active: boolean
  roles: string[]
  departments: string[]
}

export const userApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<UserItem>>>('/api/admin/v1/tenant/users', { params }),
  create: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<UserItem>>('/api/admin/v1/tenant/users', data),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<UserItem>>(`/api/admin/v1/tenant/users/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/users/${id}`),
  importCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return client.post<unknown, ApiResponse<{ success: number; failed: { row: number; reason: string }[]; total: number }>>(
      '/api/admin/v1/tenant/users/import',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },
  exportCsv: (keyword?: string) =>
    client.get('/api/admin/v1/tenant/users/export', {
      params: keyword ? { keyword } : {},
      responseType: 'blob',
    }),
}

export const roleApi = {
  list: () =>
    client.get<unknown, ApiResponse<Role[]>>('/api/admin/v1/tenant/roles'),
  create: (data: { code: string; name: string; description?: string }) =>
    client.post<unknown, ApiResponse<Role>>('/api/admin/v1/tenant/roles', data),
  grantPermissions: (roleId: string, permissionIds: string[]) =>
    client.post<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/roles/${roleId}/grant_permissions`, { permission_ids: permissionIds }),
  delete: (roleId: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/roles/${roleId}`),
}

export const permissionApi = {
  list: () =>
    client.get<unknown, ApiResponse<PermissionItem[]>>('/api/admin/v1/tenant/permissions'),
}
