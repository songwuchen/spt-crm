// 扩展平台(低代码)表单引擎 API。对接后端 /api/v1/lc/*。
import client from './client'
import type { ApiResponse, PageData } from './types'
import type {
  FieldDefinition, FormRule, FormTemplate, FormVersion, FormInstance, FormInstanceDetail,
  BuiltinTemplate,
} from '@/types/lowcode'

export interface SaveDesignPayload {
  field_definitions: FieldDefinition[]
  layout_definition?: Record<string, unknown>
  rule_definitions?: FormRule[]
}

export const lowcodeApi = {
  // ---- 模板 ----
  listTemplates: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<FormTemplate>>>('/api/v1/lc/form-templates', { params }),
  getTemplate: (id: string) =>
    client.get<unknown, ApiResponse<FormTemplate>>(`/api/v1/lc/form-templates/${id}`),
  createTemplate: (data: Partial<FormTemplate>) =>
    client.post<unknown, ApiResponse<FormTemplate>>('/api/v1/lc/form-templates', data),
  updateTemplate: (id: string, data: Partial<FormTemplate>) =>
    client.put<unknown, ApiResponse<FormTemplate>>(`/api/v1/lc/form-templates/${id}`, data),
  deleteTemplate: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/lc/form-templates/${id}`),

  // ---- 模板市场(内置模板库) ----
  listBuiltins: () =>
    client.get<unknown, ApiResponse<BuiltinTemplate[]>>('/api/v1/lc/builtin-templates'),
  installBuiltin: (key: string) =>
    client.post<unknown, ApiResponse<FormTemplate>>(`/api/v1/lc/builtin-templates/${key}/install`),

  // ---- 设计 / 版本 / 发布 ----
  loadDesign: (id: string) =>
    client.get<unknown, ApiResponse<FormVersion>>(`/api/v1/lc/form-templates/${id}/design`),
  saveDesign: (id: string, data: SaveDesignPayload) =>
    client.post<unknown, ApiResponse<FormVersion>>(`/api/v1/lc/form-templates/${id}/design`, data),
  publish: (id: string) =>
    client.post<unknown, ApiResponse<FormVersion>>(`/api/v1/lc/form-templates/${id}/publish`),
  listVersions: (id: string) =>
    client.get<unknown, ApiResponse<FormVersion[]>>(`/api/v1/lc/form-templates/${id}/versions`),
  publishedVersion: (id: string) =>
    client.get<unknown, ApiResponse<FormVersion>>(`/api/v1/lc/form-templates/${id}/published-version`),

  // ---- 实体扩展字段(统一自定义字段) ----
  entityFields: (entityType: string) =>
    client.get<unknown, ApiResponse<{ field_definitions: FieldDefinition[] }>>(`/api/v1/lc/entity-fields/${entityType}`),
  entityTemplate: (entityType: string) =>
    client.get<unknown, ApiResponse<FormTemplate>>(`/api/v1/lc/entity-templates/${entityType}`),

  // ---- 数据(实例) ----
  listInstances: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<FormInstance>>>('/api/v1/lc/form-instances', { params }),
  getInstance: (id: string) =>
    client.get<unknown, ApiResponse<FormInstanceDetail>>(`/api/v1/lc/form-instances/${id}`),
  createInstance: (data: { template_id: string; form_data: Record<string, unknown>; title?: string; as_draft?: boolean }) =>
    client.post<unknown, ApiResponse<{ id: string; status: string; business_no?: string }>>('/api/v1/lc/form-instances', data),
  updateInstance: (id: string, data: { form_data?: Record<string, unknown>; title?: string }) =>
    client.put<unknown, ApiResponse<{ id: string; status: string }>>(`/api/v1/lc/form-instances/${id}`, data),
  deleteInstance: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/lc/form-instances/${id}`),
}
