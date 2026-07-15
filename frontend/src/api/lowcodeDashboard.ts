// 扩展平台 仪表盘 API。对接后端 /api/v1/lc/dashboards/*。
import client from './client'
import type { ApiResponse, PageData } from './types'
import type { Dashboard, DashDataSource, AggregateResult, CrmSource } from '@/types/lowcode'

export const dashboardApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Dashboard>>>('/api/v1/lc/dashboards', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Dashboard>>(`/api/v1/lc/dashboards/${id}`),
  create: (data: { name: string; description?: string }) =>
    client.post<unknown, ApiResponse<Dashboard>>('/api/v1/lc/dashboards', data),
  update: (id: string, data: Partial<Dashboard>) =>
    client.put<unknown, ApiResponse<Dashboard>>(`/api/v1/lc/dashboards/${id}`, data),
  remove: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/lc/dashboards/${id}`),
  aggregate: (data: DashDataSource) =>
    client.post<unknown, ApiResponse<AggregateResult>>('/api/v1/lc/dashboards/aggregate', data),
  crmSources: () =>
    client.get<unknown, ApiResponse<CrmSource[]>>('/api/v1/lc/dashboards/crm-sources'),
  aggregateCrm: (data: { entity: string; dimensions: unknown[]; metrics: unknown[]; filters?: unknown[] }) =>
    client.post<unknown, ApiResponse<AggregateResult>>('/api/v1/lc/dashboards/aggregate-crm', data),
}
