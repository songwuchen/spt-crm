import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import Dashboard from '../dashboard/Dashboard'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

// Mock chart components (canvas-based, not renderable in jsdom)
vi.mock('@ant-design/charts', () => ({
  Line: () => null,
  Column: () => null,
  Pie: () => null,
  Funnel: () => null,
}))

// Mock dashboard API
vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    stats: vi.fn().mockResolvedValue({
      data: {
        customer_total: 42,
        lead_total: 15,
        monthly_new_customers: 5,
        pending_leads: 3,
        project_total: 20,
        active_projects: 8,
        quote_total: 12,
        solution_total: 6,
        milestone_total: 30,
        milestone_delayed: 2,
        invoice_total: 10,
        payment_received: 500000,
        change_total: 3,
        ticket_total: 7,
        ticket_open: 2,
        pipeline_value: 5000000,
        contract_total: 9,
      },
    }),
    alerts: vi.fn().mockResolvedValue({ data: [] }),
    trends: vi.fn().mockResolvedValue({
      data: {
        customers: { current: 42, previous: 38, diff: 4, pct: 10.5 },
        leads: { current: 15, previous: 12, diff: 3, pct: 25 },
        projects: { current: 20, previous: 18, diff: 2, pct: 11 },
        tickets: { current: 7, previous: 5, diff: 2, pct: 40 },
      },
    }),
    myOverview: vi.fn().mockResolvedValue({ data: {
      my_customer_count: 10, my_active_projects: 3, my_pipeline: 100000,
      my_won_month: 1, my_pending_leads: 2, my_open_tickets: 1,
      expiring_contracts: [], stalled_projects: [],
    }}),
    funnel: vi.fn().mockResolvedValue({ data: [] }),
    paymentOverview: vi.fn().mockResolvedValue({ data: null }),
    leaderboard: vi.fn().mockResolvedValue({ data: [] }),
    trend: vi.fn().mockResolvedValue({ data: [] }),
    collection: vi.fn().mockResolvedValue({ data: [] }),
    monthlyRevenue: vi.fn().mockResolvedValue({ data: [] }),
    winLoss: vi.fn().mockResolvedValue({ data: { won_count: 0, lost_count: 0, win_rate: 0, won_amount: 0, lost_amount: 0 } }),
    contractExpiry: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('@/api/approval', () => ({
  approvalApi: {
    myPending: vi.fn().mockResolvedValue({ data: [] }),
    decide: vi.fn(),
    statistics: vi.fn().mockResolvedValue({ data: null }),
  },
}))

const mockUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: [],
  tenant_id: 't-1',
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().setUser(mockUser)
    })
  })

  it('renders page title', () => {
    render(<Dashboard />)
    expect(screen.getByText('工作台')).toBeInTheDocument()
  })

  it('renders welcome message with user name', () => {
    render(<Dashboard />)
    expect(screen.getByText('Admin')).toBeInTheDocument()
  })

  it('renders refresh button', () => {
    render(<Dashboard />)
    expect(screen.getByText('刷新')).toBeInTheDocument()
  })

  it('loads and displays stats', async () => {
    render(<Dashboard />)
    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument() // customer_total
      expect(screen.getByText('15')).toBeInTheDocument() // lead_total
    })
  })

  it('displays KPI labels', () => {
    render(<Dashboard />)
    expect(screen.getByText('客户总数')).toBeInTheDocument()
    expect(screen.getByText('线索总数')).toBeInTheDocument()
    expect(screen.getByText('商机总数')).toBeInTheDocument()
  })

  it('renders quick action buttons', () => {
    render(<Dashboard />)
    expect(screen.getByText('新建客户')).toBeInTheDocument()
    expect(screen.getByText('新建线索')).toBeInTheDocument()
    expect(screen.getByText('新建商机')).toBeInTheDocument()
  })

  it('renders today tasks section', () => {
    render(<Dashboard />)
    expect(screen.getByText('今日任务')).toBeInTheDocument()
  })

  it('renders leaderboard section', () => {
    render(<Dashboard />)
    expect(screen.getByText('业绩排行')).toBeInTheDocument()
  })
})
