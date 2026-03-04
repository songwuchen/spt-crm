/**
 * QuoteDetail page tests — rendering, version selection, line items.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

// ---- Mocks ----------------------------------------------------------------

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ id: 'proj-1', qid: 'q-1' }),
  }
})

vi.mock('@/api/quote', () => ({
  quoteApi: {
    get: vi.fn(),
    listCostSnapshots: vi.fn(),
    listSendLogs: vi.fn(),
    compareVersions: vi.fn(),
  },
}))

vi.mock('@/api/contract', () => ({
  contractApi: { create: vi.fn() },
}))

vi.mock('@/api/approval', () => ({
  approvalApi: { submit: vi.fn() },
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn() },
}))

vi.mock('@/api/ai', () => ({
  aiApi: { analyze: vi.fn() },
}))

import QuoteDetail from '../opportunity/QuoteDetail'
import { quoteApi } from '@/api/quote'
import { userApi } from '@/api/user'

const mockQuote = {
  id: 'q-1',
  project_id: 'proj-1',
  quote_no: 'QT-2026-001',
  title: 'Test Quote',
  status: 'draft',
  current_version: {
    id: 'qv-1',
    version_no: 1,
    total_amount: 200000,
    cost_est: 150000,
    margin_rate: 0.25,
    discount_total: 5000,
    validity_days: 30,
    currency: 'CNY',
    status: 'draft',
    created_at: '2026-01-10T00:00:00',
  },
  versions: [
    {
      id: 'qv-1',
      version_no: 1,
      total_amount: 200000,
      status: 'draft',
      created_at: '2026-01-10T00:00:00',
    },
  ],
  lines: [
    {
      id: 'ql-1',
      version_id: 'qv-1',
      item_type: 'product',
      item_name: 'CNC Machine A',
      quantity: 2,
      unit_price: 100000,
      amount: 200000,
    },
  ],
  created_at: '2026-01-10T00:00:00',
}

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['quote:view', 'quote:edit', 'quote:approve'],
  tenant_id: 't-1',
}

describe('QuoteDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    ;(quoteApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockQuote })
    ;(quoteApi.listCostSnapshots as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(quoteApi.listSendLogs as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(userApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
  })

  it('renders quote number after loading', async () => {
    render(<QuoteDetail />)
    await waitFor(() => {
      expect(screen.getByText(/QT-2026-001/)).toBeInTheDocument()
    })
  })

  it('fetches quote on mount', async () => {
    render(<QuoteDetail />)
    await waitFor(() => {
      expect(quoteApi.get).toHaveBeenCalledWith('q-1')
    })
  })

  it('displays line items', async () => {
    render(<QuoteDetail />)
    await waitFor(() => {
      expect(screen.getByText('CNC Machine A')).toBeInTheDocument()
    })
  })

  it('shows version info', async () => {
    render(<QuoteDetail />)
    await waitFor(() => {
      expect(screen.getByText(/V1/)).toBeInTheDocument()
    })
  })

  it('calls quoteApi.get with correct id', async () => {
    render(<QuoteDetail />)
    await waitFor(() => {
      expect(quoteApi.get).toHaveBeenCalledWith('q-1')
    })
  })
})
