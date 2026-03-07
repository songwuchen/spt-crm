import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/api/payment', () => ({
  paymentApi: {
    listAllPlans: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/serviceTicket', () => ({
  serviceTicketApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 'tk-1', ticket_no: 'TK-001', type: 'fault', priority: 'high', status: 'open', description: '测试' } }),
  },
}))

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    calendarEvents: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({ id: 'tk-1' }) }
})

import dayjs from 'dayjs'
import MobilePayments from '../mobile/MobilePayments'
import MobileCalendar from '../mobile/MobileCalendar'

describe('MobilePayments', () => {
  it('renders page title', () => {
    render(<MobilePayments />)
    expect(screen.getByText('回款管理')).toBeInTheDocument()
  })

  it('shows summary cards', () => {
    render(<MobilePayments />)
    expect(screen.getByText('计划总额')).toBeInTheDocument()
    expect(screen.getByText('已回款')).toBeInTheDocument()
  })
})

describe('MobileCalendar', () => {
  it('renders page header', () => {
    render(<MobileCalendar />)
    expect(screen.getByText('日程')).toBeInTheDocument()
  })

  it('renders month navigation', () => {
    render(<MobileCalendar />)
    expect(screen.getByText(dayjs().format('YYYY年M月'))).toBeInTheDocument()
  })
})
