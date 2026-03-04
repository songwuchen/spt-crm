import client from './client'

export const settingsApi = {
  // Stage policies
  listStages: () => client.get('/api/admin/v1/tenant/policies/stages'),
  updateStage: (code: string, data: Record<string, unknown>) =>
    client.put(`/api/admin/v1/tenant/policies/stages/${code}`, data),

  // Margin policies
  listMargins: () => client.get('/api/admin/v1/tenant/policies/margin'),
  createMargin: (data: Record<string, unknown>) =>
    client.post('/api/admin/v1/tenant/policies/margin', data),

  // AI policies
  listAiPolicies: () => client.get('/api/admin/v1/tenant/ai/policies'),

  // AI Budget
  getAiBudget: (period: string) =>
    client.get('/api/admin/v1/tenant/ai/budget', { params: { period } }),
  updateAiBudget: (data: Record<string, unknown>) =>
    client.put('/api/admin/v1/tenant/ai/budget', data),

  // Integrations
  listIntegrations: () => client.get('/api/admin/v1/tenant/integrations'),
  createIntegration: (data: Record<string, unknown>) =>
    client.post('/api/admin/v1/tenant/integrations', data),
  deleteIntegration: (id: string) =>
    client.delete(`/api/admin/v1/tenant/integrations/${id}`),

  // Feature toggles
  listFeatures: () => client.get('/api/admin/v1/tenant/features'),
  updateFeature: (code: string, data: { enabled: boolean }) =>
    client.put(`/api/admin/v1/tenant/features/${code}`, data),

  // Approval policies
  listApprovalPolicies: (bizType?: string) =>
    client.get('/api/admin/v1/tenant/approval-policies', { params: bizType ? { biz_type: bizType } : {} }),
  createApprovalPolicy: (data: Record<string, unknown>) =>
    client.post('/api/admin/v1/tenant/approval-policies', data),
  updateApprovalPolicy: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/admin/v1/tenant/approval-policies/${id}`, data),
  deleteApprovalPolicy: (id: string) =>
    client.delete(`/api/admin/v1/tenant/approval-policies/${id}`),
}
