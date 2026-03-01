import client from './client'
import type { ApiResponse, ContractItem, ContractVersion } from './types'

export const contractApi = {
  listByProject: (projectId: string) =>
    client.get<unknown, ApiResponse<ContractItem[]>>(`/api/v1/projects/${projectId}/contracts`),
  create: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<{ contract: ContractItem; version: ContractVersion }>>(`/api/v1/projects/${projectId}/contracts`, data),
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
}
