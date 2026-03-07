import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('@/api/lead', () => ({
  leadApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 'l1', title: '测试', status: 'new' } }),
    create: vi.fn().mockResolvedValue({ data: {} }),
    update: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/api/customer', () => ({
  customerApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 'c1', name: '客户A' } }),
    create: vi.fn().mockResolvedValue({ data: {} }),
    update: vi.fn().mockResolvedValue({ data: {} }),
    list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    checkUnique: vi.fn().mockResolvedValue({ data: { unique: true } }),
  },
}))

vi.mock('@/api/project', () => ({
  projectApi: {
    get: vi.fn().mockResolvedValue({ data: { id: 'p1', name: '项目A', stage: 'S1' } }),
    create: vi.fn().mockResolvedValue({ data: {} }),
    update: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }) },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn(), useParams: () => ({}) }
})

import LeadForm from '../lead/LeadForm'
import CustomerForm from '../customer/CustomerForm'
import OpportunityForm from '../opportunity/OpportunityForm'

describe('LeadForm', () => {
  it('renders create mode title', () => {
    render(<LeadForm />)
    expect(screen.getByText('新建线索')).toBeInTheDocument()
  })
})

describe('CustomerForm', () => {
  it('renders create mode title', () => {
    render(<CustomerForm />)
    expect(screen.getByText('新建客户')).toBeInTheDocument()
  })
})

describe('OpportunityForm', () => {
  it('renders create mode title', () => {
    render(<OpportunityForm />)
    expect(screen.getByText('新建商机')).toBeInTheDocument()
  })
})
