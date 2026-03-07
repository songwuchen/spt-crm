import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('@/api/task', () => ({
  taskApi: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => vi.fn() }
})

import TaskPage from '../task/TaskPage'
import { taskApi } from '@/api/task'

describe('TaskPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(taskApi.list as ReturnType<typeof vi.fn>).mockResolvedValue({
      data: {
        items: [
          { id: 't-1', title: '编写方案', priority: 'high', status: 'todo', is_completed: false, due_date: '2026-03-10', assignee_name: '张三', created_at: '2026-03-01' },
          { id: 't-2', title: '回访客户', priority: 'normal', status: 'done', is_completed: true, due_date: null, assignee_name: '李四', created_at: '2026-03-02' },
          { id: 't-3', title: '紧急报价', priority: 'urgent', status: 'todo', is_completed: false, due_date: '2026-01-01', assignee_name: '王五', created_at: '2026-03-03' },
        ],
        total: 3,
      },
    })
  })

  it('renders page title and summary', async () => {
    render(<TaskPage />)
    expect(screen.getByText('待办任务')).toBeInTheDocument()
    await waitFor(() => {
      expect(taskApi.list).toHaveBeenCalled()
    })
  })

  it('loads and displays task data', async () => {
    render(<TaskPage />)
    await waitFor(() => {
      expect(screen.getByText('编写方案')).toBeInTheDocument()
      expect(screen.getByText('回访客户')).toBeInTheDocument()
      expect(screen.getByText('紧急报价')).toBeInTheDocument()
    })
  })

  it('shows priority tags', async () => {
    render(<TaskPage />)
    await waitFor(() => {
      expect(screen.getByText('紧急')).toBeInTheDocument()
      expect(screen.getByText('高')).toBeInTheDocument()
    })
  })

  it('shows overdue indicator for past due dates', async () => {
    render(<TaskPage />)
    await waitFor(() => {
      // Task t-3 has due_date 2026-01-01 which is past (current date 2026-03-07)
      const overdueElements = screen.getAllByText(/逾期/)
      expect(overdueElements.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('renders new task button', () => {
    render(<TaskPage />)
    expect(screen.getByText('新建任务')).toBeInTheDocument()
  })

  it('renders filter selects', () => {
    render(<TaskPage />)
    // Status and priority filter placeholders — may appear in table headers too
    expect(screen.getAllByText('状态').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('优先级').length).toBeGreaterThanOrEqual(1)
  })
})
