import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/api/lead', () => ({
  leadApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 'l1', title: '测试线索', lead_code: 'LD-001', status: 'new', score: 60, source: 'website' } }),
  },
}))

vi.mock('@/api/serviceTicket', () => ({
  serviceTicketApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 'tk-1', ticket_no: 'SRV-001', type: 'fault', priority: 'high', status: 'open', description: '测试工单' } }),
    update: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/api/activity', () => ({
  activityApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    create: vi.fn().mockResolvedValue({ data: {} }),
    togglePin: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  },
}))

vi.mock('@/api/attachment', () => ({
  attachmentApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    upload: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({ data: null }),
  },
}))

vi.mock('@/components/VoiceInput', () => ({
  default: () => null,
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }) },
}))

vi.mock('@/api/notification', () => ({
  notificationApi: {
    list: vi.fn().mockResolvedValue({ data: [] }),
    preferences: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('@/api/auth', () => ({
  authApi: {
    profile: vi.fn().mockResolvedValue({ data: { id: 'u1', username: 'admin', real_name: '管理员' } }),
    updateProfile: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/stores/useAuthStore', () => {
  const state = { user: { id: 'u1', username: 'admin', real_name: '管理员' }, setUser: vi.fn(), hasPermission: () => true, token: 'test' }
  const useAuthStore = (selector?: any) => selector ? selector(state) : state
  useAuthStore.getState = () => ({ token: 'test', user: { sub: 'u1' } })
  return { useAuthStore }
})

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({ id: 'test-1' }) }
})

import LeadDetail from '../lead/LeadDetail'
import ServiceTicketDetail from '../service/ServiceTicketDetail'
import NotificationCenter from '../notification/NotificationCenter'
import ProfilePage from '../profile/ProfilePage'

describe('LeadDetail', () => {
  it('renders page structure', () => {
    render(<LeadDetail />)
    expect(document.querySelector('.ant-skeleton') || document.querySelector('[class*="skeleton"]')).toBeTruthy()
  })
})

describe('ServiceTicketDetail', () => {
  it('renders page structure', () => {
    render(<ServiceTicketDetail />)
    expect(document.querySelector('.ant-skeleton') || document.querySelector('[class*="skeleton"]')).toBeTruthy()
  })
})

describe('NotificationCenter', () => {
  it('renders page title', () => {
    render(<NotificationCenter />)
    expect(screen.getByText('通知中心')).toBeInTheDocument()
  })
})

describe('ProfilePage', () => {
  it('renders page title', () => {
    render(<ProfilePage />)
    expect(screen.getByText('个人中心')).toBeInTheDocument()
  })
})
