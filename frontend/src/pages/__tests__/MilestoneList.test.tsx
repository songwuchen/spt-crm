import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('@/api/delivery', () => ({
  deliveryApi: {
    listAllMilestones: vi.fn(),
    createMilestone: vi.fn(),
    updateMilestone: vi.fn(),
    deleteMilestone: vi.fn(),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import MilestoneList from '../delivery/MilestoneList'
import { deliveryApi } from '@/api/delivery'

describe('MilestoneList', { timeout: 15000 }, () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(deliveryApi.listAllMilestones as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { items: [], total: 0 },
    })
  })

  it('renders page title', () => {
    render(<MilestoneList />)
    expect(screen.getByText('交付里程碑')).toBeInTheDocument()
  })

  it('renders subtitle', () => {
    render(<MilestoneList />)
    expect(screen.getByText('查看所有项目的交付里程碑')).toBeInTheDocument()
  })

  it('calls listAllMilestones on mount', async () => {
    render(<MilestoneList />)
    await waitFor(() => {
      expect(deliveryApi.listAllMilestones).toHaveBeenCalled()
    })
  })

  it('renders search input', () => {
    render(<MilestoneList />)
    expect(screen.getByPlaceholderText('搜索里程碑名称/编号...')).toBeInTheDocument()
  })

  it('displays milestone data when loaded', async () => {
    ;(deliveryApi.listAllMilestones as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [
          {
            id: 'm-1',
            milestone_code: 'M001',
            name: '需求确认',
            status: 'doing',
            plan_date: '2026-04-01',
            actual_date: null,
            note: '进行中',
            sort_order: 1,
            project_id: 'p-1',
          },
        ],
        total: 1,
      },
    })
    render(<MilestoneList />)
    await waitFor(() => {
      expect(screen.getByText('需求确认')).toBeInTheDocument()
      expect(screen.getByText('M001')).toBeInTheDocument()
    })
  })
})
