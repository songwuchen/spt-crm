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
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    calendarEvents: vi.fn().mockResolvedValue({ data: [] }),
    stats: vi.fn().mockResolvedValue({ data: { customer_total: 0, lead_total: 0, monthly_new_customers: 0, pending_leads: 0, project_total: 0, active_projects: 0, pipeline_value: 0, ticket_open: 0, contract_total: 0, quote_total: 0, ticket_total: 0 } }),
    myOverview: vi.fn().mockResolvedValue({ data: null }),
  },
}))

vi.mock('@/api/approval', () => ({
  approvalApi: {
    myPending: vi.fn().mockResolvedValue({ data: [] }),
    pendingCount: vi.fn().mockResolvedValue({ data: 0 }),
  },
}))

vi.mock('@/api/customer', () => ({
  customerApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/lead', () => ({
  leadApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/project', () => ({
  projectApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/notification', () => ({
  notificationApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    markRead: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('@/stores/useAuthStore', () => ({
  useAuthStore: vi.fn((selector: any) => {
    const state = { user: { username: 'admin', real_name: '管理员' }, token: 'test' }
    return selector ? selector(state) : state
  }),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({ id: 'tk-1' }) }
})

import dayjs from 'dayjs'
import MobilePayments from '../mobile/MobilePayments'
import MobileCalendar from '../mobile/MobileCalendar'
import MobileWorkbench from '../mobile/MobileWorkbench'
import MobileCustomers from '../mobile/MobileCustomers'
import MobileLeads from '../mobile/MobileLeads'
import MobileOpportunities from '../mobile/MobileOpportunities'
import MobileApprovals from '../mobile/MobileApprovals'
import MobileNotifications from '../mobile/MobileNotifications'
import MobileServiceTickets from '../mobile/MobileServiceTickets'

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

describe('MobileWorkbench', { timeout: 15000 }, () => {
  it('renders welcome greeting', () => {
    render(<MobileWorkbench />)
    expect(screen.getByText(/你好/)).toBeInTheDocument()
  })

  it('shows quick actions section', () => {
    render(<MobileWorkbench />)
    expect(screen.getByText('快捷操作')).toBeInTheDocument()
  })
})

describe('MobileCustomers', { timeout: 15000 }, () => {
  it('renders page title', () => {
    render(<MobileCustomers />)
    expect(screen.getByText('客户')).toBeInTheDocument()
  })

  it('renders search input', () => {
    render(<MobileCustomers />)
    expect(screen.getByPlaceholderText('搜索客户名称...')).toBeInTheDocument()
  })
})

describe('MobileLeads', { timeout: 15000 }, () => {
  it('renders page title', () => {
    render(<MobileLeads />)
    expect(screen.getByText('线索')).toBeInTheDocument()
  })

  it('renders status filter tabs', () => {
    render(<MobileLeads />)
    expect(screen.getByText('跟进中')).toBeInTheDocument()
  })
})

describe('MobileOpportunities', { timeout: 15000 }, () => {
  it('renders page title', () => {
    render(<MobileOpportunities />)
    expect(screen.getByText('商机看板')).toBeInTheDocument()
  })
})

describe('MobileApprovals', { timeout: 15000 }, () => {
  it('renders page title', async () => {
    render(<MobileApprovals />)
    expect(await screen.findByText('审批中心')).toBeInTheDocument()
  })
})

describe('MobileNotifications', { timeout: 15000 }, () => {
  it('renders page title', () => {
    render(<MobileNotifications />)
    expect(screen.getByText('通知')).toBeInTheDocument()
  })
})

describe('MobileServiceTickets', { timeout: 15000 }, () => {
  it('renders page title', () => {
    render(<MobileServiceTickets />)
    expect(screen.getByText('售后工单')).toBeInTheDocument()
  })

  it('renders status filter tabs', () => {
    render(<MobileServiceTickets />)
    expect(screen.getByText('全部')).toBeInTheDocument()
  })
})
