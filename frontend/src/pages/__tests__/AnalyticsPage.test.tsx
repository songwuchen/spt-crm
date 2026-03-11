import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    funnel: vi.fn(),
    winLoss: vi.fn(),
    topCustomers: vi.fn(),
    paymentOverview: vi.fn(),
    milestoneOverview: vi.fn(),
    monthlyRevenue: vi.fn(),
    leaderboard: vi.fn(),
    trend: vi.fn(),
    collection: vi.fn(),
    customerRegionStats: vi.fn(),
    winForecast: vi.fn(),
    stageDuration: vi.fn(),
    exportExcelUrl: vi.fn().mockReturnValue('/api/v1/dashboard/export/excel'),
    exportPdfUrl: vi.fn().mockReturnValue('/api/v1/dashboard/export/pdf'),
  },
}))

vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))

vi.mock('@ant-design/charts', () => ({
  Column: () => <div data-testid="column-chart" />,
  Pie: () => <div data-testid="pie-chart" />,
  Funnel: () => <div data-testid="funnel-chart" />,
  Bar: () => <div data-testid="bar-chart" />,
  Line: () => <div data-testid="line-chart" />,
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import AnalyticsPage from '../analytics/AnalyticsPage'
import { dashboardApi } from '@/api/dashboard'

describe('AnalyticsPage', { timeout: 15000 }, () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(dashboardApi.funnel as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(dashboardApi.winLoss as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { won_count: 5, lost_count: 3, won_amount: 500000, lost_amount: 200000, win_rate: 62 },
    })
    ;(dashboardApi.topCustomers as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(dashboardApi.paymentOverview as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { total_planned: 100000, total_received: 50000, overdue_count: 2, overdue_amount: 10000, upcoming_30d_amount: 20000, collection_rate: 50 },
    })
    ;(dashboardApi.milestoneOverview as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { pending: 2, in_progress: 3, completed: 5, delayed: 1, total: 11, completion_rate: 45 },
    })
    ;(dashboardApi.monthlyRevenue as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(dashboardApi.leaderboard as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(dashboardApi.trend as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(dashboardApi.collection as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(dashboardApi.customerRegionStats as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(dashboardApi.winForecast as ReturnType<typeof vi.fn>).mockResolvedValue({ data: null })
    ;(dashboardApi.stageDuration as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
  })

  it('renders page title after loading', async () => {
    render(<AnalyticsPage />)
    await waitFor(() => {
      expect(screen.getByText('报表中心')).toBeInTheDocument()
    })
  })

  it('calls all dashboard APIs on mount', async () => {
    render(<AnalyticsPage />)
    await waitFor(() => {
      expect(dashboardApi.funnel).toHaveBeenCalled()
      expect(dashboardApi.winLoss).toHaveBeenCalled()
      expect(dashboardApi.paymentOverview).toHaveBeenCalled()
    })
  })

  it('renders charts after loading', async () => {
    render(<AnalyticsPage />)
    await waitFor(() => {
      expect(screen.getByText('销售漏斗')).toBeInTheDocument()
    })
  })

  it('renders export buttons after loading', async () => {
    render(<AnalyticsPage />)
    await waitFor(() => {
      expect(screen.getByText('导出Excel')).toBeInTheDocument()
    })
  })
})
