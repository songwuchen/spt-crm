import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

vi.mock('@/api/serviceTicket', () => ({
  serviceTicketApi: {
    list: vi.fn(),
    listRenewals: vi.fn(),
    slaStats: vi.fn(),
  },
}))

vi.mock('@/api/customer', () => ({
  customerApi: { list: vi.fn() },
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn() },
}))

vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import ServiceTicketList from '../service/ServiceTicketList'
import { serviceTicketApi } from '@/api/serviceTicket'

const adminUser: UserInfo = {
  id: 'u-1', username: 'admin', real_name: 'Admin',
  roles: ['admin'], permissions: ['service:view', 'service:create', 'service:edit'],
  tenant_id: 't-1',
}

describe('ServiceTicketList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.getState().setUser(adminUser)
    ;(serviceTicketApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [
          { id: 't-1', ticket_no: 'TK-001', type: 'fault', priority: 'high', status: 'open', description: '设备故障' },
          { id: 't-2', ticket_no: 'TK-002', type: 'maintenance', priority: 'medium', status: 'resolved', description: '定期维护' },
        ],
        total: 2,
      },
    })
    ;(serviceTicketApi.listRenewals as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    ;(serviceTicketApi.slaStats as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        open_tickets: 3, resolved_tickets: 10,
        breach_count: 1, near_breach_count: 2, on_time_rate: 92.3,
        sla_config: { critical: 4, high: 8, medium: 24, low: 72 },
        by_priority: { high: 2, medium: 1 },
      },
    })
  })

  it('renders page title', () => {
    render(<ServiceTicketList />)
    expect(screen.getByText('售后服务')).toBeInTheDocument()
  })

  it('displays SLA stats', async () => {
    render(<ServiceTicketList />)
    await waitFor(() => {
      expect(screen.getByText('92.3%')).toBeInTheDocument()
    })
  })

  it('shows SLA breach count', async () => {
    render(<ServiceTicketList />)
    await waitFor(() => {
      expect(screen.getByText('SLA 达标率')).toBeInTheDocument()
    })
  })

  it('loads and displays tickets', async () => {
    render(<ServiceTicketList />)
    await waitFor(() => {
      expect(screen.getByText('TK-001')).toBeInTheDocument()
      expect(screen.getByText('TK-002')).toBeInTheDocument()
    })
  })
})
