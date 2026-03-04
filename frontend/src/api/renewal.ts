import client from './client'

export const renewalApi = {
  list: (params?: Record<string, unknown>) =>
    client.get('/api/v1/renewal_opportunities', { params }),
  get: (id: string) =>
    client.get(`/api/v1/renewal_opportunities/${id}`),
  create: (data: Record<string, unknown>) =>
    client.post('/api/v1/renewal_opportunities', data),
  update: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/v1/renewal_opportunities/${id}`, data),
}
