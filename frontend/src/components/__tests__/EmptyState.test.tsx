import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EmptyState from '../EmptyState'

describe('EmptyState', () => {
  it('renders with default props', () => {
    const { container } = render(<EmptyState />)
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
    // 图标现为 antd 内联 SVG(inbox -> InboxOutlined),不再是 Material Symbols 连字文本
    expect(container.querySelector('.anticon-inbox')).toBeInTheDocument()
  })

  it('renders custom title', () => {
    render(<EmptyState title="没有记录" />)
    expect(screen.getByText('没有记录')).toBeInTheDocument()
  })

  it('renders custom icon', () => {
    const { container } = render(<EmptyState icon="search_off" />)
    expect(container.querySelector('.anticon-search')).toBeInTheDocument()
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
