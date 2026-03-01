import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import PaymentChart from '../PaymentChart'
import type { PaymentPlanItem, PaymentRecordItem } from '@/api/types'

const makePlan = (overrides: Partial<PaymentPlanItem> = {}): PaymentPlanItem => ({
  id: 'plan-1',
  project_id: 'p-1',
  plan_no: 'PP-001',
  due_date: '2026-03-15',
  amount: 100000,
  status: 'pending',
  remark: '',
  created_at: '2026-03-01T00:00:00',
  ...overrides,
})

const makeRecord = (overrides: Partial<PaymentRecordItem> = {}): PaymentRecordItem => ({
  id: 'rec-1',
  project_id: 'p-1',
  received_date: '2026-03-10',
  amount: 50000,
  channel: 'bank',
  reference_no: 'REF001',
  remark: '',
  created_at: '2026-03-01T00:00:00',
  ...overrides,
})

describe('PaymentChart', () => {
  it('renders empty state when no data', () => {
    render(<PaymentChart plans={[]} records={[]} />)
    expect(screen.getByText('暂无回款数据')).toBeInTheDocument()
  })

  it('renders plan and received totals', () => {
    render(<PaymentChart plans={[makePlan({ amount: 200000 })]} records={[makeRecord({ amount: 80000 })]} />)
    expect(screen.getAllByText('¥200,000').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('¥80,000').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('计划回款').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('实际到账').length).toBeGreaterThanOrEqual(1)
  })

  it('displays collection rate', () => {
    render(<PaymentChart plans={[makePlan({ amount: 100000 })]} records={[makeRecord({ amount: 100000 })]} />)
    expect(screen.getByText('100.0%')).toBeInTheDocument()
  })

  it('shows overdue tag for overdue plans', () => {
    render(
      <PaymentChart
        plans={[makePlan({ due_date: '2025-01-01', status: 'overdue', amount: 50000 })]}
        records={[]}
      />
    )
    expect(screen.getByText('逾期')).toBeInTheDocument()
  })

  it('renders multiple months', () => {
    const plans = [
      makePlan({ id: 'p1', due_date: '2026-03-15', amount: 50000 }),
      makePlan({ id: 'p2', due_date: '2026-04-15', amount: 60000 }),
    ]
    const records = [
      makeRecord({ id: 'r1', received_date: '2026-03-10', amount: 30000 }),
    ]
    render(<PaymentChart plans={plans} records={records} />)
    expect(screen.getByText('26/03')).toBeInTheDocument()
    expect(screen.getByText('26/04')).toBeInTheDocument()
  })
})
