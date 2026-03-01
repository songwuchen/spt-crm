import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MilestoneGantt from '../MilestoneGantt'
import type { DeliveryMilestone } from '@/api/types'

const makeMilestone = (overrides: Partial<DeliveryMilestone> = {}): DeliveryMilestone => ({
  id: 'ms-1',
  project_id: 'p-1',
  milestone_code: 'design',
  name: '设计评审',
  plan_date: '2026-03-10',
  actual_date: null as unknown as string,
  status: 'doing',
  source_type: 'manual',
  sort_order: 1,
  note: '',
  created_at: '2026-03-01T00:00:00',
  ...overrides,
})

describe('MilestoneGantt', () => {
  it('renders empty state when no milestones', () => {
    render(<MilestoneGantt milestones={[]} />)
    expect(screen.getByText('暂无带日期的里程碑数据')).toBeInTheDocument()
  })

  it('renders milestone name', () => {
    const milestones = [makeMilestone()]
    render(<MilestoneGantt milestones={milestones} />)
    expect(screen.getByText('设计评审')).toBeInTheDocument()
  })

  it('shows overdue tag when past plan date and not completed', () => {
    const milestones = [
      makeMilestone({
        plan_date: '2025-01-01',
        status: 'doing',
      }),
    ]
    render(<MilestoneGantt milestones={milestones} />)
    expect(screen.getByText('延期')).toBeInTheDocument()
  })

  it('does not show overdue tag when completed on time', () => {
    const milestones = [
      makeMilestone({
        plan_date: '2026-03-10',
        actual_date: '2026-03-08',
        status: 'done',
      }),
    ]
    render(<MilestoneGantt milestones={milestones} />)
    expect(screen.queryByText('延期')).not.toBeInTheDocument()
  })

  it('renders multiple milestones', () => {
    const milestones = [
      makeMilestone({ id: 'ms-1', name: '设计评审', plan_date: '2026-03-10', sort_order: 1 }),
      makeMilestone({ id: 'ms-2', name: '生产制造', plan_date: '2026-04-15', sort_order: 2 }),
      makeMilestone({ id: 'ms-3', name: '出厂验收', plan_date: '2026-05-20', sort_order: 3 }),
    ]
    render(<MilestoneGantt milestones={milestones} />)
    expect(screen.getByText('设计评审')).toBeInTheDocument()
    expect(screen.getByText('生产制造')).toBeInTheDocument()
    expect(screen.getByText('出厂验收')).toBeInTheDocument()
  })

  it('skips milestones without plan_date', () => {
    const milestones = [
      makeMilestone({ id: 'ms-1', name: '有日期', plan_date: '2026-03-10' }),
      makeMilestone({ id: 'ms-2', name: '无日期', plan_date: undefined as unknown as string }),
    ]
    render(<MilestoneGantt milestones={milestones} />)
    expect(screen.getByText('有日期')).toBeInTheDocument()
    expect(screen.queryByText('无日期')).not.toBeInTheDocument()
  })
})
