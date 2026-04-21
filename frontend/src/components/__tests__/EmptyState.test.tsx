import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EmptyState from '../EmptyState'

describe('EmptyState', () => {
  it('renders with default props', () => {
    render(<EmptyState />)
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
    expect(screen.getByText('inbox')).toBeInTheDocument()
  })

  it('renders custom title', () => {
    render(<EmptyState title="没有记录" />)
    expect(screen.getByText('没有记录')).toBeInTheDocument()
  })

  it('renders custom icon', () => {
    render(<EmptyState icon="search_off" />)
    expect(screen.getByText('search_off')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<EmptyState description="请添加数据后重试" />)
    expect(screen.getByText('请添加数据后重试')).toBeInTheDocument()
  })

  it('does not render description when not provided', () => {
    render(<EmptyState />)
    // Only the title element should exist, no description text
    expect(screen.queryByText('请添加数据后重试')).not.toBeInTheDocument()
  })
})
