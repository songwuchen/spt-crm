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
  get: (id: string) =>
    client.get<unknown, ApiResponse<UserItem>>(`/api/admin/v1/tenant/users/${id}`),
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
  resetPassword: (id: string, newPassword: string) =>
    client.post<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/users/${id}/reset_password`, { new_password: newPassword }),
  bulkRoles: (data: { user_ids: string[]; role_ids: string[]; mode: 'replace' | 'add' }) =>
    client.post<unknown, ApiResponse<{ updated: number }>>('/api/admin/v1/tenant/users/bulk_roles', data),
}

export const roleApi = {
  list: () =>
    client.get<unknown, ApiResponse<Role[]>>('/api/admin/v1/tenant/roles'),
  create: (data: { code: string; name: string; description?: string; data_scope?: string }) =>
    client.post<unknown, ApiResponse<Role>>('/api/admin/v1/tenant/roles', data),
  update: (roleId: string, data: { name?: string; description?: string; data_scope?: string }) =>
    client.put<unknown, ApiResponse<Role>>(`/api/admin/v1/tenant/roles/${roleId}`, data),
  grantPermissions: (roleId: string, permissionIds: string[]) =>
    client.post<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/roles/${roleId}/grant_permissions`, { permission_ids: permissionIds }),
  delete: (roleId: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/roles/${roleId}`),
}

export interface RbacSyncPreview {
  mode: 'additive' | 'reset'
  roles_to_create: { code: string; name: string; perm_count: number }[]
  perms_to_add: Record<string, { code: string; name: string }[]>
  perms_to_remove: Record<string, { code: string; name: string }[]>
  roles_to_update: { code: string; changes: string[] }[]
  permissions_to_create: string[]
  summary: { roles_to_create: number; perms_to_add: number; perms_to_remove: number; roles_to_update: number; permissions_to_create: number }
}

export interface RbacSyncReport {
  mode: 'additive' | 'reset'
  created_roles: string[]
  perms_added: number
  perms_removed: number
  roles_updated: string[]
  roles_touched: string[]
}

// 同步「标准角色与权限」到系统标准目录(仅本租户)。只动标准角色,不碰自定义角色。
export const rbacApi = {
  previewStandardSync: (mode: 'additive' | 'reset' = 'additive') =>
    client.get<unknown, ApiResponse<RbacSyncPreview>>('/api/admin/v1/rbac/standard-sync/preview', { params: { mode } }),
  applyStandardSync: (mode: 'additive' | 'reset' = 'additive') =>
    client.post<unknown, ApiResponse<RbacSyncReport>>('/api/admin/v1/rbac/standard-sync/apply', { mode }),
}

export const permissionApi = {
  list: () =>
    client.get<unknown, ApiResponse<PermissionItem[]>>('/api/admin/v1/tenant/permissions'),
}
