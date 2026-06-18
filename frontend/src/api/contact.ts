import client from './client'
import type { ApiResponse, Contact } from './types'

export const contactApi = {
  listAll: (params: Record<string, any>) =>
    client.get<unknown, ApiResponse<{ items: (Contact & { customer_name?: string })[]; total: number }>>('/api/v1/contacts', { params }),
  list: (customerId: string) =>
    client.get<unknown, ApiResponse<Contact[]>>(`/api/v1/customers/${customerId}/contacts`),
  create: (customerId: string, data: Partial<Contact>) =>
    client.post<unknown, ApiResponse<Contact>>(`/api/v1/customers/${customerId}/contacts`, data),
  update: (customerId: string, contactId: string, data: Partial<Contact>) =>
    client.put<unknown, ApiResponse<Contact>>(`/api/v1/customers/${customerId}/contacts/${contactId}`, data),
  delete: (customerId: string, contactId: string) =>
    client.delete<unknown, ApiResponse<void>>(`/api/v1/customers/${customerId}/contacts/${contactId}`),
  importFile: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return client.post<unknown, ApiResponse<{ success: number; failed: number; total: number; errors: { row: number; reason: string }[] }>>(
      '/api/v1/contacts/import',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },
  importCsv: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return client.post<unknown, ApiResponse<{ success: number; failed: number; total: number; errors: { row: number; reason: string }[] }>>(
      '/api/v1/contacts/import',
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } },
    )
  },
  exportExcel: (params?: { keyword?: string; role_type?: string }) =>
    client.get('/api/v1/contacts/export', {
      params: params || {},
      responseType: 'blob',
    }),
  downloadTemplate: () =>
    client.get('/api/v1/contacts/template', { responseType: 'blob' }),
}
