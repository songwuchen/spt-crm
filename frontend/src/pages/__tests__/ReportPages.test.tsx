import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/api/dashboard', () => ({
  dashboardApi: {
    funnel: vi.fn().mockResolvedValue({ data: [] }),
    leaderboard: vi.fn().mockResolvedValue({ data: [] }),
    collection: vi.fn().mockResolvedValue({ data: [] }),
    customerRegionStats: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('@/api/product', () => ({
  productApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    categories: vi.fn().mockResolvedValue({ data: [] }),
  },
}))

vi.mock('@/api/customer', () => ({
  customerApi: {
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
  },
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }) },
}))

vi.mock('@ant-design/charts', () => ({
  Column: () => <div data-testid="column-chart" />,
  Pie: () => <div data-testid="pie-chart" />,
  Bar: () => <div data-testid="bar-chart" />,
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import ProductReport from '../report/ProductReport'
import CustomerLifecycleReport from '../report/CustomerLifecycleReport'
import TeamPerformanceReport from '../report/TeamPerformanceReport'

describe('ProductReport', () => {
  it('renders page title', () => {
    render(<ProductReport />)
    expect(screen.getByText('产品销售报表')).toBeInTheDocument()
  })
})

describe('CustomerLifecycleReport', () => {
  it('renders page title', () => {
    render(<CustomerLifecycleReport />)
    expect(screen.getByText('客户生命周期报表')).toBeInTheDocument()
  })
})

describe('TeamPerformanceReport', () => {
  it('renders page title', () => {
    render(<TeamPerformanceReport />)
    expect(screen.getByText('团队绩效报表')).toBeInTheDocument()
  })
})
