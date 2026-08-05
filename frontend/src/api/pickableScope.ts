import client from './client'
import type { ApiResponse } from './types'

export type PickableScopeKind = 'person' | 'department'

export interface PickableScopeItem {
  id: string
  code: string
  name: string
  kind: PickableScopeKind
  description?: string | null
  is_system?: boolean
  rules?: {
    role_codes?: string[]
    user_ids?: string[]
    dept_ids?: string[]
    include_children?: boolean
  }
  created_at?: string
  updated_at?: string
}

export const pickableScopeApi = {
  list: (params?: { kind?: string }) =>
    client.get<unknown, ApiResponse<PickableScopeItem[]>>('/api/admin/v1/tenant/pickable-scopes', { params }),
  create: (data: { code: string; name: string; kind: PickableScopeKind; description?: string; rules?: Record<string, unknown> }) =>
    client.post<unknown, ApiResponse<PickableScopeItem>>('/api/admin/v1/tenant/pickable-scopes', data),
  update: (id: string, data: { name?: string; description?: string; rules?: Record<string, unknown> }) =>
    client.put<unknown, ApiResponse<PickableScopeItem>>(`/api/admin/v1/tenant/pickable-scopes/${id}`, data),
  remove: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/admin/v1/tenant/pickable-scopes/${id}`),
  /** 设计器下拉（仅需登录） */
  listForPicker: (params?: { kind?: string }) =>
    client.get<unknown, ApiResponse<{ id: string; code: string; name: string; kind: string; description?: string }[]>>(
      '/api/v1/lc/pickable-scopes', { params },
    ),
}
