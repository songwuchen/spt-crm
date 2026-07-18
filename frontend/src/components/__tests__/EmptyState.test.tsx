import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EmptyState from '../EmptyState'

describe('EmptyState', () => {
  it('renders with default props', () => {
    render(<EmptyState />)
    expect(screen.getByText('暂无数据')).toBeInTheDocument()
    // 图标现为 antd 内联 SVG,不再是 Material Symbols 连字文本。
    // 按无障碍名断言(antd 会渲染 role="img" + aria-label),不耦合 antd 的内部 class 命名。
    expect(screen.getByRole('img', { name: 'inbox' })).toBeInTheDocument()
  })

  it('renders custom title', () => {
    render(<EmptyState title="没有记录" />)
    expect(screen.getByText('没有记录')).toBeInTheDocument()
  })

  it('renders custom icon', () => {
    render(<EmptyState icon="search_off" />)
    expect(screen.getByRole('img', { name: 'search' })).toBeInTheDocument()
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
