import client from './client'

// Open platform management API (internal admin, JWT + role:manage).
export const openApiApi = {
  listScopes: () => client.get('/api/admin/v1/tenant/openapi/scopes'),
  listApps: () => client.get('/api/admin/v1/tenant/openapi/apps'),
  createApp: (data: Record<string, unknown>) =>
    client.post('/api/admin/v1/tenant/openapi/apps', data),
  updateApp: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/admin/v1/tenant/openapi/apps/${id}`, data),
  regenerateSecret: (id: string) =>
    client.post(`/api/admin/v1/tenant/openapi/apps/${id}/regenerate-secret`),
  deleteApp: (id: string) =>
    client.delete(`/api/admin/v1/tenant/openapi/apps/${id}`),
  listCallLogs: (params?: Record<string, unknown>) =>
    client.get('/api/admin/v1/tenant/openapi/call-logs', { params }),

  // Webhook subscriptions reuse the existing tenant webhook endpoints.
  listWebhooks: () => client.get('/api/admin/v1/tenant/webhooks'),
  createWebhook: (data: Record<string, unknown>) =>
    client.post('/api/admin/v1/tenant/webhooks', data),
  deleteWebhook: (id: string) =>
    client.delete(`/api/admin/v1/tenant/webhooks/${id}`),
  testWebhook: (id: string) =>
    client.post(`/api/admin/v1/tenant/openapi/webhooks/${id}/test`),

  // Event delivery (test push / failed redelivery)
  listEvents: (params?: Record<string, unknown>) =>
    client.get('/api/admin/v1/tenant/openapi/events', { params }),
  redeliverEvent: (id: string) =>
    client.post(`/api/admin/v1/tenant/openapi/events/${id}/redeliver`),
}
