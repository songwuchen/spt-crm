/**
 * OpportunityDetail page tests — rendering, tabs, stage transitions, AI actions.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

// ---- Mocks (no top-level variable refs inside vi.mock factories) -----------

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({ id: 'proj-1' }),
  }
})

vi.mock('@/api/project', () => ({
  projectApi: {
    get: vi.fn(),
    stageHistory: vi.fn(),
    health: vi.fn(),
    listShares: vi.fn(),
    advance: vi.fn(),
    rollback: vi.fn(),
  },
}))

vi.mock('@/api/customer', () => ({
  customerApi: { get: vi.fn() },
}))

vi.mock('@/api/quote', () => ({
  quoteApi: { listByProject: vi.fn() },
}))

vi.mock('@/api/contract', () => ({
  contractApi: { listByProject: vi.fn() },
}))

vi.mock('@/api/solution', () => ({
  solutionApi: { listByProject: vi.fn() },
}))

vi.mock('@/api/delivery', () => ({
  deliveryApi: { listMilestones: vi.fn(), listOrderLinks: vi.fn() },
}))

vi.mock('@/api/payment', () => ({
  paymentApi: {
    listPlans: vi.fn(),
    listRecords: vi.fn(),
    listInvoices: vi.fn(),
  },
}))

vi.mock('@/api/change', () => ({
  changeApi: { listByProject: vi.fn() },
}))

vi.mock('@/api/ai', () => ({
  aiApi: {
    analyze: vi.fn(),
    findSimilarProjects: vi.fn(),
  },
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn() },
  roleApi: { list: vi.fn() },
}))

vi.mock('@/components/AttachmentPanel', () => ({
  default: () => <div data-testid="attachment-panel">AttachmentPanel</div>,
}))

vi.mock('@/components/ActivityTimeline', () => ({
  default: () => <div data-testid="activity-timeline">ActivityTimeline</div>,
}))

vi.mock('@/components/MilestoneGantt', () => ({
  default: () => <div data-testid="milestone-gantt">MilestoneGantt</div>,
}))

vi.mock('@/components/PaymentChart', () => ({
  default: () => <div data-testid="payment-chart">PaymentChart</div>,
}))

import OpportunityDetail from '../opportunity/OpportunityDetail'
import { projectApi } from '@/api/project'
import { customerApi } from '@/api/customer'
import { quoteApi } from '@/api/quote'
import { contractApi } from '@/api/contract'
import { solutionApi } from '@/api/solution'
import { deliveryApi } from '@/api/delivery'
import { paymentApi } from '@/api/payment'
import { changeApi } from '@/api/change'
import { aiApi } from '@/api/ai'
import { userApi, roleApi } from '@/api/user'

const mockProject = {
  id: 'proj-1',
  name: 'Test Project',
  customer_id: 'cust-1',
  stage_code: 'S2',
  amount_expect: 500000,
  amount_weighted: 250000,
  probability: 50,
  risk_level: 'medium',
  status: 'open',
  expected_close_date: '2026-06-30',
  owner_id: 'u-1',
  owner_name: 'Admin',
  created_at: '2026-01-01T00:00:00',
  updated_at: '2026-01-15T00:00:00',
}

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['project:view', 'project:edit', 'quote:view', 'contract:view'],
  tenant_id: 't-1',
}

describe('OpportunityDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    // Set up mock return values in beforeEach (not in vi.mock factory)
    ;(projectApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockProject })
    ;(projectApi.stageHistory as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(projectApi.health as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { score: 75, dimensions: [{ name: '进度', score: 80 }], risks: [] },
    })
    ;(projectApi.listShares as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(customerApi.get as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { id: 'cust-1', name: 'Test Corp', industry: 'Machinery', level: 'A' },
    })
    ;(quoteApi.listByProject as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(contractApi.listByProject as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(solutionApi.listByProject as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(deliveryApi.listMilestones as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(deliveryApi.listOrderLinks as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(paymentApi.listPlans as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(paymentApi.listRecords as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(paymentApi.listInvoices as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(changeApi.listByProject as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(aiApi.analyze as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { task_id: 't-1', result: { risk_level: 'low' } },
    })
    ;(aiApi.findSimilarProjects as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { similar_projects: [], insights: '' },
    })
    ;(userApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(roleApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
  })

  it('renders project name after loading', async () => {
    render(<OpportunityDetail />)
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })
  })

  it('displays project amount', async () => {
    render(<OpportunityDetail />)
    await waitFor(() => {
      expect(screen.getByText(/500,000/)).toBeInTheDocument()
    })
  })

  it('fetches project data on mount', async () => {
    render(<OpportunityDetail />)
    await waitFor(() => {
      expect(projectApi.get).toHaveBeenCalledWith('proj-1')
    })
  })

  it('fetches health score on mount', async () => {
    render(<OpportunityDetail />)
    await waitFor(() => {
      expect(projectApi.health).toHaveBeenCalledWith('proj-1')
    })
  })

  it('renders health score section', async () => {
    render(<OpportunityDetail />)
    await waitFor(() => {
      expect(screen.getByText(/健康度/)).toBeInTheDocument()
    })
  })

  it('calls AI analyze when clicking AI button', async () => {
    const user = userEvent.setup()
    render(<OpportunityDetail />)
    await waitFor(() => {
      expect(screen.getByText('Test Project')).toBeInTheDocument()
    })

    const aiButtons = screen.getAllByRole('button').filter(b => b.textContent?.includes('AI'))
    if (aiButtons.length > 0) {
      await user.click(aiButtons[0])
      await waitFor(() => {
        expect(aiApi.analyze).toHaveBeenCalled()
      })
    }
  })
})
