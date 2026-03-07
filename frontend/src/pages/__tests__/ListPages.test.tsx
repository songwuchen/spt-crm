import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/api/payment', () => ({
  paymentApi: {
    listAllPlans: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    listAllRecords: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    listAllInvoices: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    paymentOverview: vi.fn().mockResolvedValue({ data: { total_planned: 0, total_received: 0, overdue_amount: 0, collection_rate: 0 } }),
  },
}))

vi.mock('@/api/product', () => ({
  productApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    categories: vi.fn().mockResolvedValue({ data: [] }),
    listCategories: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('@/api/activity', () => ({
  activityApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    listAll: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/customer', () => ({
  customerApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/change', () => ({
  changeApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/delivery', () => ({
  deliveryApi: {
    listAllMilestones: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn(), useSearchParams: () => [new URLSearchParams(), vi.fn()] }
})

import PaymentPage from '../payment/PaymentPage'
import ProductList from '../product/ProductList'
import FollowUpPage from '../activity/FollowUpPage'
import ChangeRequestList from '../change/ChangeRequestList'
import MilestoneList from '../delivery/MilestoneList'

describe('PaymentPage', () => {
  it('renders page title', () => {
    render(<PaymentPage />)
    expect(screen.getByText('回款管理')).toBeInTheDocument()
  })

  it('renders tabs', () => {
    render(<PaymentPage />)
    expect(screen.getByRole('tab', { name: /回款计划/ })).toBeInTheDocument()
  })
})

describe('ProductList', () => {
  it('renders page title', () => {
    render(<ProductList />)
    expect(screen.getByText('产品目录')).toBeInTheDocument()
  })
})

describe('FollowUpPage', () => {
  it('renders page title', () => {
    render(<FollowUpPage />)
    expect(screen.getByText('跟进记录')).toBeInTheDocument()
  })
})

describe('ChangeRequestList', () => {
  it('renders page title', () => {
    render(<ChangeRequestList />)
    expect(screen.getByText('变更管理')).toBeInTheDocument()
  })
})

describe('MilestoneList', () => {
  it('renders page title', () => {
    render(<MilestoneList />)
    expect(screen.getByText('交付里程碑')).toBeInTheDocument()
  })
})
