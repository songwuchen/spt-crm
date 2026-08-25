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
    // ApprovalCenter 用 location.state 打开 WF 抽屉；测试不挂 Router，需自行 mock
    useLocation: () => ({ pathname: '/approvals', search: '', hash: '', state: null, key: 'test' }),
    useSearchParams: () => [new URLSearchParams(), vi.fn()] as const,
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

vi.mock('@/api/unifiedApprovals', () => ({
  fetchUnifiedPending: vi.fn(),
  fetchUnifiedMine: vi.fn().mockResolvedValue([]),
  fetchUnifiedDone: vi.fn().mockResolvedValue([]),
  fetchUnifiedCc: vi.fn().mockResolvedValue([]),
  fetchFilterOptions: vi.fn().mockResolvedValue({ processes: [], node_names: [] }),
  countActiveFilters: vi.fn().mockReturnValue(0),
  decideUnified: vi.fn(),
}))

vi.mock('@/api/lowcodeWorkflow', () => ({
  workflowApi: {
    todo: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    done: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    mine: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    cc: vi.fn().mockResolvedValue({ data: { items: [], total: 0 } }),
    filterOptions: vi.fn().mockResolvedValue({ data: { processes: [], node_names: [] } }),
    listAgents: vi.fn().mockResolvedValue({ data: [] }),
    createAgent: vi.fn(),
    deleteAgent: vi.fn(),
    instance: vi.fn(),
    act: vi.fn(),
    withdraw: vi.fn(),
    urge: vi.fn(),
  },
}))

vi.mock('@/components/lowcode/WfProcessDrawer', () => ({
  useWfProcessDrawer: () => ({ openWith: vi.fn(), node: null }),
  WfProcessDrawer: () => null,
  bizEntityPath: () => null,
}))

vi.mock('@/components/lowcode/fields/PersonField', () => ({
  default: () => null,
}))

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}))

import ApprovalCenter from '../approval/ApprovalCenter'
import { approvalApi } from '@/api/approval'
import { userApi } from '@/api/user'
import { fetchUnifiedPending } from '@/api/unifiedApprovals'

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['approval:view', 'approval:edit'],
  tenant_id: 't-1',
}

const mockUnifiedPending = [
  {
    key: 'legacy:task-1',
    taskId: 'task-1',
    engine: 'legacy' as const,
    title: '报价审批 - QT-001',
    subtitle: '张三 发起 · 节点 1/2',
    bizType: 'quote_version',
    bizId: 'qv-1',
    instanceId: 'flow-1',
    createdAt: '2026-03-10T10:00:00',
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
    ;(fetchUnifiedPending as ReturnType<typeof vi.fn>).mockResolvedValue({
      items: mockUnifiedPending,
      total: mockUnifiedPending.length,
    })
    ;(approvalApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: mockFlows, total: mockFlows.length } })
    ;(userApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({ data: { items: [], total: 0 } })
  })

  it('renders page title', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('审批中心')).toBeInTheDocument()
    })
  })

  it('fetches unified pending on mount without loading all flows', async () => {
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(fetchUnifiedPending).toHaveBeenCalled()
    })
    expect(approvalApi.list).not.toHaveBeenCalled()
  })

  it('loads all flows when switching to 所有审批 tab', async () => {
    const user = userEvent.setup()
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(fetchUnifiedPending).toHaveBeenCalled()
    })
    await user.click(screen.getByRole('tab', { name: /所有审批/ }))
    await waitFor(() => {
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
    ;(fetchUnifiedPending as ReturnType<typeof vi.fn>).mockResolvedValue({ items: [], total: 0 })
    render(<ApprovalCenter />)
    await waitFor(() => {
      expect(screen.getByText('暂无待审批任务')).toBeInTheDocument()
    })
  })
})
