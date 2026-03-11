import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('@/api/payment', () => ({
  paymentApi: {
    listAllPlans: vi.fn(),
    listAllRecords: vi.fn(),
    listAllInvoices: vi.fn(),
    deletePlan: vi.fn(),
    deleteRecord: vi.fn(),
    deleteInvoice: vi.fn(),
  },
}))

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    paymentOverview: vi.fn(),
  },
}))

vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import PaymentPage from '../payment/PaymentPage'
import { paymentApi } from '@/api/payment'
import { dashboardApi } from '@/api/dashboard'

describe('PaymentPage', { timeout: 15000 }, () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(paymentApi.listAllPlans as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(paymentApi.listAllRecords as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(paymentApi.listAllInvoices as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
    ;(dashboardApi.paymentOverview as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        total_planned: 100000,
        total_received: 50000,
        overdue_count: 2,
        overdue_amount: 10000,
        upcoming_30d_amount: 20000,
        collection_rate: 50,
      },
    })
  })

  it('renders page title', () => {
    render(<PaymentPage />)
    expect(screen.getByText('回款管理')).toBeInTheDocument()
  })

  it('renders tabs for plans, records, invoices', () => {
    render(<PaymentPage />)
    expect(screen.getByRole('tab', { name: /回款计划/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /到账记录/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /发票/ })).toBeInTheDocument()
  })

  it('has export button', () => {
    render(<PaymentPage />)
    expect(screen.getByText('导出')).toBeInTheDocument()
  })

  it('loads overview data on mount', async () => {
    render(<PaymentPage />)
    await waitFor(() => {
      expect(dashboardApi.paymentOverview).toHaveBeenCalled()
    })
  })

  it('displays overview cards when data loads', async () => {
    render(<PaymentPage />)
    await waitFor(() => {
      expect(screen.getByText('计划总额')).toBeInTheDocument()
      expect(screen.getByText('已回款')).toBeInTheDocument()
      expect(screen.getByText('回款率')).toBeInTheDocument()
      expect(screen.getByText('50%')).toBeInTheDocument()
    })
  })

  it('calls all list APIs on mount', async () => {
    render(<PaymentPage />)
    await waitFor(() => {
      expect(paymentApi.listAllPlans).toHaveBeenCalled()
      expect(paymentApi.listAllRecords).toHaveBeenCalled()
      expect(paymentApi.listAllInvoices).toHaveBeenCalled()
    })
  })
})
