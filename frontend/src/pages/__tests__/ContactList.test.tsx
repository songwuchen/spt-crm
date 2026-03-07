import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import ContactList from '../customer/ContactList'

vi.mock('@/api/contact', () => ({
  contactApi: {
    listAll: vi.fn().mockResolvedValue({
      data: {
        items: [
          { id: 'ct-1', customer_id: 'c-1', customer_name: '测试客户', name: '张经理', title: '总经理', role_type: 'decision_maker', phone: '021-12345678', mobile: '13800138000', email: 'zhang@test.com', is_primary: true, remark: '', created_at: '2026-01-01T00:00:00' },
          { id: 'ct-2', customer_id: 'c-1', customer_name: '测试客户', name: '李工', title: '技术总监', role_type: 'influencer', phone: '', mobile: '13900139000', email: 'li@test.com', is_primary: false, remark: '', created_at: '2026-01-02T00:00:00' },
        ],
        total: 2,
      },
    }),
    list: vi.fn().mockResolvedValue({ data: [] }),
    create: vi.fn().mockResolvedValue({ data: {} }),
    update: vi.fn().mockResolvedValue({ data: {} }),
    delete: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

describe('ContactList', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('renders page title', () => {
    render(<ContactList />)
    expect(screen.getByText('联系人管理')).toBeInTheDocument()
  })

  it('renders contact data', async () => {
    render(<ContactList />)
    await waitFor(() => {
      expect(screen.getByText('张经理')).toBeInTheDocument()
      expect(screen.getByText('李工')).toBeInTheDocument()
    })
  })

  it('renders role type tags', async () => {
    render(<ContactList />)
    await waitFor(() => {
      expect(screen.getByText('决策人')).toBeInTheDocument()
      expect(screen.getByText('影响者')).toBeInTheDocument()
    })
  })

  it('renders customer name links', async () => {
    render(<ContactList />)
    await waitFor(() => {
      const links = screen.getAllByText('测试客户')
      expect(links.length).toBeGreaterThanOrEqual(1)
    })
  })
})
