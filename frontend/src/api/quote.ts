import client from './client'
import type { ApiResponse, QuoteItem, QuoteVersion, QuoteLine, CostSnapshotItem, QuoteSendLogItem } from './types'

export const quoteApi = {
  listByProject: (projectId: string) =>
    client.get<unknown, ApiResponse<QuoteItem[]>>(`/api/v1/projects/${projectId}/quotes`),
  create: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<{ quote: QuoteItem; version: QuoteVersion }>>(`/api/v1/projects/${projectId}/quotes`, data),
  get: (id: string) =>
    client.get<unknown, ApiResponse<QuoteItem>>(`/api/v1/quotes/${id}`),
  update: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<QuoteItem>>(`/api/v1/quotes/${id}`, data),
  delete: (id: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/quotes/${id}`),
  newVersion: (id: string) =>
    client.post<unknown, ApiResponse<QuoteVersion>>(`/api/v1/quotes/${id}/new_version`),

  // Version
  getVersion: (vid: string) =>
    client.get<unknown, ApiResponse<QuoteVersion & { lines: QuoteLine[] }>>(`/api/v1/quote_versions/${vid}`),
  updateVersion: (vid: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<QuoteVersion>>(`/api/v1/quote_versions/${vid}`, data),

  // Lines
  addLine: (vid: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<QuoteLine>>(`/api/v1/quote_versions/${vid}/lines`, data),
  updateLine: (lid: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<QuoteLine>>(`/api/v1/quote_lines/${lid}`, data),
  deleteLine: (lid: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/quote_lines/${lid}`),

  // Version Comparison
  compareVersions: (quoteId: string, versionA: string, versionB: string) =>
    client.get<unknown, ApiResponse<any>>(`/api/v1/quotes/${quoteId}/compare`, {
      params: { version_a: versionA, version_b: versionB },
    }),

  // Cost Snapshots
  listCostSnapshots: (vid: string) =>
    client.get<unknown, ApiResponse<CostSnapshotItem[]>>(`/api/v1/quote_versions/${vid}/cost_snapshots`),
  createCostSnapshot: (vid: string, data?: { note?: string; breakdown_json?: Record<string, number> }) =>
    client.post<unknown, ApiResponse<CostSnapshotItem>>(`/api/v1/quote_versions/${vid}/cost_snapshots`, data || {}),

  // Send Logs
  sendQuote: (vid: string, data: { channel: string; to_list_json?: { name: string; contact: string }[]; subject?: string; body?: string; attachments_json?: { filename: string }[] }) =>
    client.post<unknown, ApiResponse<QuoteSendLogItem>>(`/api/v1/quote_versions/${vid}/send`, data),
  listSendLogs: (quoteId: string) =>
    client.get<unknown, ApiResponse<QuoteSendLogItem[]>>(`/api/v1/quotes/${quoteId}/send_logs`),
}
