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
  updateIntegration: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/admin/v1/tenant/integrations/${id}`, data),
  deleteIntegration: (id: string) =>
    client.delete(`/api/admin/v1/tenant/integrations/${id}`),
  testIntegration: (id: string) =>
    client.post(`/api/admin/v1/tenant/integrations/${id}/test`),

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

  // Doc templates
  listDocTemplates: (docType?: string) =>
    client.get('/api/v1/doc-templates', { params: docType ? { doc_type: docType } : {} }),
  getDocTemplate: (id: string) => client.get(`/api/v1/doc-templates/${id}`),
  createDocTemplate: (data: Record<string, unknown>) =>
    client.post('/api/v1/doc-templates', data),
  updateDocTemplate: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/v1/doc-templates/${id}`, data),
  deleteDocTemplate: (id: string) =>
    client.delete(`/api/v1/doc-templates/${id}`),

  // Email templates
  listEmailTemplates: () => client.get('/api/v1/admin/email-templates'),
  createEmailTemplate: (data: Record<string, unknown>) =>
    client.post('/api/v1/admin/email-templates', data),
  updateEmailTemplate: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/v1/admin/email-templates/${id}`, data),
  deleteEmailTemplate: (id: string) =>
    client.delete(`/api/v1/admin/email-templates/${id}`),

  // Backup
  backupStats: () => client.get('/api/v1/admin/backup/stats'),
  backupDownloadUrl: () => '/api/v1/admin/backup',
  restoreBackup: (data: Record<string, unknown>) => client.post('/api/v1/admin/backup/restore', data),

  // Data dictionary
  listDataDict: (dictType?: string) =>
    client.get('/api/v1/data-dict', { params: dictType ? { dict_type: dictType } : {} }),
  createDataDict: (data: Record<string, unknown>) =>
    client.post('/api/v1/data-dict', data),
  updateDataDict: (id: string, data: Record<string, unknown>) =>
    client.put(`/api/v1/data-dict/${id}`, data),
  deleteDataDict: (id: string) =>
    client.delete(`/api/v1/data-dict/${id}`),

  // Recycle bin
  listRecycleBin: (params?: Record<string, unknown>) =>
    client.get('/api/v1/recycle-bin', { params }),
  restoreRecord: (bizType: string, id: string) =>
    client.post(`/api/v1/recycle-bin/${bizType}/${id}/restore`),
  permanentDelete: (bizType: string, id: string) =>
    client.delete(`/api/v1/recycle-bin/${bizType}/${id}`),

  // Audit
  auditVerify: () => client.post('/api/v1/audit_logs/verify'),

  // Pool rules
  getPoolRules: () => client.get('/api/admin/v1/tenant/pool_rules'),
  updatePoolRules: (data: Record<string, unknown>) =>
    client.put('/api/admin/v1/tenant/pool_rules', data),

  // Field rules
  getFieldRules: () => client.get('/api/admin/v1/tenant/field_rules'),
  updateFieldRules: (data: Array<Record<string, unknown>>) =>
    client.put('/api/admin/v1/tenant/field_rules', data),

  // Report schedules
  getReportSchedules: () => client.get('/api/admin/v1/tenant/report_schedules'),
  updateReportSchedules: (data: Array<Record<string, unknown>>) =>
    client.put('/api/admin/v1/tenant/report_schedules', data),

  // UI settings (界面设置：系统显示名 / 菜单别名 / 菜单隐藏)
  getUiSettings: () => client.get('/api/admin/v1/tenant/ui-settings'),
  updateUiSettings: (data: Record<string, unknown>) =>
    client.put('/api/admin/v1/tenant/ui-settings', data),

  // File storage
  getFileStorage: () => client.get('/api/admin/v1/tenant/file-storage'),
  updateFileStorage: (data: Record<string, unknown>) =>
    client.put('/api/admin/v1/tenant/file-storage', data),
  testFileStorage: (storageType: string) =>
    client.post('/api/admin/v1/tenant/file-storage/test', null, { params: { storage_type: storageType } }),

  // AI 模型接入
  getAiSettings: () => client.get('/api/admin/v1/tenant/ai-settings'),
  updateAiSettings: (data: Record<string, unknown>) =>
    client.put('/api/admin/v1/tenant/ai-settings', data),
  testAiChat: () => client.post('/api/admin/v1/tenant/ai-settings/test-chat'),
  testAiEmbedding: () => client.post('/api/admin/v1/tenant/ai-settings/test-embedding'),
}
