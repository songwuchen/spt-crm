import client from './client'
import type { ApiResponse } from './types'

export interface PlatformTenant {
  id: string
  code: string
  name: string
  is_active: boolean
  plan?: string
  contact_name?: string
  contact_email?: string
  created_at: string
}

export interface TenantPlan {
  id: string
  name: string
  pricing_json?: Record<string, unknown>
  limits_json?: Record<string, unknown>
  features_json?: Record<string, unknown>
  status: string
  created_at: string
}

export interface AiBudget {
  id: string
  period: string
  budget_cost?: number
  used_cost?: number
  budget_tokens?: number
  used_tokens?: number
  hard_limit: boolean
}

export interface PlatformOverview {
  total_tenants: number
  active_tenants: number
  total_users: number
  current_period: string
  usage_summary: Record<string, number>
  tenant_usage: Record<string, Record<string, number>>
}

export interface UsageMeter {
  id: string
  tenant_id: string
  metric_code: string
  period: string
  value: number
}

export const platformApi = {
  // Tenants
  listTenants: () =>
    client.get<unknown, ApiResponse<PlatformTenant[]>>('/api/admin/v1/platform/tenants'),
  updateTenant: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<PlatformTenant>>(`/api/admin/v1/platform/tenants/${id}`, data),

  // Plans
  listPlans: () =>
    client.get<unknown, ApiResponse<TenantPlan[]>>('/api/admin/v1/platform/plans'),
  createPlan: (data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<TenantPlan>>('/api/admin/v1/platform/plans', data),
  updatePlan: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<TenantPlan>>(`/api/admin/v1/platform/plans/${id}`, data),

  // Platform Overview & Usage
  getOverview: () =>
    client.get<unknown, ApiResponse<PlatformOverview>>('/api/admin/v1/platform/overview'),
  listUsage: (params?: { tenant_id?: string; period?: string }) =>
    client.get<unknown, ApiResponse<UsageMeter[]>>('/api/admin/v1/platform/usage', { params }),

  // AI Budget
  getAiBudget: (period: string) =>
    client.get<unknown, ApiResponse<AiBudget | null>>('/api/admin/v1/tenant/ai/budget', { params: { period } }),
  updateAiBudget: (data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<AiBudget>>('/api/admin/v1/tenant/ai/budget', data),
}
