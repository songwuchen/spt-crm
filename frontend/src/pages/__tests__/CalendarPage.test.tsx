import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    calendarEvents: vi.fn(),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import CalendarPage from '../calendar/CalendarPage'
import { dashboardApi } from '@/api/dashboard'

describe('CalendarPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(dashboardApi.calendarEvents as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: [
        { id: 'e-1', type: 'follow_up', title: '跟进客户A', date: '2026-03-10', color: '#3b82f6' },
        { id: 'e-2', type: 'payment_due', title: '回款到期', date: '2026-03-15', color: '#f59e0b' },
      ],
    })
  })

  it('renders page title', () => {
    render(<CalendarPage />)
    expect(screen.getByText('日程日历')).toBeInTheDocument()
  })

  it('loads events on mount', async () => {
    render(<CalendarPage />)
    await waitFor(() => {
      expect(dashboardApi.calendarEvents).toHaveBeenCalled()
    })
  })

  it('renders type filter dropdown', () => {
    render(<CalendarPage />)
    expect(screen.getByText('全部类型')).toBeInTheDocument()
  })
})
