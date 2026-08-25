import client from './client'
import type { ApiResponse, ContractItem, ContractVersion } from './types'

export const contractApi = {
  list: (params?: Record<string, unknown>) =>
    client.get('/api/v1/contracts', { params }),
  /** 合同管理仪表盘汇总 */
  dashboardSummary: (params?: {
    customer_name?: string
    card_date_from?: string
    card_date_to?: string
    department_id?: string
    assignee_id?: string
  }) =>
    client.get('/api/v1/contracts/dashboard/summary', { params }),
  listByProject: (projectId: string) =>
    client.get<unknown, ApiResponse<ContractItem[]>>(`/api/v1/projects/${projectId}/contracts`),
  /** 编号查询：合同图纸对应表 */
  drawingMapLookups: (params?: { keyword?: string; limit?: number; exclude_contract_id?: string }) =>
    client.get<unknown, ApiResponse<Array<{
      id: string
      contract_no: string
      drawing_no: string
      department_id?: string | null
      label: string
    }>>>('/api/v1/contracts/drawing-map-lookups', { params }),
  /** 应用领域 / 应用物料 / 物料名称基础表选项 */
  baseLookups: (params: {
    type: 'application_field' | 'application_material' | 'material_name'
    keyword?: string
    limit?: number
  }) =>
    client.get<unknown, ApiResponse<Array<{
      id: string
      name: string
      label: string
    }>>>('/api/v1/contracts/base-lookups', { params }),
  /** 新建登记：预览下一流水号 */
  peekSerialNo: (params?: { card_date?: string }) =>
    client.get<unknown, ApiResponse<{ serial_no: string }>>(
      '/api/v1/contracts/peek-serial-no', { params },
    ),
  /** 新建登记：预览下一图纸编号（按取号当天，与订货日无关） */
  peekDrawingNo: (params?: { number_attr?: string }) =>
    client.get<unknown, ApiResponse<{ drawing_no: string; number_attr?: string }>>(
      '/api/v1/contracts/peek-drawing-no', { params },
    ),
  /** 新建登记：重新取号（当前号仍可用则保留；按取号当天） */
  allocateDrawingNo: (body?: {
    drawing_no?: string
    number_attr?: string
  }) =>
    client.post<unknown, ApiResponse<{ drawing_no: string; number_attr?: string }>>(
      '/api/v1/contracts/allocate-drawing-no', body || {},
    ),
  create: (projectId: string | null | undefined, data: Record<string, unknown>) =>
    projectId
      ? client.post<unknown, ApiResponse<{ contract: ContractItem; version: ContractVersion }>>(
        `/api/v1/projects/${projectId}/contracts`, data,
      )
      : client.post<unknown, ApiResponse<{ contract: ContractItem; version: ContractVersion }>>(
        '/api/v1/contracts', { ...data, project_id: null },
      ),
  get: (id: string) =>
    client.get<unknown, ApiResponse<ContractItem>>(`/api/v1/contracts/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ContractItem>>(`/api/v1/contracts/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/contracts/${id}`),
  newVersion: (id: string) =>
    client.post<unknown, ApiResponse<ContractVersion>>(`/api/v1/contracts/${id}/new_version`),
  sign: (id: string, data: { signed_date: string }) =>
    client.post<unknown, ApiResponse<ContractItem>>(`/api/v1/contracts/${id}/sign`, data),
  fromQuote: (quoteId: string) =>
    client.post<unknown, ApiResponse<{ contract: ContractItem; version: ContractVersion }>>('/api/v1/contracts/from_quote', { quote_id: quoteId }),

  // Version
  getVersion: (vid: string) =>
    client.get<unknown, ApiResponse<ContractVersion>>(`/api/v1/contract_versions/${vid}`),
  updateVersion: (vid: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<ContractVersion>>(`/api/v1/contract_versions/${vid}`, data),
  submitVersion: (vid: string, data?: { assignee_ids?: string[]; assignee_names?: string[] }) =>
    client.post<unknown, ApiResponse<ContractVersion>>(`/api/v1/contract_versions/${vid}/submit`, data || {}),

  batchExportPdf: (ids: string[]) =>
    client.post('/api/v1/contracts/batch_export/pdf', { ids }, { responseType: 'blob' }),
  related: (id: string) =>
    client.get<unknown, ApiResponse<{
      payment_plans: Array<Record<string, unknown>>
      payment_records: Array<Record<string, unknown>>
      invoices: Array<Record<string, unknown>>
      invoice_applications: Array<Record<string, unknown>>
      milestones: Array<Record<string, unknown>>
    }>>(`/api/v1/contracts/${id}/related`),
}
