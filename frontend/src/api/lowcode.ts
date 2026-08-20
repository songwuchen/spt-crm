// 扩展平台(低代码)表单引擎 API。对接后端 /api/v1/lc/*。
import client from './client'
import type { ApiResponse, PageData } from './types'
import type {
  FieldDefinition, FormRule, FormTemplate, FormVersion, FormInstance, FormInstanceDetail,
  BuiltinTemplate, EntityFormSchema,
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
  /** 侧栏模块：按稳定 code=key 确保已安装并发布 */
  ensureBuiltin: (key: string) =>
    client.post<unknown, ApiResponse<FormTemplate>>(`/api/v1/lc/builtin-templates/${key}/ensure`),
  getTemplateByCode: (code: string) =>
    client.get<unknown, ApiResponse<FormTemplate>>(`/api/v1/lc/form-templates/by-code/${encodeURIComponent(code)}`),

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
  /** 预览下一流水号（不消耗计数），用于填报页即时展示 */
  peekSerials: (id: string, form_data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<Record<string, string>>>(
      `/api/v1/lc/form-templates/${id}/peek-serials`,
      { form_data },
    ),
  /** 重新取号：正式占号并避开库中已有值 */
  allocateSerials: (id: string, form_data: Record<string, unknown>, field_ids?: string[]) =>
    client.post<unknown, ApiResponse<Record<string, string>>>(
      `/api/v1/lc/form-templates/${id}/allocate-serials`,
      { form_data, field_ids },
    ),

  /** 按部门 id 查部门编号基础表 */
  lookupDeptCode: (departmentId: string) =>
    client.get<unknown, ApiResponse<{ department_id: string; dept_code: string | null }>>(
      '/api/v1/lc/department-code',
      { params: { department_id: departmentId } },
    ),

  /** 按业务员查区域经理/组长对照表 */
  lookupSalespersonRegion: (salespersonId: string) =>
    client.get<unknown, ApiResponse<{
      salesperson_id: string | null
      region_manager_id: string | null
      region_manager_name: string | null
    }>>(
      '/api/v1/lc/salesperson-region',
      { params: { salesperson_id: salespersonId } },
    ),

  /** 基础资料表选项（物料名称 / 应用领域 / 应用物料） */
  baseLookups: (params: {
    type: 'application_field' | 'application_material' | 'material_name'
    keyword?: string
    limit?: number
  }) =>
    client.get<unknown, ApiResponse<Array<{ id: string; name: string; label: string }>>>(
      '/api/v1/lc/base-lookups',
      { params },
    ),

  // ---- 实体扩展字段(统一自定义字段) ----
  entityFields: (entityType: string) =>
    client.get<unknown, ApiResponse<{ field_definitions: FieldDefinition[]; rule_definitions: FormRule[] }>>(`/api/v1/lc/entity-fields/${entityType}`),
  entityTemplate: (entityType: string) =>
    client.get<unknown, ApiResponse<FormTemplate>>(`/api/v1/lc/entity-templates/${entityType}`),
  /** 业务表单用的完整字段策略：原生字段(含租户覆盖) + 扩展字段 + 规则。 */
  entityFormSchema: (entityType: string) =>
    client.get<unknown, ApiResponse<EntityFormSchema>>(`/api/v1/lc/entity-form-schema/${entityType}`),

  // ---- 数据(实例) ----
  listInstances: (params: Record<string, unknown>) =>
    client.get<unknown, ApiResponse<PageData<FormInstance>>>('/api/v1/lc/form-instances', { params }),
  getInstance: (id: string) =>
    client.get<unknown, ApiResponse<FormInstanceDetail>>(`/api/v1/lc/form-instances/${id}`),
  createInstance: (data: { template_id: string; form_data: Record<string, unknown>; title?: string; as_draft?: boolean }) =>
    client.post<unknown, ApiResponse<{ id: string; status: string; business_no?: string }>>('/api/v1/lc/form-instances', data),
  updateInstance: (id: string, data: { form_data?: Record<string, unknown>; title?: string }) =>
    client.put<unknown, ApiResponse<{ id: string; status: string }>>(`/api/v1/lc/form-instances/${id}`, data),
  /** 草稿提交审批（校验必填并启动绑定流程） */
  submitInstance: (id: string, data?: { form_data?: Record<string, unknown>; title?: string }) =>
    client.post<unknown, ApiResponse<{ id: string; status: string; business_no?: string; process_instance_id?: string }>>(
      `/api/v1/lc/form-instances/${id}/submit`, data || {},
    ),
  deleteInstance: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/lc/form-instances/${id}`),
}
