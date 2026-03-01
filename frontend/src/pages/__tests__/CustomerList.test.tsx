import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import CustomerList from '../customer/CustomerList'

// Mock customer API — inline data to avoid hoisting issues
vi.mock('@/api/customer', () => ({
  customerApi: {
    list: vi.fn().mockResolvedValue({
      data: {
        items: [
          { id: 'c-1', name: '测试客户A', industry: '电子制造', region: '华东', level: 'A', status: 'active', owner_name: '张三', created_at: '2026-01-15T00:00:00' },
          { id: 'c-2', name: '测试客户B', industry: '航空航天', region: '华南', level: 'B', status: 'active', owner_name: '李四', created_at: '2026-02-20T00:00:00' },
        ],
        total: 2,
      },
    }),
    delete: vi.fn().mockResolvedValue({}),
  },
}))

vi.mock('@/utils/download', () => ({
  downloadFile: vi.fn(),
}))

// Mock useSearchParams
const mockSetSearchParams = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useSearchParams: () => [new URLSearchParams(), mockSetSearchParams],
  }
})

describe('CustomerList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders page title', () => {
    render(<CustomerList />)
    expect(screen.getByText('客户管理')).toBeInTheDocument()
  })

  it('renders search input', () => {
    render(<CustomerList />)
    expect(screen.getByPlaceholderText('搜索客户名称...')).toBeInTheDocument()
  })

  it('renders filter button', () => {
    render(<CustomerList />)
    expect(screen.getByText('筛选')).toBeInTheDocument()
  })

  it('renders action buttons', () => {
    render(<CustomerList />)
    expect(screen.getByText('新建客户')).toBeInTheDocument()
    expect(screen.getByText('导入')).toBeInTheDocument()
    expect(screen.getByText('导出')).toBeInTheDocument()
  })

  it('loads and displays customer data', async () => {
    render(<CustomerList />)
    await waitFor(() => {
      expect(screen.getByText('测试客户A')).toBeInTheDocument()
      expect(screen.getByText('测试客户B')).toBeInTheDocument()
    })
  })

  it('displays customer details in table', async () => {
    render(<CustomerList />)
    await waitFor(() => {
      expect(screen.getByText('电子制造')).toBeInTheDocument()
      expect(screen.getByText('航空航天')).toBeInTheDocument()
    })
  })

  it('shows total count', async () => {
    render(<CustomerList />)
    await waitFor(() => {
      expect(screen.getByText('共 2 条')).toBeInTheDocument()
    })
  })
})
