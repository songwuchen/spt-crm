import client from './client'

export const taskApi = {
  list: (params?: Record<string, unknown>) => client.get('/api/v1/tasks', { params }),
  create: (data: Record<string, unknown>) => client.post('/api/v1/tasks', data),
  update: (id: string, data: Record<string, unknown>) => client.put(`/api/v1/tasks/${id}`, data),
  delete: (id: string) => client.delete(`/api/v1/tasks/${id}`),
}
