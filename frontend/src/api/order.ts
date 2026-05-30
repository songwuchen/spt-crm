import client from './client'
import type { ApiResponse, PageData, Order } from './types'

export const orderApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<Order>>>('/api/v1/orders', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<Order>>(`/api/v1/orders/${id}`),
  create: (data: Partial<Order>) =>
    client.post<unknown, ApiResponse<Order>>('/api/v1/orders', data),
  update: (id: string, data: Partial<Order>) =>
    client.put<unknown, ApiResponse<Order>>(`/api/v1/orders/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/orders/${id}`),
}
