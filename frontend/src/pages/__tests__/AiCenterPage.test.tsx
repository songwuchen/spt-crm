/**
 * AiCenterPage tests — stats, task filtering, template CRUD.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useAuthStore } from '@/stores/useAuthStore'
import type { UserInfo } from '@/api/types'

// ---- Mocks ----------------------------------------------------------------

vi.mock('@/api/ai', () => ({
  aiApi: {
    listTasks: vi.fn(),
    listTemplates: vi.fn(),
    getResult: vi.fn(),
    createTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
  },
}))

import AiCenterPage from '../ai/AiCenterPage'
import { aiApi } from '@/api/ai'

const mockTasks = [
  {
    id: 'task-1',
    task_type: 'customer_insight',
    biz_type: 'customer',
    biz_id: 'cust-1',
    status: 'done',
    model_name: 'gpt-4',
    tokens_in: 500,
    tokens_out: 200,
    cost_est: 0.05,
    created_by_name: 'Admin',
    created_at: '2026-01-15T10:00:00',
  },
  {
    id: 'task-2',
    task_type: 'quote_risk_analysis',
    biz_type: 'project',
    biz_id: 'proj-1',
    status: 'running',
    model_name: 'gpt-4',
    tokens_in: 300,
    tokens_out: 0,
    cost_est: 0.02,
    created_by_name: 'Admin',
    created_at: '2026-01-16T10:00:00',
  },
  {
    id: 'task-3',
    task_type: 'contract_risk',
    biz_type: 'project',
    biz_id: 'proj-2',
    status: 'failed',
    model_name: 'gpt-4',
    tokens_in: 100,
    tokens_out: 0,
    cost_est: 0.01,
    error_message: 'Timeout',
    created_by_name: 'Admin',
    created_at: '2026-01-17T10:00:00',
  },
]

const mockTemplates = [
  {
    id: 'tpl-1',
    code: 'customer_insight_v1',
    name: '客户画像分析',
    task_type: 'customer_insight',
    template_text: '分析客户 {{name}}',
    is_active: true,
    updated_at: '2026-01-10T00:00:00',
  },
]

const adminUser: UserInfo = {
  id: 'u-1',
  username: 'admin',
  real_name: 'Admin',
  roles: ['admin'],
  permissions: ['ai:view', 'ai:manage'],
  tenant_id: 't-1',
}

describe('AiCenterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useAuthStore.getState().setUser(adminUser)
    })
    ;(aiApi.listTasks as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockTasks })
    ;(aiApi.listTemplates as ReturnType<typeof vi.fn>).mockResolvedValue({ data: mockTemplates })
    ;(aiApi.getResult as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: { result_json: { summary: 'Test result' } },
    })
  })

  it('loads tasks on mount', async () => {
    render(<AiCenterPage />)
    await waitFor(() => {
      expect(aiApi.listTasks).toHaveBeenCalled()
    })
  })

  it('displays task stats correctly', async () => {
    render(<AiCenterPage />)
    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument()
    })
  })

  it('shows Prompt template tab', async () => {
    const user = userEvent.setup()
    render(<AiCenterPage />)
    await waitFor(() => expect(aiApi.listTasks).toHaveBeenCalled())

    // Ant Design Tabs renders tab triggers with role="tab"
    const tab = screen.getByRole('tab', { name: /Prompt 模板/ })
    await user.click(tab)
    await waitFor(() => {
      expect(aiApi.listTemplates).toHaveBeenCalled()
    })
  })

  it('displays template in table', async () => {
    const user = userEvent.setup()
    render(<AiCenterPage />)
    await waitFor(() => expect(aiApi.listTasks).toHaveBeenCalled())

    const tab = screen.getByRole('tab', { name: /Prompt 模板/ })
    await user.click(tab)
    await waitFor(() => {
      expect(screen.getByText('客户画像分析')).toBeInTheDocument()
    })
  })

  it('renders task type labels', async () => {
    render(<AiCenterPage />)
    await waitFor(() => {
      expect(screen.getByText(/客户洞察/)).toBeInTheDocument()
    })
  })
})
