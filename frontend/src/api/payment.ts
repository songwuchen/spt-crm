import client from './client'
import type { ApiResponse, InvoiceItem, PaymentPlanItem, PaymentRecordItem } from './types'

export const paymentApi = {
  // Invoices
  listInvoices: (projectId: string) =>
    client.get<unknown, ApiResponse<InvoiceItem[]>>(`/api/v1/projects/${projectId}/invoices`),
  createInvoice: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<InvoiceItem>>(`/api/v1/projects/${projectId}/invoices`, data),
  updateInvoice: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<InvoiceItem>>(`/api/v1/invoices/${id}`, data),
  deleteInvoice: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/v1/invoices/${id}`),

  // Payment Plans
  listPlans: (projectId: string) =>
    client.get<unknown, ApiResponse<PaymentPlanItem[]>>(`/api/v1/projects/${projectId}/payment_plans`),
  createPlan: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<PaymentPlanItem>>(`/api/v1/projects/${projectId}/payment_plans`, data),
  bulkCreatePlans: (projectId: string, plans: Record<string, unknown>[]) =>
    client.post<unknown, ApiResponse<PaymentPlanItem[]>>(`/api/v1/projects/${projectId}/payment_plans/bulk`, { plans }),
  updatePlan: (id: string, data: Record<string, unknown>) =>
    client.put<unknown, ApiResponse<PaymentPlanItem>>(`/api/v1/payment_plans/${id}`, data),
  deletePlan: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/v1/payment_plans/${id}`),

  // Payment Records
  listRecords: (projectId: string) =>
    client.get<unknown, ApiResponse<PaymentRecordItem[]>>(`/api/v1/projects/${projectId}/payment_records`),
  createRecord: (projectId: string, data: Record<string, unknown>) =>
    client.post<unknown, ApiResponse<PaymentRecordItem>>(`/api/v1/projects/${projectId}/payment_records`, data),
  deleteRecord: (id: string) =>
    client.delete<unknown, ApiResponse<null>>(`/api/v1/payment_records/${id}`),

  // Cross-project listing
  listAllPlans: (params: Record<string, unknown>) =>
    client.get('/api/v1/payment/plans', { params }),
  listAllRecords: (params: Record<string, unknown>) =>
    client.get('/api/v1/payment/records', { params }),
  listAllInvoices: (params: Record<string, unknown>) =>
    client.get('/api/v1/payment/invoices', { params }),
}
