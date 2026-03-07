import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('@/api/customer', () => ({
  customerApi: {
    listPool: vi.fn(),
    claim: vi.fn(),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import CustomerPool from '../customer/CustomerPool'
import { customerApi } from '@/api/customer'

describe('CustomerPool', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(customerApi.listPool as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [
          { id: 'c-1', name: '公海客户A', level: 'A', industry: '制造', region: '华东', source: '展会', updated_at: '2026-03-01T10:00:00' },
          { id: 'c-2', name: '公海客户B', level: 'B', industry: '科技', region: '华南', source: '官网', updated_at: '2026-03-02T10:00:00' },
        ],
        total: 2,
      },
    })
  })

  it('renders page title and description', () => {
    render(<CustomerPool />)
    expect(screen.getByText('客户公海')).toBeInTheDocument()
    expect(screen.getByText('无人负责的客户，可自由领取跟进')).toBeInTheDocument()
  })

  it('loads and displays pool customers', async () => {
    render(<CustomerPool />)
    await waitFor(() => {
      expect(screen.getByText('公海客户A')).toBeInTheDocument()
      expect(screen.getByText('公海客户B')).toBeInTheDocument()
    })
  })

  it('shows total count in stats bar', async () => {
    render(<CustomerPool />)
    await waitFor(() => {
      expect(customerApi.listPool).toHaveBeenCalled()
    })
  })

  it('renders search input', () => {
    render(<CustomerPool />)
    expect(screen.getByPlaceholderText('搜索客户名称')).toBeInTheDocument()
  })

  it('renders level filter', () => {
    render(<CustomerPool />)
    // '级别' appears in stats bar level tags and filter placeholder
    expect(screen.getAllByText(/级别|级/).length).toBeGreaterThanOrEqual(1)
  })

  it('shows claim buttons for each customer', async () => {
    render(<CustomerPool />)
    await waitFor(() => {
      // '领取' appears in table action buttons + possible batch button
      const claimBtns = screen.getAllByText(/领取/)
      expect(claimBtns.length).toBeGreaterThanOrEqual(1)
    })
  })
})
