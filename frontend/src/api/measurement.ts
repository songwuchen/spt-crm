import client from './client'
import type { ApiResponse, PageData, ServiceMeasurement, MeasurementModelStat } from './types'

export const measurementApi = {
  list: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<ServiceMeasurement>>>('/api/v1/measurements', { params }),
  get: (id: string) =>
    client.get<unknown, ApiResponse<ServiceMeasurement>>(`/api/v1/measurements/${id}`),
  create: (data: Partial<ServiceMeasurement>) =>
    client.post<unknown, ApiResponse<ServiceMeasurement>>('/api/v1/measurements', data),
  update: (id: string, data: Partial<ServiceMeasurement>) =>
    client.put<unknown, ApiResponse<ServiceMeasurement>>(`/api/v1/measurements/${id}`, data),
  remove: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/measurements/${id}`),
  stats: () =>
    client.get<unknown, ApiResponse<MeasurementModelStat[]>>('/api/v1/measurements/stats'),
}
