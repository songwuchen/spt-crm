/**
 * ApprovalCenter page tests — rendering, tabs, pending list, actions.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

// ---- Mocks ----------------------------------------------------------------

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return {
    ...actual,
    useNavigate: () => vi.fn(),
    useParams: () => ({}),
  }
})

vi.mock('@/api/approval', () => ({
  approvalApi: {
    myPending: vi.fn(),
    list: vi.fn(),
    get: vi.fn(),
    decide: vi.fn(),
    withdraw: vi.fn(),
    delegate: vi.fn(),
    resubmit: vi.fn(),
    bulkDecide: vi.fn(),
    statistics: vi.fn(),
  },
}))

vi.mock('@/api/user', () => ({
  userApi: { list: vi.fn() },
}))

// 审批中心会额外查一次新工作流引擎的待办数，用于提示「还有 N 条待办在流程审批中心」
vi.mock('@/api/lowcodeWorkflow', () => ({
  workflowApi: { todo: vi.fn() },
}))

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}))

import ApprovalCenter from '../approval/ApprovalCenter'
import { approvalApi } from '@/api/approval'
import { userApi } from '@/api/user'
import { workflowApi } from '@/api/lowcodeWorkflow'

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['approval:view', 'approval:edit'],
  tenant_id: 't-1',
}

const mockPending = [
  {
    id: 'task-1',
    flow_id: 'flow-1',
    node_order: 1,
    status: 'pending',
    assignee_id: 'u-1',
    assignee_name: 'Admin',
    flow: {
      id: 'flow-1',
      title: '报价审批 - QT-001',
      biz_type: 'quote_version',
      biz_id: 'qv-1',
      status: 'pending',
      submitted_by_id: 'u-2',
      submitted_by_name: '张三',
      current_node: 1,
      total_nodes: 2,
      approval_mode: 'sequential',
      created_at: '2026-03-10T10:00:00',
    },
  },
]

const mockFlows = [
  {
    id: 'flow-1',
    title: '报价审批 - QT-001',
    biz_type: 'quote_version',
    biz_id: 'qv-1',
    status: 'pending',
    submitted_by_id: 'u-2',
    submitted_by_name: '张三',
    current_node: 1,
    total_nodes: 2,
    approval_mode: 'sequential',
    created_at: '2026-03-10T10:00:00',
    updated_at: '2026-03-10T10:00:00',
  },
  {
    id: 'flow-2',
    title: '合同审批 - CT-001',
    biz_type: 'contract_version',
    biz_id: 'cv-1',
    status: 'approved',
    submitted_by_id: 'u-1',
    submitted_by_name: 'Admin',
    current_node: 2,
    total_nodes: 2,
    approval_mode: 'sequential',
    created_at: '2026-03-09T10:00:00',
    updated_at: '2026-03-09T12:00:00',
  },
]

describe('ApprovalCenter', { timeout: 15000 }, () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    ;(approvalApi.myPending as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockPending })
    ;(approvalApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: mockFlows, total: mockFlows.length } })
    ;(userApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: [], total: 0 } })
    ;(workflowApi.todo as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('renders page title', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('审批中心')).toBeInTheDocument()
    })
  })

  it('fetches pending and all flows on mount', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(approvalApi.myPending).toHaveBeenCalled()
      expect(approvalApi.list).toHaveBeenCalled()
    })
  })

  it('displays pending approval items', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('报价审批 - QT-001')).toBeInTheDocument()
    })
  })

  it('shows pending count badge', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('1')).toBeInTheDocument()
    })
  })

  it('displays approve and reject buttons for pending tasks', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('通过')).toBeInTheDocument()
      expect(screen.getByText('驳回')).toBeInTheDocument()
    })
  })

  it('displays delegate button', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('转交')).toBeInTheDocument()
    })
  })

  it('shows tabs for pending, mine, all, stats', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: /待我审批/ })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /我发起的/ })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /所有审批/ })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: /统计/ })).toBeInTheDocument()
    })
  })

  it('opens decide modal on approve click', async () => {
    const user = userEvent.setup()
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('通过')).toBeInTheDocument()
    })
    await user.click(screen.getByText('通过'))
    await waitFor(() => {
      expect(screen.getByText('审批通过')).toBeInTheDocument()
      expect(screen.getByText('确认通过')).toBeInTheDocument()
    })
  })

  it('renders empty state when no pending tasks', async () => {
    ;(approvalApi.myPending as ReturnType<typeof vi.fn>).mockResolvedValue({ data: [] })
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('暂无待审批任务')).toBeInTheDocument()
    })
  })
})
